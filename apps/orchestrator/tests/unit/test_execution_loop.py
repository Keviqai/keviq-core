"""Unit tests for real execution loop.

Tests orchestrator dispatch to agent-runtime, result mapping,
failure/timeout paths, and event emission.
"""

from __future__ import annotations

import pytest
from typing import Any
from uuid import UUID, uuid4

from src.application.execution_loop import run_real_execution
from src.application.ports import ExecutionDispatchPort, RuntimeExecutionResult
from src.domain.run import RunStatus
from src.domain.step import StepStatus
from src.domain.task import Task, TaskStatus

from .fake_uow import FakeUnitOfWork


# ── Fake Dispatcher ─────────────────────────────────────────────

class FakeDispatcher(ExecutionDispatchPort):
    """Test double for ExecutionDispatchPort."""

    def __init__(self, result: RuntimeExecutionResult | None = None):
        self._result = result
        self.calls: list[dict] = []

    def dispatch(
        self,
        *,
        agent_invocation_id: UUID,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        correlation_id: UUID,
        agent_id: str,
        model_alias: str,
        instruction: str,
        input_payload: dict[str, Any] | None = None,
        timeout_ms: int = 30_000,
    ) -> RuntimeExecutionResult:
        self.calls.append({
            "agent_invocation_id": agent_invocation_id,
            "workspace_id": workspace_id,
            "task_id": task_id,
            "run_id": run_id,
            "step_id": step_id,
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "model_alias": model_alias,
            "instruction": instruction,
        })
        if self._result is not None:
            return self._result
        return RuntimeExecutionResult(
            agent_invocation_id=agent_invocation_id,
            status="completed",
            output_text="Hello from model",
            prompt_tokens=10,
            completion_tokens=5,
        )


# ── Helpers ──────────────────────────────────────────────────────

def make_pending_task(uow: FakeUnitOfWork, **overrides) -> Task:
    """Create a pending task in the fake UoW."""
    defaults = dict(
        workspace_id=uuid4(),
        title="Test task",
        task_type="general",
        created_by_id=uuid4(),
    )
    defaults.update(overrides)
    task = Task(**defaults)
    task.submit()
    uow.tasks.save(task)
    return task


# ── Happy path ───────────────────────────────────────────────────

class TestHappyPath:
    def test_task_reaches_completed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        assert task.task_status == TaskStatus.COMPLETED

    def test_run_reaches_completed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        assert run is not None
        assert run.run_status == RunStatus.COMPLETED
        assert run.completed_at is not None
        assert run.duration_ms is not None

    def test_step_reaches_completed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        steps = uow.steps.list_by_run(run.id)
        assert len(steps) == 1
        step = steps[0]
        assert step.step_status == StepStatus.COMPLETED
        assert step.output_snapshot is not None
        assert step.output_snapshot["output_text"] == "Hello from model"

    def test_dispatcher_called_with_correct_params(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow, title="Do something important")
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        assert len(dispatcher.calls) == 1
        call = dispatcher.calls[0]
        assert call["task_id"] == task.id
        assert call["workspace_id"] == task.workspace_id
        assert call["instruction"] == "Do something important"

    def test_correct_event_sequence(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        event_types = [e.event_type for e in uow.outbox.events]
        assert event_types == [
            "task.started",
            "run.queued",
            "run.started",
            "step.started",
            "step.completed",
            "run.completing",
            "run.completed",
            "task.completed",
        ]

    def test_correlation_id_shared(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        correlation_ids = {e.correlation_id for e in uow.outbox.events}
        assert len(correlation_ids) == 1, "All events must share one correlation_id"

    def test_causation_chain_linked(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        events = uow.outbox.events
        # First event (task.started) has no causation_id
        assert events[0].causation_id is None
        # Each subsequent event references a previous event
        for i in range(1, len(events)):
            assert events[i].causation_id is not None


# ── Failure path ─────────────────────────────────────────────────

class TestFailurePath:
    def test_task_reaches_failed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="GATEWAY_ERROR",
            error_message="Provider error",
            retryable=True,
        ))

        run_real_execution(task.id, uow, dispatcher)

        assert task.task_status == TaskStatus.FAILED

    def test_run_reaches_failed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="GATEWAY_ERROR",
            error_message="Provider error",
        ))

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        assert run.run_status == RunStatus.FAILED
        assert run.error_summary is not None
        assert "GATEWAY_ERROR" in run.error_summary

    def test_step_reaches_failed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="GATEWAY_ERROR",
            error_message="Provider error",
        ))

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        steps = uow.steps.list_by_run(run.id)
        step = steps[0]
        assert step.step_status == StepStatus.FAILED
        assert step.error_detail is not None
        assert step.error_detail["error_code"] == "GATEWAY_ERROR"

    def test_failure_event_sequence(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="HTTP_500",
            error_message="Internal server error",
        ))

        run_real_execution(task.id, uow, dispatcher)

        event_types = [e.event_type for e in uow.outbox.events]
        assert event_types == [
            "task.started",
            "run.queued",
            "run.started",
            "step.started",
            "step.failed",
            "run.failed",
            "task.failed",
        ]


# ── Timeout path ─────────────────────────────────────────────────

class TestTimeoutPath:
    def test_task_reaches_failed_on_timeout(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Execution timed out",
        ))

        run_real_execution(task.id, uow, dispatcher)

        assert task.task_status == TaskStatus.FAILED

    def test_run_reaches_timed_out(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Execution timed out",
        ))

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        assert run.run_status == RunStatus.TIMED_OUT

    def test_step_failed_on_timeout(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Execution timed out",
        ))

        run_real_execution(task.id, uow, dispatcher)

        run = uow.runs.get_latest_by_task(task.id)
        steps = uow.steps.list_by_run(run.id)
        step = steps[0]
        assert step.step_status == StepStatus.FAILED
        assert step.error_detail["error_code"] == "TIMEOUT"

    def test_timeout_event_sequence(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Execution timed out",
        ))

        run_real_execution(task.id, uow, dispatcher)

        event_types = [e.event_type for e in uow.outbox.events]
        assert event_types == [
            "task.started",
            "run.queued",
            "run.started",
            "step.started",
            "step.failed",
            "run.timed_out",
            "task.failed",
        ]


# ── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    def test_task_not_found_raises(self):
        uow = FakeUnitOfWork()
        dispatcher = FakeDispatcher()

        with pytest.raises(ValueError, match="not found"):
            run_real_execution(uuid4(), uow, dispatcher)

    def test_task_not_pending_raises(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        task.start()  # now running, not pending
        uow.tasks.save(task)
        dispatcher = FakeDispatcher()

        with pytest.raises(ValueError, match="expected pending"):
            run_real_execution(task.id, uow, dispatcher)

    def test_invocation_id_passed_to_dispatcher(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        call = dispatcher.calls[0]
        assert call["agent_invocation_id"] is not None
        # Verify invocation ID is recorded in step input_snapshot
        run = uow.runs.get_latest_by_task(task.id)
        steps = uow.steps.list_by_run(run.id)
        assert "agent_invocation_id" in steps[0].input_snapshot

    def test_connection_error_maps_to_failure(self):
        """Dispatcher returning failed status maps correctly."""
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="CONNECTION_ERROR",
            error_message="Cannot reach agent-runtime",
        ))

        run_real_execution(task.id, uow, dispatcher)

        assert task.task_status == TaskStatus.FAILED
        run = uow.runs.get_latest_by_task(task.id)
        assert run.run_status == RunStatus.FAILED
