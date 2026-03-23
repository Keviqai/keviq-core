"""Unit tests for orchestrator ↔ execution-service wiring.

Tests sandbox provisioning/termination lifecycle integration
with the execution loop, correlation ID propagation, and
error mapping for sandbox failures.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.application.execution_loop import run_real_execution
from src.application.ports import (
    ExecutionDispatchPort,
    ExecutionServicePort,
    RuntimeExecutionResult,
    SandboxInfo,
    ToolExecutionResult,
)
from src.domain.run import RunStatus
from src.domain.step import StepStatus
from src.domain.task import Task, TaskStatus

from .fake_uow import FakeUnitOfWork


# ── Fakes ────────────────────────────────────────────────────


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
            "instruction": instruction,
            "input_payload": input_payload,
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


class FakeExecutionService(ExecutionServicePort):
    """Test double for ExecutionServicePort."""

    def __init__(
        self,
        *,
        provision_fail: bool = False,
        terminate_fail: bool = False,
    ):
        self._provision_fail = provision_fail
        self._terminate_fail = terminate_fail
        self._sandbox_id = uuid4()
        self.provisioned: list[dict] = []
        self.terminated: list[dict] = []
        self.tool_executions: list[dict] = []

    @property
    def sandbox_id(self) -> UUID:
        return self._sandbox_id

    def provision_sandbox(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        sandbox_type: str = "container",
    ) -> SandboxInfo:
        if self._provision_fail:
            raise RuntimeError("Docker pull failed")
        self.provisioned.append({
            "workspace_id": workspace_id,
            "task_id": task_id,
            "run_id": run_id,
            "step_id": step_id,
            "agent_invocation_id": agent_invocation_id,
            "sandbox_type": sandbox_type,
        })
        return SandboxInfo(
            sandbox_id=self._sandbox_id,
            sandbox_status="ready",
        )

    def execute_tool(
        self,
        *,
        sandbox_id: UUID,
        tool_name: str,
        tool_input: dict[str, Any],
        attempt_index: int = 0,
        timeout_ms: int = 30_000,
        correlation_id: UUID | None = None,
    ) -> ToolExecutionResult:
        self.tool_executions.append({
            "sandbox_id": sandbox_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        })
        return ToolExecutionResult(
            execution_id=uuid4(),
            sandbox_id=sandbox_id,
            status="completed",
            stdout="ok\n",
            exit_code=0,
        )

    def get_execution(self, execution_id: UUID) -> dict[str, Any]:
        return {"id": str(execution_id), "status": "completed"}

    def terminate_sandbox(
        self,
        sandbox_id: UUID,
        *,
        reason: str = "completed",
    ) -> bool:
        if self._terminate_fail:
            raise RuntimeError("terminate failed")
        self.terminated.append({
            "sandbox_id": sandbox_id,
            "reason": reason,
        })
        return True


# ── Helpers ──────────────────────────────────────────────────


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


# ── Sandbox provisioning ────────────────────────────────────


class TestSandboxProvisioning:
    def test_sandbox_provisioned_before_dispatch(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.provisioned) == 1
        prov = exec_svc.provisioned[0]
        assert prov["task_id"] == task.id
        assert prov["workspace_id"] == task.workspace_id
        assert prov["sandbox_type"] == "container"

    def test_sandbox_id_passed_to_dispatcher(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(dispatcher.calls) == 1
        payload = dispatcher.calls[0]["input_payload"]
        assert payload["sandbox_id"] == str(exec_svc.sandbox_id)

    def test_sandbox_terminated_after_success(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.terminated) == 1
        assert exec_svc.terminated[0]["sandbox_id"] == exec_svc.sandbox_id
        assert exec_svc.terminated[0]["reason"] == "completed"

    def test_sandbox_terminated_after_failure(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="RUNTIME_ERROR",
            error_message="Something broke",
        ))
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        # Sandbox should still be terminated even on failure
        assert len(exec_svc.terminated) == 1

    def test_sandbox_terminated_after_timeout(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Timed out",
        ))
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.terminated) == 1

    def test_task_completes_with_sandbox(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert task.task_status == TaskStatus.COMPLETED


# ── Sandbox provision failure ───────────────────────────────


class TestSandboxProvisionFailure:
    def test_provision_failure_maps_to_task_failed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService(provision_fail=True)

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert task.task_status == TaskStatus.FAILED

    def test_provision_failure_does_not_dispatch(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService(provision_fail=True)

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(dispatcher.calls) == 0

    def test_provision_failure_step_has_error(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService(provision_fail=True)

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        run = uow.runs.get_latest_by_task(task.id)
        steps = uow.steps.list_by_run(run.id)
        assert len(steps) == 1
        step = steps[0]
        assert step.step_status == StepStatus.FAILED
        assert step.error_detail["error_code"] == "SANDBOX_PROVISION_FAILED"

    def test_provision_failure_no_sandbox_to_terminate(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService(provision_fail=True)

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        # No sandbox was created, so nothing to terminate
        assert len(exec_svc.terminated) == 0


# ── Terminate failure resilience ────────────────────────────


class TestTerminateFailureResilience:
    def test_terminate_failure_does_not_break_task_completion(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService(terminate_fail=True)

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        # Task should still complete even if sandbox termination fails
        assert task.task_status == TaskStatus.COMPLETED


# ── Without execution service (backward compat) ────────────


class TestWithoutExecutionService:
    def test_works_without_execution_service(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        assert task.task_status == TaskStatus.COMPLETED

    def test_no_sandbox_id_in_payload_without_exec_service(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher)

        payload = dispatcher.calls[0]["input_payload"]
        assert "sandbox_id" not in payload

    def test_none_execution_service_skips_sandbox(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()

        run_real_execution(task.id, uow, dispatcher, execution_service=None)

        assert task.task_status == TaskStatus.COMPLETED


# ── Correlation ID propagation ──────────────────────────────


class TestCorrelationPropagation:
    def test_correlation_id_shared_with_sandbox(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        # All outbox events should share the same correlation_id
        correlation_ids = {e.correlation_id for e in uow.outbox.events}
        assert len(correlation_ids) == 1

        # The dispatch call should use the same correlation_id
        dispatch_corr = dispatcher.calls[0]["correlation_id"]
        assert dispatch_corr in correlation_ids

    def test_event_sequence_with_sandbox(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        event_types = [e.event_type for e in uow.outbox.events]
        # Same event sequence as without sandbox — sandbox lifecycle
        # is transparent to the orchestrator event model
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


# ── Termination reason semantics ─────────────────────────────


class TestTerminationReasonSemantics:
    def test_success_terminates_with_completed(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher()
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.terminated) == 1
        assert exec_svc.terminated[0]["reason"] == "completed"

    def test_failure_terminates_with_error(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="failed",
            error_code="RUNTIME_ERROR",
            error_message="Something broke",
        ))
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.terminated) == 1
        assert exec_svc.terminated[0]["reason"] == "error"

    def test_timeout_terminates_with_timeout(self):
        uow = FakeUnitOfWork()
        task = make_pending_task(uow)
        dispatcher = FakeDispatcher(result=RuntimeExecutionResult(
            agent_invocation_id=uuid4(),
            status="timed_out",
            error_code="TIMEOUT",
            error_message="Timed out",
        ))
        exec_svc = FakeExecutionService()

        run_real_execution(task.id, uow, dispatcher, exec_svc)

        assert len(exec_svc.terminated) == 1
        assert exec_svc.terminated[0]["reason"] == "timeout"
