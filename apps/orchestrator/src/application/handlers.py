"""Command handlers for orchestrator.

Each handler:
- Calls domain transition methods (never sets status directly)
- Uses repository abstractions (no raw SQL, no SQLAlchemy models)
- Writes outbox events in the same transaction as state mutations
- Returns domain objects for the caller (API layer in PR10)
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.domain.errors import DomainError, DomainValidationError, InvalidTransitionError
from src.domain.run import Run
from src.domain.step import Step, StepStatus
from src.domain.task import Task, TaskStatus, TaskType

from .commands import CancelTask, CreateTaskDraft, LaunchTask, RetryTask, SubmitTask, UpdateTaskBrief
from .events import (
    OutboxEvent,
    run_cancelled_event,
    step_cancelled_event,
    task_cancelled_event,
    task_retried_event,
    task_submitted_event,
)
from .ports import UnitOfWork


class SubmitTaskResult:
    __slots__ = ("task",)

    def __init__(self, task: Task):
        self.task = task


class CancelTaskResult:
    __slots__ = ("task", "cancelled_runs", "cancelled_steps")

    def __init__(
        self,
        task: Task,
        cancelled_runs: list[Run],
        cancelled_steps: list[Step],
    ):
        self.task = task
        self.cancelled_runs = cancelled_runs
        self.cancelled_steps = cancelled_steps


def handle_submit_task(cmd: SubmitTask, uow: UnitOfWork) -> SubmitTaskResult:
    """Create a Task in DRAFT, then submit it (draft → pending).

    Writes task.submitted event to outbox in the same transaction.
    """
    with uow:
        task = Task(
            workspace_id=cmd.workspace_id,
            title=cmd.title,
            task_type=TaskType(cmd.task_type),
            created_by_id=cmd.created_by_id,
            description=cmd.description,
            input_config=cmd.input_config,
            repo_snapshot_id=cmd.repo_snapshot_id,
            policy_id=cmd.policy_id,
            parent_task_id=cmd.parent_task_id,
        )
        task.submit()  # draft → pending

        uow.tasks.save(task)
        uow.outbox.write(task_submitted_event(
            task_id=task.id,
            workspace_id=task.workspace_id,
            correlation_id=uuid4(),  # new correlation context for this task
            created_by_id=task.created_by_id,
            title=task.title,
            task_type=task.task_type.value,
        ))
        uow.commit()

    return SubmitTaskResult(task=task)


class CreateTaskDraftResult:
    __slots__ = ("task",)

    def __init__(self, task: Task):
        self.task = task


class UpdateTaskBriefResult:
    __slots__ = ("task",)

    def __init__(self, task: Task):
        self.task = task


def handle_create_draft(cmd: CreateTaskDraft, uow: UnitOfWork) -> CreateTaskDraftResult:
    """Create a Task in DRAFT status without auto-submitting.

    Task stays in draft until explicitly submitted or launched.
    """
    with uow:
        task = Task(
            workspace_id=cmd.workspace_id,
            title=cmd.title,
            task_type=TaskType(cmd.task_type),
            created_by_id=cmd.created_by_id,
            description=cmd.description,
            goal=cmd.goal,
            context=cmd.context,
            constraints=cmd.constraints,
            desired_output=cmd.desired_output,
            template_id=cmd.template_id,
            agent_template_id=cmd.agent_template_id,
            risk_level=cmd.risk_level,
            input_config=cmd.input_config,
        )
        # Stays in DRAFT — no submit()
        uow.tasks.save(task)
        uow.commit()

    return CreateTaskDraftResult(task=task)


def handle_update_brief(cmd: UpdateTaskBrief, uow: UnitOfWork) -> UpdateTaskBriefResult:
    """Update brief fields on a draft task."""
    with uow:
        task = uow.tasks.get_by_id(cmd.task_id)
        if task is None:
            raise DomainError(f"Task {cmd.task_id} not found")

        task.update_brief(**cmd.updates)
        uow.tasks.save(task)
        uow.commit()

    return UpdateTaskBriefResult(task=task)


# ── Launch Task ───────────────────────────────────────────────


class LaunchTaskResult:
    __slots__ = ("task",)

    def __init__(self, task: Task):
        self.task = task


def _validate_launch_readiness(task: Task) -> None:
    """Check that a draft task has all required fields for launch."""
    if task.task_status != TaskStatus.DRAFT:
        raise DomainValidationError(
            "Task",
            f"cannot launch from status {task.task_status.value}",
        )
    missing = []
    if not task.title or not task.title.strip():
        missing.append("title")
    if not task.goal or not task.goal.strip():
        missing.append("goal")
    if not task.desired_output or not task.desired_output.strip():
        missing.append("desired_output")
    if not task.agent_template_id:
        missing.append("agent_template_id")
    if missing:
        raise DomainValidationError(
            "Task",
            f"cannot launch — missing required fields: {', '.join(missing)}",
        )


def handle_launch_task(
    cmd: LaunchTask, uow: UnitOfWork,
) -> LaunchTaskResult:
    """Validate readiness, auto-set risk, submit draft → pending."""
    with uow:
        task = uow.tasks.get_by_id(cmd.task_id)
        if task is None:
            raise DomainError(f"Task {cmd.task_id} not found")

        _validate_launch_readiness(task)

        # Auto-set risk_level from agent template if not specified
        if not task.risk_level and task.agent_template_id:
            agent_tmpl = uow.agent_templates.get_by_id(
                task.agent_template_id,
            )
            if agent_tmpl:
                task.update_brief(
                    risk_level=agent_tmpl.default_risk_profile,
                )

        task.submit()  # draft → pending
        uow.tasks.save(task)
        uow.outbox.write(task_submitted_event(
            task_id=task.id,
            workspace_id=task.workspace_id,
            correlation_id=uuid4(),
            created_by_id=cmd.launched_by_id,
            title=task.title,
            task_type=task.task_type.value,
        ))
        uow.commit()

    return LaunchTaskResult(task=task)


def handle_cancel_task(cmd: CancelTask, uow: UnitOfWork) -> CancelTaskResult:
    """Cancel a Task and cascade to all active Runs and Steps.

    Writes task.cancelled + run.cancelled + step.cancelled events
    in the same transaction as state mutations.
    """
    with uow:
        task = uow.tasks.get_by_id(cmd.task_id)
        if task is None:
            raise DomainError(f"Task {cmd.task_id} not found")

        # Domain transition — will raise if invalid
        task.cancel()
        uow.tasks.save(task)

        # Cascade to active runs
        cancelled_runs: list[Run] = []
        cancelled_steps: list[Step] = []
        events: list[OutboxEvent] = []

        # Use task.id as correlation for cancellation cascade
        correlation_id = uuid4()
        cancel_event = task_cancelled_event(
            task_id=task.id,
            workspace_id=task.workspace_id,
            correlation_id=correlation_id,
            cancelled_by_id=cmd.cancelled_by_id,
        )
        events.append(cancel_event)

        active_runs = uow.runs.list_active_by_task(task.id)
        for run in active_runs:
            run.cancel()
            uow.runs.save(run)
            cancelled_runs.append(run)

            run_event = run_cancelled_event(
                run_id=run.id,
                task_id=task.id,
                workspace_id=task.workspace_id,
                correlation_id=correlation_id,
                causation_id=cancel_event.event_id,
            )
            events.append(run_event)

            # Cascade to active steps within this run
            active_steps = uow.steps.list_active_by_run(run.id)
            for step in active_steps:
                step.cancel()
                uow.steps.save(step)
                cancelled_steps.append(step)

                events.append(step_cancelled_event(
                    step_id=step.id,
                    run_id=run.id,
                    task_id=task.id,
                    workspace_id=task.workspace_id,
                    correlation_id=correlation_id,
                    causation_id=run_event.event_id,
                ))

        for event in events:
            uow.outbox.write(event)

        uow.commit()

    return CancelTaskResult(
        task=task,
        cancelled_runs=cancelled_runs,
        cancelled_steps=cancelled_steps,
    )


class RetryTaskResult:
    __slots__ = ("task",)

    def __init__(self, task: Task):
        self.task = task


def handle_retry_task(cmd: RetryTask, uow: UnitOfWork) -> RetryTaskResult:
    """Retry a failed task: failed → pending.

    Emits task.retried event. The execution loop picks up the pending task
    and creates a new Run (same pattern as handle_launch_task).
    """
    with uow:
        task = uow.tasks.get_by_id(cmd.task_id)
        if task is None:
            raise DomainError(f"Task {cmd.task_id} not found")

        task.retry()
        uow.tasks.save(task)

        uow.outbox.write(task_retried_event(
            task_id=task.id,
            workspace_id=task.workspace_id,
            correlation_id=uuid4(),
            retried_by_id=cmd.retried_by_id,
        ))
        uow.commit()

    return RetryTaskResult(task=task)
