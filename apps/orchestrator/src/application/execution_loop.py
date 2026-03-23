"""Real execution loop for orchestrator.

Replaces simulated_loop.py as the production execution path.
Dispatches to agent-runtime via ExecutionDispatchPort and maps results
back to orchestrator domain lifecycle transitions.
"""

from __future__ import annotations

import logging
import os
from uuid import UUID, uuid4

# Orchestrator → agent-runtime dispatch timeout.
# Must be >= agent-runtime's INVOCATION_BUDGET_MS to prevent ghost invocations.
_AGENT_DISPATCH_TIMEOUT_MS = int(os.getenv('AGENT_DISPATCH_TIMEOUT_MS', '120000'))

# Default model alias for agent dispatch.
# Set to 'claude_code_cli:sonnet' to route through Claude Code CLI bridge.
_DEFAULT_MODEL_ALIAS = os.getenv('DEFAULT_MODEL_ALIAS', 'default')

# Skip sandbox provisioning for local-only mode (no Docker execution backend).
_SKIP_SANDBOX = os.getenv('SKIP_SANDBOX_PROVISIONING', 'false').lower() in ('true', '1', 'yes')

from src.domain.run import Run, TriggerType
from src.domain.step import Step, StepType
from src.domain.task import Task, TaskStatus

from .events import (
    OutboxEvent,
    run_completed_event,
    run_completing_event,
    run_failed_event,
    run_queued_event,
    run_started_event,
    run_timed_out_event,
    step_completed_event,
    step_failed_event,
    step_started_event,
    task_completed_event,
    task_failed_event,
    task_started_event,
)
from .ports import ExecutionDispatchPort, ExecutionServicePort, RuntimeExecutionResult, UnitOfWork

logger = logging.getLogger(__name__)


def run_real_execution(
    task_id: UUID,
    uow: UnitOfWork,
    dispatcher: ExecutionDispatchPort,
    execution_service: ExecutionServicePort | None = None,
) -> None:
    """Run real execution for a specific task.

    Flow:
    1. task: pending -> running
    2. create Run (queued -> preparing -> running)
    3. provision sandbox (if execution_service provided)
    4. create Step (pending -> running)
    5. dispatch to agent-runtime (synchronous)
    6. map result -> step completed/failed
    7. run -> completing -> completed (or failed/timed_out)
    8. terminate sandbox (cleanup)
    """
    with uow:
        task = uow.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.task_status != TaskStatus.PENDING:
            raise ValueError(f"Task {task_id} is {task.task_status.value}, expected pending")

        _execute_single_task(task, uow, dispatcher, execution_service)


def _execute_single_task(
    task: Task,
    uow: UnitOfWork,
    dispatcher: ExecutionDispatchPort,
    execution_service: ExecutionServicePort | None = None,
) -> None:
    """Execute real lifecycle for a single task."""
    correlation_id = uuid4()
    agent_invocation_id = uuid4()

    # 1. Task: pending -> running
    task.start()
    uow.tasks.save(task)

    task_started_evt = task_started_event(
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
    )
    uow.outbox.write(task_started_evt)

    # 2. Create Run
    run = Run(
        task_id=task.id,
        workspace_id=task.workspace_id,
        trigger_type=TriggerType.MANUAL,
    )
    uow.runs.save(run)

    run_queued_evt = run_queued_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        trigger_type=run.trigger_type.value,
        causation_id=task_started_evt.event_id,
    )
    uow.outbox.write(run_queued_evt)

    # 3. Run: queued -> preparing -> running
    run.prepare()
    uow.runs.save(run)

    run.start()
    uow.runs.save(run)

    run_started_evt = run_started_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=run_queued_evt.event_id,
    )
    uow.outbox.write(run_started_evt)

    # 4. Create Step
    step = Step(
        run_id=run.id,
        workspace_id=task.workspace_id,
        sequence=1,
        step_type=StepType.AGENT_INVOCATION,
    )
    uow.steps.save(step)

    # 5. Step: pending -> running
    step.start(input_snapshot={
        "task_title": task.title,
        "agent_invocation_id": str(agent_invocation_id),
    })
    uow.steps.save(step)

    step_started_evt = step_started_event(
        step_id=step.id,
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        step_type=step.step_type.value,
        sequence=step.sequence,
        causation_id=run_started_evt.event_id,
    )
    uow.outbox.write(step_started_evt)

    # 6. Dispatch to agent-runtime (outside transaction — sync HTTP call)
    #    We commit current state first so step is visible as "running"
    uow.commit()

    # Save IDs and values before dispatch — needed for reload after commit.
    # After commit(), SQLAlchemy expires the ORM objects (DetachedInstanceError).
    task_id = task.id
    run_id = run.id
    step_id = step.id
    workspace_id = task.workspace_id
    task_title = task.title
    task_input_config = task.input_config

    # 6a. Provision sandbox if execution-service is available (skip in local-only mode)
    sandbox_id = None
    if execution_service is not None and not _SKIP_SANDBOX:
        try:
            sandbox_info = execution_service.provision_sandbox(
                workspace_id=workspace_id,
                task_id=task_id,
                run_id=run_id,
                step_id=step_id,
                agent_invocation_id=agent_invocation_id,
                sandbox_type="container",
            )
            sandbox_id = sandbox_info.sandbox_id
            logger.info(
                "Provisioned sandbox %s for task %s", sandbox_id, task_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to provision sandbox for task %s: %s", task_id, exc,
            )
            # Sandbox provision failure → task failure
            exec_result = RuntimeExecutionResult(
                agent_invocation_id=agent_invocation_id,
                status="failed",
                error_code="SANDBOX_PROVISION_FAILED",
                error_message=f"Failed to provision sandbox: {type(exc).__name__}: {exc}",
            )
            _finalize_execution(
                task_id, run_id, step_id, workspace_id,
                exec_result, correlation_id, step_started_evt, uow,
            )
            return

    logger.info("Dispatching task %s to agent-runtime", task_id)

    # Initialize so _map_termination_reason works even on unexpected errors
    exec_result = RuntimeExecutionResult(
        agent_invocation_id=agent_invocation_id,
        status="failed",
        error_code="DISPATCH_ERROR",
        error_message="Dispatch did not complete",
    )

    try:
        # Build input payload, including sandbox_id if provisioned
        input_payload = task_input_config if task_input_config is not None else {}
        if sandbox_id is not None:
            input_payload = {**input_payload, "sandbox_id": str(sandbox_id)}

        exec_result = dispatcher.dispatch(
            agent_invocation_id=agent_invocation_id,
            workspace_id=workspace_id,
            task_id=task_id,
            run_id=run_id,
            step_id=step_id,
            correlation_id=correlation_id,
            agent_id="default-agent",
            model_alias=_DEFAULT_MODEL_ALIAS,
            instruction=task_title,
            input_payload=input_payload,
            timeout_ms=_AGENT_DISPATCH_TIMEOUT_MS,
        )
    except Exception as exc:
        logger.exception("Unexpected error during dispatch for task %s", task_id)
        exec_result = RuntimeExecutionResult(
            agent_invocation_id=agent_invocation_id,
            status="failed",
            error_code="DISPATCH_ERROR",
            error_message=f"Unexpected dispatch error: {type(exc).__name__}",
        )
    finally:
        # 8. Terminate sandbox (cleanup — always, regardless of outcome)
        if sandbox_id is not None and execution_service is not None:
            # Map execution outcome to termination reason
            termination_reason = _map_termination_reason(exec_result)
            try:
                execution_service.terminate_sandbox(
                    sandbox_id, reason=termination_reason,
                )
                logger.info("Terminated sandbox %s for task %s", sandbox_id, task_id)
            except Exception as exc:
                logger.warning(
                    "Failed to terminate sandbox %s: %s", sandbox_id, exc,
                )

    # 7. Map result back to orchestrator lifecycle (new transaction)
    _finalize_execution(
        task_id, run_id, step_id, workspace_id,
        exec_result, correlation_id, step_started_evt, uow,
    )


def _map_termination_reason(exec_result: RuntimeExecutionResult) -> str:
    """Map execution outcome to sandbox termination reason.

    Uses the TerminationReason enum values from execution-service domain:
    completed, timeout, error, policy_violation, manual.
    """
    if exec_result.is_success:
        return "completed"
    if exec_result.is_timeout:
        return "timeout"
    # All other failures — dispatch error, sandbox provision failure, etc.
    return "error"


def _finalize_execution(
    task_id: UUID,
    run_id: UUID,
    step_id: UUID,
    workspace_id: UUID,
    exec_result: RuntimeExecutionResult,
    correlation_id: UUID,
    step_started_evt: OutboxEvent,
    uow: UnitOfWork,
) -> None:
    """Map execution result back to orchestrator lifecycle (new transaction)."""
    with uow:
        # Reload entities to get fresh state after commit
        task = uow.tasks.get_by_id(task_id)
        run = uow.runs.get_by_id(run_id)
        step = uow.steps.get_by_id(step_id)

        if task is None or run is None or step is None:
            raise RuntimeError(
                f"Entities disappeared after mid-execution commit: "
                f"task={task_id} run={run_id} step={step_id}"
            )

        if exec_result.is_success:
            _handle_success(task, run, step, exec_result, correlation_id, step_started_evt, uow)
        elif exec_result.is_timeout:
            _handle_timeout(task, run, step, exec_result, correlation_id, step_started_evt, uow)
        else:
            _handle_failure(task, run, step, exec_result, correlation_id, step_started_evt, uow)

        uow.commit()

    logger.info("Task %s execution completed with status: %s", task_id, exec_result.status)


def _handle_success(
    task: Task,
    run: Run,
    step: Step,
    result: RuntimeExecutionResult,
    correlation_id: UUID,
    step_started_evt: OutboxEvent,
    uow: UnitOfWork,
) -> None:
    """Map successful execution to step/run/task completion."""
    # Step: running -> completed
    step.complete(output_snapshot={
        "output_text": result.output_text,
        "agent_invocation_id": str(result.agent_invocation_id),
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    })
    uow.steps.save(step)

    step_completed_evt = step_completed_event(
        step_id=step.id,
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=step_started_evt.event_id,
    )
    uow.outbox.write(step_completed_evt)

    # Run: running -> completing -> completed
    run.begin_completing()
    uow.runs.save(run)

    run_completing_evt = run_completing_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=step_completed_evt.event_id,
    )
    uow.outbox.write(run_completing_evt)

    run.complete()
    uow.runs.save(run)

    run_completed_evt = run_completed_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        duration_ms=run.duration_ms,
        causation_id=run_completing_evt.event_id,
    )
    uow.outbox.write(run_completed_evt)

    # Task: running -> completed
    task.complete()
    uow.tasks.save(task)

    uow.outbox.write(task_completed_event(
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=run_completed_evt.event_id,
    ))


def _handle_failure(
    task: Task,
    run: Run,
    step: Step,
    result: RuntimeExecutionResult,
    correlation_id: UUID,
    step_started_evt: OutboxEvent,
    uow: UnitOfWork,
) -> None:
    """Map failed execution to step/run/task failure."""
    # Use error_message directly as summary (agent-runtime now provides user-friendly messages).
    # error_code is preserved in step.error_detail for debugging.
    error_summary = result.error_message or result.error_code or "Unknown error"

    # Step: running -> failed
    step.fail(error_detail={
        "error_code": result.error_code or "UNKNOWN",
        "error_message": result.error_message or "",
        "agent_invocation_id": str(result.agent_invocation_id),
        "retryable": result.retryable,
    })
    uow.steps.save(step)

    step_failed_evt = step_failed_event(
        step_id=step.id,
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        error_code=result.error_code,
        error_message=result.error_message,
        causation_id=step_started_evt.event_id,
    )
    uow.outbox.write(step_failed_evt)

    # Run: running -> failed
    run.fail(error_summary=error_summary)
    uow.runs.save(run)

    run_failed_evt = run_failed_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        error_summary=error_summary,
        causation_id=step_failed_evt.event_id,
    )
    uow.outbox.write(run_failed_evt)

    # Task: running -> failed
    task.fail()
    uow.tasks.save(task)

    uow.outbox.write(task_failed_event(
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        error_summary=error_summary,
        causation_id=run_failed_evt.event_id,
    ))


def _handle_timeout(
    task: Task,
    run: Run,
    step: Step,
    result: RuntimeExecutionResult,
    correlation_id: UUID,
    step_started_evt: OutboxEvent,
    uow: UnitOfWork,
) -> None:
    """Map timed-out execution to step failure + run timeout + task failure."""
    error_summary = f"TIMEOUT: {result.error_message}" if result.error_message else "Execution timed out"

    # Step: running -> failed (step has no timed_out state)
    step.fail(error_detail={
        "error_code": "TIMEOUT",
        "error_message": result.error_message or "Execution timed out",
        "agent_invocation_id": str(result.agent_invocation_id),
    })
    uow.steps.save(step)

    step_failed_evt = step_failed_event(
        step_id=step.id,
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        error_code="TIMEOUT",
        error_message=result.error_message,
        causation_id=step_started_evt.event_id,
    )
    uow.outbox.write(step_failed_evt)

    # Run: running -> timed_out
    run.time_out()
    uow.runs.save(run)

    run_timed_out_evt = run_timed_out_event(
        run_id=run.id,
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=step_failed_evt.event_id,
    )
    uow.outbox.write(run_timed_out_evt)

    # Task: running -> failed (task has no timed_out state)
    task.fail()
    uow.tasks.save(task)

    uow.outbox.write(task_failed_event(
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        error_summary=error_summary,
        causation_id=run_timed_out_evt.event_id,
    ))
