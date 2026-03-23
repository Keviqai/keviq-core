"""Unit tests for the simulated execution loop.

Uses FakeUnitOfWork — no database needed.
Verifies the loop uses domain methods and produces correct events.
"""

import pytest
from uuid import uuid4

from src.application.commands import SubmitTask
from src.application.handlers import handle_submit_task
from src.application.simulated_loop import run_simulated_execution
from src.domain.run import RunStatus
from src.domain.step import StepStatus
from src.domain.task import TaskStatus

from .fake_uow import FakeUnitOfWork


class TestSimulatedLoop:
    def _submit_task(self, uow: FakeUnitOfWork):
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Simulated task",
            task_type="coding",
            created_by_id=uuid4(),
        )
        return handle_submit_task(cmd, uow)

    def test_happy_path_reaches_completed(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        task_id = result.task.id

        # Reset outbox to isolate loop events
        uow.outbox.events.clear()
        uow.committed = False

        run_simulated_execution(task_id, uow)

        # Task should be completed
        task = uow.tasks.get_by_id(task_id)
        assert task.task_status == TaskStatus.COMPLETED

        # Should have exactly one run
        runs = [r for r in uow.runs._store.values() if r.task_id == task_id]
        assert len(runs) == 1
        assert runs[0].run_status == RunStatus.COMPLETED
        assert runs[0].duration_ms is not None
        assert runs[0].duration_ms >= 0

        # Should have exactly one step
        steps = list(uow.steps._store.values())
        assert len(steps) == 1
        assert steps[0].step_status == StepStatus.COMPLETED
        assert steps[0].output_snapshot is not None

        assert uow.committed is True

    def test_produces_correct_event_sequence(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        task_id = result.task.id

        # Clear submit event
        uow.outbox.events.clear()

        run_simulated_execution(task_id, uow)

        event_types = [e.event_type for e in uow.outbox.events]
        expected = [
            "task.started",
            "run.queued",
            "run.started",
            "step.started",
            "step.completed",
            "run.completing",
            "run.completed",
            "task.completed",
        ]
        assert event_types == expected

    def test_correlation_id_shared_across_all_events(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        uow.outbox.events.clear()

        run_simulated_execution(result.task.id, uow)

        correlation_ids = {e.correlation_id for e in uow.outbox.events}
        assert len(correlation_ids) == 1, "All events in one run share correlation_id"

    def test_causation_chain_is_linked(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        uow.outbox.events.clear()

        run_simulated_execution(result.task.id, uow)

        events = uow.outbox.events
        # task.started has no causation (entry point)
        assert events[0].event_type == "task.started"
        assert events[0].causation_id is None

        # run.queued caused by task.started
        assert events[1].event_type == "run.queued"
        assert events[1].causation_id == events[0].event_id

        # run.started caused by run.queued
        assert events[2].event_type == "run.started"
        assert events[2].causation_id == events[1].event_id

        # step.started caused by run.started
        assert events[3].event_type == "step.started"
        assert events[3].causation_id == events[2].event_id

        # step.completed caused by step.started
        assert events[4].event_type == "step.completed"
        assert events[4].causation_id == events[3].event_id

        # run.completing caused by step.completed
        assert events[5].event_type == "run.completing"
        assert events[5].causation_id == events[4].event_id

    def test_no_direct_status_set(self):
        """Simulated loop must use domain transition methods."""
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)

        run_simulated_execution(result.task.id, uow)

        # If direct status set were used, domain invariants wouldn't hold
        task = uow.tasks.get_by_id(result.task.id)
        assert task.task_status == TaskStatus.COMPLETED

        runs = list(uow.runs._store.values())
        assert all(r.completed_at is not None for r in runs)

        steps = list(uow.steps._store.values())
        assert all(s.completed_at is not None for s in steps)
        assert all(s.started_at is not None for s in steps)

    def test_task_not_found_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(ValueError, match="not found"):
            run_simulated_execution(uuid4(), uow)

    def test_non_pending_task_raises(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        # Run execution once
        run_simulated_execution(result.task.id, uow)
        # Try again — task is now completed
        with pytest.raises(ValueError, match="completed.*expected pending"):
            run_simulated_execution(result.task.id, uow)

    def test_events_have_workspace_and_task_ids(self):
        uow = FakeUnitOfWork()
        result = self._submit_task(uow)
        ws_id = result.task.workspace_id
        task_id = result.task.id
        uow.outbox.events.clear()

        run_simulated_execution(task_id, uow)

        for evt in uow.outbox.events:
            assert evt.workspace_id == ws_id
            assert evt.task_id == task_id
