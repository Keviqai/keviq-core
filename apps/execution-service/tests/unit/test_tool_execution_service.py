"""Unit tests for tool execution service."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.application.events import OutboxEvent
from src.application.ports import (
    BackendInfo,
    ExecResult,
    ExecutionAttemptRepository,
    OutboxWriter,
    SandboxBackend,
    SandboxRepository,
    ToolExecutionBackend,
    UnitOfWork,
)
from src.application.sandbox_service import provision_sandbox
from src.application.tool_execution_service import execute_tool, get_execution
from src.domain.contracts import (
    SandboxProvisionRequest,
    ToolExecutionRequest,
    ToolExecutionStatus,
)
from src.domain.errors import DomainError, SandboxBusyError
from src.domain.sandbox import Sandbox, SandboxStatus


# ── Fakes ────────────────────────────────────────────────────


class FakeSandboxRepository(SandboxRepository):
    def __init__(self):
        self._store: dict[str, Sandbox] = {}

    def save(self, sandbox: Sandbox) -> None:
        self._store[str(sandbox.id)] = sandbox

    def get_by_id(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        return self._store.get(str(sandbox_id))

    def get_by_invocation(self, agent_invocation_id: uuid.UUID) -> Sandbox | None:
        for s in self._store.values():
            if s.agent_invocation_id == agent_invocation_id:
                return s
        return None

    def list_active(self, limit: int = 50) -> list[Sandbox]:
        return [
            s for s in self._store.values()
            if s.sandbox_status not in (SandboxStatus.TERMINATED, SandboxStatus.FAILED)
        ][:limit]

    def get_by_id_for_update(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        return self.get_by_id(sandbox_id)

    def claim_for_execution(self, sandbox_id: uuid.UUID) -> Sandbox:
        sandbox = self.get_by_id(sandbox_id)
        if sandbox is None:
            raise DomainError(f"Sandbox {sandbox_id} not found")
        if sandbox.sandbox_status not in (SandboxStatus.READY, SandboxStatus.IDLE):
            raise SandboxBusyError(str(sandbox_id), sandbox.sandbox_status.value)
        sandbox.mark_executing()
        self.save(sandbox)
        return sandbox

    def list_stuck(self, *, stuck_before, statuses: list[str]) -> list[Sandbox]:
        return [
            s for s in self._store.values()
            if s.sandbox_status.value in statuses and s.updated_at < stuck_before
        ]


class FakeExecutionAttemptRepository(ExecutionAttemptRepository):
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}
        self._by_sandbox_index: dict[str, dict[str, Any]] = {}

    def save(self, attempt_data: dict[str, Any]) -> None:
        attempt_id = attempt_data["id"]
        # Merge with existing data (upsert behavior)
        existing = self._store.get(attempt_id, {})
        existing.update(attempt_data)
        self._store[attempt_id] = existing
        key = f"{attempt_data['sandbox_id']}:{attempt_data['attempt_index']}"
        self._by_sandbox_index[key] = existing

    def get(self, attempt_id: uuid.UUID) -> dict[str, Any] | None:
        return self._store.get(str(attempt_id))

    def get_by_sandbox_and_index(
        self, sandbox_id: uuid.UUID, attempt_index: int,
    ) -> dict[str, Any] | None:
        key = f"{sandbox_id}:{attempt_index}"
        return self._by_sandbox_index.get(key)


class FakeOutboxWriter(OutboxWriter):
    def __init__(self):
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.sandboxes = FakeSandboxRepository()
        self.attempts = FakeExecutionAttemptRepository()
        self.outbox = FakeOutboxWriter()
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeBackend(SandboxBackend):
    def __init__(self, *, should_fail: bool = False):
        self._should_fail = should_fail
        self.provisioned: list[uuid.UUID] = []
        self.terminated: list[uuid.UUID] = []

    def provision(
        self,
        *,
        sandbox_id: uuid.UUID,
        sandbox_type: str,
        resource_limits: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> BackendInfo:
        if self._should_fail:
            raise RuntimeError("Docker pull failed")
        self.provisioned.append(sandbox_id)
        return BackendInfo(container_id="fake-container-id")

    def terminate(self, sandbox_id: uuid.UUID) -> None:
        self.terminated.append(sandbox_id)

    def is_alive(self, sandbox_id: uuid.UUID) -> bool:
        return sandbox_id in self.provisioned and sandbox_id not in self.terminated


class FakeExecutionBackend(ToolExecutionBackend):
    def __init__(
        self,
        *,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        should_fail: bool = False,
        should_timeout: bool = False,
    ):
        self._exit_code = exit_code
        self._stdout = stdout
        self._stderr = stderr
        self._should_fail = should_fail
        self._should_timeout = should_timeout
        self.executed: list[dict] = []

    def exec_in_sandbox(
        self,
        *,
        sandbox_id: uuid.UUID,
        command: list[str],
        timeout_s: int = 30,
    ) -> ExecResult:
        if self._should_timeout:
            raise TimeoutError("execution timed out")
        if self._should_fail:
            raise RuntimeError("container exec failed")
        self.executed.append({
            "sandbox_id": sandbox_id,
            "command": command,
            "timeout_s": timeout_s,
        })
        return ExecResult(
            exit_code=self._exit_code,
            stdout=self._stdout,
            stderr=self._stderr,
        )


def _make_provision_request(**overrides) -> SandboxProvisionRequest:
    defaults = {
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "step_id": uuid.uuid4(),
        "agent_invocation_id": uuid.uuid4(),
        "sandbox_type": "container",
    }
    defaults.update(overrides)
    return SandboxProvisionRequest(**defaults)


def _provision_sandbox(uow, backend):
    """Helper: provision a sandbox and return its ID."""
    req = _make_provision_request()
    result = provision_sandbox(req, uow, backend)
    return result.sandbox_id


# ── Execute Tool Tests ──────────────────────────────────────


class TestExecuteTool:
    def test_execute_success(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(
            exit_code=0, stdout="hello world\n", stderr="",
        )
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="python.run_script",
            tool_input={"code": "print('hello world')"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert result.success
        assert result.status == ToolExecutionStatus.COMPLETED
        assert result.stdout == "hello world\n"
        assert result.exit_code == 0

    def test_execute_captures_stderr(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(
            exit_code=0, stdout="", stderr="warning: something\n",
        )
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert result.success
        assert result.stderr == "warning: something\n"

    def test_execute_nonzero_exit_is_failed(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(
            exit_code=1, stdout="", stderr="error\n",
        )
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "false"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert not result.success
        assert result.status == ToolExecutionStatus.FAILED
        assert result.exit_code == 1

    def test_execute_unknown_tool_raises(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend()
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="nonexistent.tool",
            tool_input={},
        )
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool(req, uow, exec_backend)

    def test_execute_sandbox_not_found(self):
        uow = FakeUnitOfWork()
        exec_backend = FakeExecutionBackend()

        req = ToolExecutionRequest(
            sandbox_id=uuid.uuid4(),
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        with pytest.raises(DomainError, match="not found"):
            execute_tool(req, uow, exec_backend)

    def test_execute_sandbox_not_active(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend()
        sandbox_id = _provision_sandbox(uow, backend)

        # Terminate the sandbox first
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        sandbox.mark_terminating()
        sandbox.mark_terminated()
        uow.sandboxes.save(sandbox)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        with pytest.raises(DomainError, match="busy|not available"):
            execute_tool(req, uow, exec_backend)

    def test_execute_wrong_sandbox_type(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend()
        # Provision a subprocess sandbox
        sandbox_id = _provision_sandbox(
            uow, backend,
        )
        # Manually change sandbox type to subprocess
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        from src.domain.sandbox import SandboxType
        sandbox.sandbox_type = SandboxType.SUBPROCESS
        uow.sandboxes.save(sandbox)

        # python.run_script only allows container type
        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="python.run_script",
            tool_input={"code": "print(1)"},
        )
        with pytest.raises(DomainError, match="not allowed"):
            execute_tool(req, uow, exec_backend)

    def test_execute_backend_failure(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(should_fail=True)
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert not result.success
        assert result.status == ToolExecutionStatus.FAILED
        assert result.error_code == "EXECUTION_ERROR"
        assert "container exec failed" in result.error_message

    def test_execute_timeout(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(should_timeout=True)
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "sleep 999"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert not result.success
        assert result.status == ToolExecutionStatus.TIMED_OUT
        assert result.error_code == "EXECUTION_TIMEOUT"

    def test_execute_transitions_sandbox_to_executing_then_idle(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(exit_code=0)
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        execute_tool(req, uow, exec_backend)

        # After execution, sandbox should be IDLE
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.IDLE

    def test_execute_failure_transitions_sandbox_back_to_idle(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(should_fail=True)
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        execute_tool(req, uow, exec_backend)

        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.IDLE

    def test_execute_emits_requested_and_succeeded_events(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(exit_code=0)
        sandbox_id = _provision_sandbox(uow, backend)

        # Clear provision events
        uow.outbox.events.clear()

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        execute_tool(req, uow, exec_backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.tool_execution.requested" in event_types
        assert "sandbox.tool_execution.succeeded" in event_types

    def test_execute_failure_emits_failed_event(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(should_fail=True)
        sandbox_id = _provision_sandbox(uow, backend)

        uow.outbox.events.clear()

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo test"},
        )
        execute_tool(req, uow, exec_backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.tool_execution.requested" in event_types
        assert "sandbox.tool_execution.failed" in event_types

    def test_execute_persists_attempt_record(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(exit_code=0, stdout="ok\n")
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo ok"},
        )
        execute_tool(req, uow, exec_backend)

        attempt = uow.attempts.get_by_sandbox_and_index(sandbox_id, 0)
        assert attempt is not None
        assert attempt["tool_name"] == "shell.exec"
        assert attempt["status"] == "completed"
        assert attempt["stdout"] == "ok\n"
        assert attempt["exit_code"] == 0

    def test_execute_truncates_large_output(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        large_output = "x" * 2_000_000
        exec_backend = FakeExecutionBackend(exit_code=0, stdout=large_output)
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo lots"},
        )
        result = execute_tool(req, uow, exec_backend)

        assert result.truncated
        assert len(result.stdout) == 1_000_000

    def test_multiple_executions_on_same_sandbox(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(exit_code=0, stdout="ok\n")
        sandbox_id = _provision_sandbox(uow, backend)

        for i in range(3):
            req = ToolExecutionRequest(
                sandbox_id=sandbox_id,
                attempt_index=i,
                tool_name="shell.exec",
                tool_input={"code": f"echo {i}"},
            )
            result = execute_tool(req, uow, exec_backend)
            assert result.success

        # Sandbox should be IDLE after all executions
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.IDLE


# ── Get Execution Tests ─────────────────────────────────────


class TestGetExecution:
    def test_get_existing_execution(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        exec_backend = FakeExecutionBackend(exit_code=0, stdout="result\n")
        sandbox_id = _provision_sandbox(uow, backend)

        req = ToolExecutionRequest(
            sandbox_id=sandbox_id,
            attempt_index=0,
            tool_name="shell.exec",
            tool_input={"code": "echo result"},
        )
        execute_tool(req, uow, exec_backend)

        # Find the execution ID from the attempt store
        attempt = uow.attempts.get_by_sandbox_and_index(sandbox_id, 0)
        eid = uuid.UUID(attempt["id"])

        result = get_execution(eid, uow)
        assert result["tool_name"] == "shell.exec"
        assert result["status"] == "completed"

    def test_get_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_execution(uuid.uuid4(), uow)
