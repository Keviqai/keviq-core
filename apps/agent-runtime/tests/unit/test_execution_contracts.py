"""Contract tests for ExecutionRequest/Result/Failure.

Validates:
- Required fields are present and typed
- Contracts are transport-agnostic (no HTTP/framework concerns)
- Forbidden fields (task_status, run_status, step_status) are absent
- Serialization roundtrip via dataclasses.asdict
"""

import pytest
from dataclasses import asdict, fields
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.execution_contracts import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionFailure,
    ExecutionStatus,
    ModelProfile,
    UsageMetadata,
)


# ── Factories ────────────────────────────────────────────────────

def make_execution_request(**overrides) -> ExecutionRequest:
    defaults = dict(
        agent_invocation_id=uuid4(),
        workspace_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        step_id=uuid4(),
        correlation_id=uuid4(),
        agent_id="reasoning-v1",
        model_profile=ModelProfile(model_alias="claude-sonnet"),
        instruction="Summarize the document.",
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


# ── ExecutionRequest ─────────────────────────────────────────────

class TestExecutionRequest:
    def test_required_fields_present(self):
        req = ExecutionRequest(
            agent_invocation_id=uuid4(),
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            correlation_id=uuid4(),
            agent_id="reasoning-v1",
            model_profile=ModelProfile(model_alias="claude-sonnet"),
            instruction="Summarize the document.",
        )
        assert req.agent_invocation_id is not None
        assert req.workspace_id is not None
        assert req.correlation_id is not None
        assert req.agent_id == "reasoning-v1"
        assert req.instruction == "Summarize the document."

    def test_default_timeout(self):
        req = make_execution_request()
        assert req.timeout_ms == 30_000

    def test_custom_timeout(self):
        req = make_execution_request(timeout_ms=60_000)
        assert req.timeout_ms == 60_000

    def test_input_payload_default_empty(self):
        req = make_execution_request()
        assert req.input_payload == {}

    def test_serializable_via_asdict(self):
        req = make_execution_request()
        d = asdict(req)
        assert "agent_invocation_id" in d
        assert "model_profile" in d
        assert d["model_profile"]["model_alias"] == "claude-sonnet"

    def test_is_frozen(self):
        req = make_execution_request()
        with pytest.raises(AttributeError):
            req.instruction = "changed"

    def test_no_forbidden_fields(self):
        """Contracts must NOT contain task_status, run_status, step_status."""
        field_names = {f.name for f in fields(ExecutionRequest)}
        forbidden = {"task_status", "run_status", "step_status"}
        assert field_names.isdisjoint(forbidden), f"Found forbidden fields: {field_names & forbidden}"

    def test_causation_id_optional(self):
        req = make_execution_request()
        assert req.causation_id is None


# ── ExecutionResult ──────────────────────────────────────────────

class TestExecutionResult:
    def test_required_fields(self):
        result = ExecutionResult(
            agent_invocation_id=uuid4(),
            status=ExecutionStatus.COMPLETED,
            output_payload={"summary": "done"},
            usage=UsageMetadata(prompt_tokens=100, completion_tokens=50),
        )
        assert result.agent_invocation_id is not None
        assert result.status == ExecutionStatus.COMPLETED
        assert result.output_payload == {"summary": "done"}

    def test_default_status_is_completed(self):
        result = ExecutionResult(agent_invocation_id=uuid4())
        assert result.status == ExecutionStatus.COMPLETED

    def test_usage_metadata_defaults(self):
        usage = UsageMetadata()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_cost_usd == Decimal("0")
        assert usage.model_concrete is None

    def test_serializable_via_asdict(self):
        result = ExecutionResult(
            agent_invocation_id=uuid4(),
            usage=UsageMetadata(prompt_tokens=100, completion_tokens=50, total_cost_usd=Decimal("0.003")),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        d = asdict(result)
        assert d["usage"]["prompt_tokens"] == 100

    def test_is_frozen(self):
        result = ExecutionResult(agent_invocation_id=uuid4())
        with pytest.raises(AttributeError):
            result.status = ExecutionStatus.FAILED

    def test_no_forbidden_fields(self):
        field_names = {f.name for f in fields(ExecutionResult)}
        forbidden = {"task_status", "run_status", "step_status"}
        assert field_names.isdisjoint(forbidden)


# ── ExecutionFailure ─────────────────────────────────────────────

class TestExecutionFailure:
    def test_required_fields(self):
        failure = ExecutionFailure(
            agent_invocation_id=uuid4(),
            status=ExecutionStatus.FAILED,
            error_code="PROVIDER_TIMEOUT",
            error_message="Model provider did not respond in 30s",
        )
        assert failure.error_code == "PROVIDER_TIMEOUT"
        assert failure.retryable is False

    def test_default_status_is_failed(self):
        failure = ExecutionFailure(agent_invocation_id=uuid4())
        assert failure.status == ExecutionStatus.FAILED

    def test_retryable_flag(self):
        failure = ExecutionFailure(
            agent_invocation_id=uuid4(),
            error_code="RATE_LIMITED",
            retryable=True,
        )
        assert failure.retryable is True

    def test_timed_out_status(self):
        failure = ExecutionFailure(
            agent_invocation_id=uuid4(),
            status=ExecutionStatus.TIMED_OUT,
            error_code="TIMEOUT",
        )
        assert failure.status == ExecutionStatus.TIMED_OUT

    def test_serializable_via_asdict(self):
        failure = ExecutionFailure(
            agent_invocation_id=uuid4(),
            error_code="ERR",
            error_message="something went wrong",
            failed_at=datetime.now(timezone.utc),
        )
        d = asdict(failure)
        assert d["error_code"] == "ERR"

    def test_is_frozen(self):
        failure = ExecutionFailure(agent_invocation_id=uuid4())
        with pytest.raises(AttributeError):
            failure.error_code = "changed"

    def test_no_forbidden_fields(self):
        field_names = {f.name for f in fields(ExecutionFailure)}
        forbidden = {"task_status", "run_status", "step_status"}
        assert field_names.isdisjoint(forbidden)


# ── ModelProfile ─────────────────────────────────────────────────

class TestModelProfile:
    def test_minimal(self):
        mp = ModelProfile(model_alias="claude-sonnet")
        assert mp.model_alias == "claude-sonnet"
        assert mp.max_tokens is None
        assert mp.temperature is None

    def test_with_params(self):
        mp = ModelProfile(model_alias="claude-opus", max_tokens=4096, temperature=0.7)
        assert mp.max_tokens == 4096
        assert mp.temperature == 0.7


# ── Transport-agnostic check ────────────────────────────────────

class TestTransportAgnostic:
    """Verify contracts module has no framework/transport imports."""

    def test_no_framework_imports(self):
        from pathlib import Path
        import src.domain.execution_contracts as mod
        source = Path(mod.__file__).read_text(encoding="utf-8")
        forbidden_imports = [
            "fastapi", "httpx", "sqlalchemy", "uvicorn",
            "starlette", "pydantic",
        ]
        for pkg in forbidden_imports:
            assert f"import {pkg}" not in source, f"Contract module imports {pkg}"
            assert f"from {pkg}" not in source, f"Contract module imports from {pkg}"
