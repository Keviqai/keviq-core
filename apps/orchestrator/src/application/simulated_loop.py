"""Simulated execution loop for orchestrator.

Proves the pipeline works end-to-end without a real agent runtime.
Picks up pending tasks, creates Runs/Steps, advances through lifecycle
using domain transition methods, and writes outbox events at each step.

This loop will be replaced by the real orchestrator loop in Phase C.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from src.domain.run import Run, TriggerType
from src.domain.step import Step, StepType
from src.domain.task import Task, TaskStatus

from .events import (
    run_completed_event,
    run_completing_event,
    run_queued_event,
    run_started_event,
    step_completed_event,
    step_started_event,
    task_completed_event,
    task_started_event,
)
from .ports import UnitOfWork

logger = logging.getLogger(__name__)


def execute_pending_tasks(uow: UnitOfWork) -> list[UUID]:
    """Find all pending tasks and run simulated execution on each.

    Uses the TaskRepository.list_pending() port method to discover tasks.
    Each task is processed via run_simulated_execution which manages its
    own UoW context. In production, this would be event-driven.

    Returns list of task IDs that were processed.
    """
    # Discover pending task IDs
    with uow:
        pending_tasks = uow.tasks.list_pending(limit=10)
        pending_ids = [t.id for t in pending_tasks]

    # Process each task — run_simulated_execution opens its own with-block
    processed: list[UUID] = []
    for task_id in pending_ids:
        try:
            run_simulated_execution(task_id, uow)
            processed.append(task_id)
        except Exception:
            logger.exception("Simulated execution failed for task %s", task_id)

    return processed


def run_simulated_execution(task_id: UUID, uow: UnitOfWork) -> None:
    """Run simulated execution for a specific task.

    This is the primary entry point for testing.
    """
    with uow:
        task = uow.tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.task_status != TaskStatus.PENDING:
            raise ValueError(f"Task {task_id} is {task.task_status.value}, expected pending")

        _execute_single_task(task, uow)
        uow.commit()


def _execute_single_task(task: Task, uow: UnitOfWork) -> None:
    """Execute simulated lifecycle for a single task.

    Flow:
    1. task: pending → running
    2. create Run (queued)
    3. run: queued → preparing → running
    4. create Step (pending)
    5. step: pending → running → completed
    6. run: running → completing → completed
    7. task: running → completed

    All transitions use domain methods. All transitions emit outbox events.
    Correlation ID is shared across the entire run.
    """
    correlation_id = uuid4()

    # 1. Task: pending → running
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

    # 3. Run: queued → preparing → running
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

    # 5. Step: pending → running → completed
    step.start(input_snapshot={"simulated": True, "task_title": task.title})
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

    step.complete(output_snapshot={"simulated": True, "result": "success"})
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

    # 6. Run: running → completing → completed
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

    # 7. Task: running → completed
    task.complete()
    uow.tasks.save(task)

    uow.outbox.write(task_completed_event(
        task_id=task.id,
        workspace_id=task.workspace_id,
        correlation_id=correlation_id,
        causation_id=run_completed_evt.event_id,
    ))
