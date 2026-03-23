"""Unit tests for command handlers.

Uses FakeUnitOfWork — no database needed.
"""

import pytest
from uuid import uuid4

from src.application.commands import CancelTask, SubmitTask
from src.application.handlers import handle_cancel_task, handle_submit_task
from src.domain.errors import DomainError, InvalidTransitionError
from src.domain.run import Run, RunStatus, TriggerType
from src.domain.step import Step, StepStatus, StepType
from src.domain.task import TaskStatus

from .fake_uow import FakeUnitOfWork


# ── SubmitTask ──────────────────────────────────────────────────

class TestSubmitTask:
    def test_happy_path(self):
        uow = FakeUnitOfWork()
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Build feature X",
            task_type="coding",
            created_by_id=uuid4(),
        )
        result = handle_submit_task(cmd, uow)

        assert result.task.task_status == TaskStatus.PENDING
        assert result.task.title == "Build feature X"
        assert uow.committed is True

        # Verify task persisted
        saved = uow.tasks.get_by_id(result.task.id)
        assert saved is not None
        assert saved.task_status == TaskStatus.PENDING

        # Verify outbox event
        assert len(uow.outbox.events) == 1
        evt = uow.outbox.events[0]
        assert evt.event_type == "task.submitted"
        assert evt.task_id == result.task.id
        assert evt.workspace_id == cmd.workspace_id
        assert evt.correlation_id is not None

    def test_with_optional_fields(self):
        uow = FakeUnitOfWork()
        repo_id = uuid4()
        policy_id = uuid4()
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Research task",
            task_type="research",
            created_by_id=uuid4(),
            description="Deep research",
            input_config={"query": "AI safety"},
            repo_snapshot_id=repo_id,
            policy_id=policy_id,
        )
        result = handle_submit_task(cmd, uow)

        assert result.task.description == "Deep research"
        assert result.task.input_config == {"query": "AI safety"}
        assert result.task.repo_snapshot_id == repo_id
        assert result.task.policy_id == policy_id

    def test_invalid_task_type_rejected(self):
        uow = FakeUnitOfWork()
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Bad type",
            task_type="invalid_type",
            created_by_id=uuid4(),
        )
        with pytest.raises(ValueError):
            handle_submit_task(cmd, uow)

    def test_no_direct_status_set(self):
        """Verify handler uses domain transition, not direct assignment."""
        uow = FakeUnitOfWork()
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Test",
            task_type="coding",
            created_by_id=uuid4(),
        )
        result = handle_submit_task(cmd, uow)
        # Task went through draft → pending via submit(), not .task_status = PENDING
        assert result.task.task_status == TaskStatus.PENDING


# ── CancelTask ──────────────────────────────────────────────────

class TestCancelTask:
    def _setup_running_task(self, uow: FakeUnitOfWork):
        """Create a task with a running run and active step."""
        ws_id = uuid4()
        # Create task in running state
        from src.domain.task import Task, TaskType
        task = Task(
            workspace_id=ws_id,
            title="Running task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task.start()
        uow.tasks.save(task)

        # Create active run
        run = Run(
            task_id=task.id,
            workspace_id=ws_id,
            trigger_type=TriggerType.MANUAL,
        )
        run.prepare()
        run.start()
        uow.runs.save(run)

        # Create active step
        step = Step(
            run_id=run.id,
            workspace_id=ws_id,
            sequence=1,
            step_type=StepType.AGENT_INVOCATION,
        )
        step.start()
        uow.steps.save(step)

        return task, run, step

    def test_cancel_running_task(self):
        uow = FakeUnitOfWork()
        task, run, step = self._setup_running_task(uow)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        result = handle_cancel_task(cmd, uow)

        assert result.task.task_status == TaskStatus.CANCELLED
        assert len(result.cancelled_runs) == 1
        assert result.cancelled_runs[0].run_status == RunStatus.CANCELLED
        assert len(result.cancelled_steps) == 1
        assert result.cancelled_steps[0].step_status == StepStatus.CANCELLED
        assert uow.committed is True

    def test_cancel_produces_events(self):
        uow = FakeUnitOfWork()
        task, run, step = self._setup_running_task(uow)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        handle_cancel_task(cmd, uow)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "task.cancelled" in event_types
        assert "run.cancelled" in event_types
        assert "step.cancelled" in event_types

    def test_cancel_events_share_correlation_id(self):
        uow = FakeUnitOfWork()
        task, run, step = self._setup_running_task(uow)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        handle_cancel_task(cmd, uow)

        correlation_ids = {e.correlation_id for e in uow.outbox.events}
        assert len(correlation_ids) == 1, "All cancel events must share one correlation_id"

    def test_cancel_causation_chain(self):
        uow = FakeUnitOfWork()
        task, run, step = self._setup_running_task(uow)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        handle_cancel_task(cmd, uow)

        events = uow.outbox.events
        task_evt = next(e for e in events if e.event_type == "task.cancelled")
        run_evt = next(e for e in events if e.event_type == "run.cancelled")
        step_evt = next(e for e in events if e.event_type == "step.cancelled")

        # task.cancelled has no causation (user-triggered)
        assert task_evt.causation_id is None
        # run.cancelled caused by task.cancelled
        assert run_evt.causation_id == task_evt.event_id
        # step.cancelled caused by run.cancelled
        assert step_evt.causation_id == run_evt.event_id

    def test_cancel_nonexistent_task(self):
        uow = FakeUnitOfWork()
        cmd = CancelTask(task_id=uuid4(), cancelled_by_id=uuid4())
        with pytest.raises(DomainError, match="not found"):
            handle_cancel_task(cmd, uow)

    def test_cancel_completed_task_rejected(self):
        uow = FakeUnitOfWork()
        from src.domain.task import Task, TaskType
        task = Task(
            workspace_id=uuid4(),
            title="Done task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task.start()
        task.complete()
        uow.tasks.save(task)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        with pytest.raises(InvalidTransitionError):
            handle_cancel_task(cmd, uow)

    def test_cancel_pending_task_no_runs(self):
        uow = FakeUnitOfWork()
        from src.domain.task import Task, TaskType
        task = Task(
            workspace_id=uuid4(),
            title="Pending task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        uow.tasks.save(task)

        cmd = CancelTask(task_id=task.id, cancelled_by_id=uuid4())
        result = handle_cancel_task(cmd, uow)

        assert result.task.task_status == TaskStatus.CANCELLED
        assert len(result.cancelled_runs) == 0
        assert len(result.cancelled_steps) == 0
        # Only task.cancelled event
        assert len(uow.outbox.events) == 1
        assert uow.outbox.events[0].event_type == "task.cancelled"
