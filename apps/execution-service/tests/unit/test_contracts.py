"""Unit tests for execution contracts serialization."""

from __future__ import annotations

import uuid

import pytest

from src.domain.contracts import (
    SandboxProvisionRequest,
    SandboxProvisionResult,
    SandboxTerminationRequest,
    SandboxTerminationResult,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)


# ── SandboxProvisionRequest ──────────────────────────────────


class TestSandboxProvisionRequest:
    def test_roundtrip(self):
        req = SandboxProvisionRequest(
            workspace_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            step_id=uuid.uuid4(),
            agent_invocation_id=uuid.uuid4(),
            sandbox_type="container",
            policy_snapshot={"max_cpu": "1"},
            resource_limits={"memory_mb": 512},
            timeout_ms=60_000,
        )
        d = req.to_dict()
        restored = SandboxProvisionRequest.from_dict(d)
        assert restored.workspace_id == req.workspace_id
        assert restored.sandbox_type == "container"
        assert restored.timeout_ms == 60_000
        assert restored.policy_snapshot == {"max_cpu": "1"}

    def test_defaults(self):
        req = SandboxProvisionRequest(
            workspace_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            step_id=uuid.uuid4(),
            agent_invocation_id=uuid.uuid4(),
            sandbox_type="subprocess",
        )
        assert req.timeout_ms == 300_000
        assert req.policy_snapshot == {}
        assert req.resource_limits == {}

    def test_all_uuid_fields_serialized_as_strings(self):
        req = SandboxProvisionRequest(
            workspace_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            step_id=uuid.uuid4(),
            agent_invocation_id=uuid.uuid4(),
            sandbox_type="container",
        )
        d = req.to_dict()
        for field in ["workspace_id", "task_id", "run_id", "step_id",
                       "agent_invocation_id"]:
            assert isinstance(d[field], str)

    def test_from_dict_missing_optional_fields(self):
        d = {
            "workspace_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "run_id": str(uuid.uuid4()),
            "step_id": str(uuid.uuid4()),
            "agent_invocation_id": str(uuid.uuid4()),
            "sandbox_type": "container",
        }
        req = SandboxProvisionRequest.from_dict(d)
        assert req.timeout_ms == 300_000
        assert req.policy_snapshot == {}

    def test_frozen(self):
        req = SandboxProvisionRequest(
            workspace_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            step_id=uuid.uuid4(),
            agent_invocation_id=uuid.uuid4(),
            sandbox_type="container",
        )
        with pytest.raises(AttributeError):
            req.sandbox_type = "subprocess"


# ── SandboxProvisionResult ───────────────────────────────────


class TestSandboxProvisionResult:
    def test_success_result(self):
        r = SandboxProvisionResult(
            sandbox_id=uuid.uuid4(),
            status="ready",
        )
        assert r.success
        d = r.to_dict()
        assert "error_code" not in d

    def test_failure_result(self):
        r = SandboxProvisionResult(
            sandbox_id=uuid.uuid4(),
            status="failed",
            error_code="PROVISION_ERROR",
            error_message="Docker pull failed",
        )
        assert not r.success
        d = r.to_dict()
        assert d["error_code"] == "PROVISION_ERROR"

    def test_roundtrip(self):
        r = SandboxProvisionResult(
            sandbox_id=uuid.uuid4(),
            status="ready",
        )
        restored = SandboxProvisionResult.from_dict(r.to_dict())
        assert restored.sandbox_id == r.sandbox_id
        assert restored.status == "ready"


# ── ToolExecutionRequest ─────────────────────────────────────


class TestToolExecutionRequest:
    def test_roundtrip(self):
        req = ToolExecutionRequest(
            sandbox_id=uuid.uuid4(),
            attempt_index=1,
            tool_name="bash",
            tool_input={"command": "ls -la"},
            timeout_ms=10_000,
        )
        d = req.to_dict()
        restored = ToolExecutionRequest.from_dict(d)
        assert restored.sandbox_id == req.sandbox_id
        assert restored.attempt_index == 1
        assert restored.tool_name == "bash"
        assert restored.tool_input == {"command": "ls -la"}
        assert restored.timeout_ms == 10_000

    def test_defaults(self):
        req = ToolExecutionRequest(
            sandbox_id=uuid.uuid4(),
            attempt_index=0,
            tool_name="read_file",
        )
        assert req.timeout_ms == 30_000
        assert req.tool_input == {}


# ── ToolExecutionResult ──────────────────────────────────────


class TestToolExecutionResult:
    def test_success_result(self):
        r = ToolExecutionResult(
            sandbox_id=uuid.uuid4(),
            attempt_index=1,
            status=ToolExecutionStatus.COMPLETED,
            stdout="hello world\n",
            stderr="",
            exit_code=0,
        )
        assert r.success
        d = r.to_dict()
        assert d["exit_code"] == 0
        assert d["stdout"] == "hello world\n"
        assert d["truncated"] is False

    def test_failure_result(self):
        r = ToolExecutionResult(
            sandbox_id=uuid.uuid4(),
            attempt_index=1,
            status=ToolExecutionStatus.FAILED,
            stderr="permission denied",
            exit_code=1,
            error_code="EXEC_FAILED",
            error_message="Non-zero exit",
        )
        assert not r.success
        d = r.to_dict()
        assert d["error_code"] == "EXEC_FAILED"

    def test_timeout_result(self):
        r = ToolExecutionResult(
            sandbox_id=uuid.uuid4(),
            attempt_index=1,
            status=ToolExecutionStatus.TIMED_OUT,
            stdout="partial output...",
            truncated=True,
        )
        assert not r.success
        assert r.status == ToolExecutionStatus.TIMED_OUT
        d = r.to_dict()
        assert d["truncated"] is True

    def test_roundtrip(self):
        r = ToolExecutionResult(
            sandbox_id=uuid.uuid4(),
            attempt_index=2,
            status=ToolExecutionStatus.COMPLETED,
            stdout="ok",
            exit_code=0,
        )
        restored = ToolExecutionResult.from_dict(r.to_dict())
        assert restored.sandbox_id == r.sandbox_id
        assert restored.attempt_index == 2
        assert restored.status == ToolExecutionStatus.COMPLETED

    def test_from_dict_missing_optional_fields(self):
        d = {
            "sandbox_id": str(uuid.uuid4()),
            "attempt_index": 0,
            "status": "completed",
        }
        r = ToolExecutionResult.from_dict(d)
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.exit_code is None
        assert r.truncated is False


# ── SandboxTerminationRequest ────────────────────────────────


class TestSandboxTerminationRequest:
    def test_roundtrip(self):
        req = SandboxTerminationRequest(
            sandbox_id=uuid.uuid4(),
            reason="timeout",
        )
        d = req.to_dict()
        restored = SandboxTerminationRequest.from_dict(d)
        assert restored.sandbox_id == req.sandbox_id
        assert restored.reason == "timeout"

    def test_default_reason(self):
        req = SandboxTerminationRequest(sandbox_id=uuid.uuid4())
        assert req.reason == "completed"


# ── SandboxTerminationResult ────────────────────────────────


class TestSandboxTerminationResult:
    def test_success(self):
        r = SandboxTerminationResult(
            sandbox_id=uuid.uuid4(),
            status="terminated",
        )
        assert r.success
        d = r.to_dict()
        assert "error_message" not in d

    def test_failure(self):
        r = SandboxTerminationResult(
            sandbox_id=uuid.uuid4(),
            status="failed",
            error_message="Container stuck",
        )
        assert not r.success
        d = r.to_dict()
        assert d["error_message"] == "Container stuck"

    def test_roundtrip(self):
        r = SandboxTerminationResult(
            sandbox_id=uuid.uuid4(),
            status="terminated",
        )
        restored = SandboxTerminationResult.from_dict(r.to_dict())
        assert restored.sandbox_id == r.sandbox_id
        assert restored.status == "terminated"
