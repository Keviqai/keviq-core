"""Unit tests for ExecuteInvocationHandler.

Tests lifecycle transitions, model-gateway call, error mapping, event emission,
and best-effort artifact creation using in-memory fakes — no real HTTP, DB, or outbox.
"""

import hashlib
import os

# H1-S1: Disable tool approval gate for pre-O5 tests
os.environ['TOOL_APPROVAL_MODE'] = 'none'

import pytest
from typing import Any
from uuid import uuid4, UUID

from src.application.execution_handler import ExecuteInvocationHandler
from src.application.ports import ArtifactServicePort, InvocationUnitOfWork, ModelGatewayPort
from src.domain.agent_invocation import AgentInvocation, InvocationStatus
from src.domain.execution_contracts import (
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ModelProfile,
)
from src.infrastructure.gateway_client import ModelGatewayError


# ── Fakes ────────────────────────────────────────────────────────

class FakeUnitOfWork(InvocationUnitOfWork):
    """In-memory UoW that captures saves and events."""

    def __init__(self):
        self.saved: list[AgentInvocation] = []
        self.events: list[dict] = []
        self._store: dict[UUID, AgentInvocation] = {}

    def save_with_event(
        self,
        invocation: AgentInvocation,
        event_type: str,
        event_payload: dict,
    ) -> None:
        self.saved.append(invocation)
        self._store[invocation.id] = invocation
        self.events.append({
            "event_type": event_type,
            "invocation_id": str(invocation.id),
            "status": invocation.invocation_status.value,
            "payload": event_payload,
        })

    def get_last(self, invocation_id: UUID) -> AgentInvocation | None:
        return self._store.get(invocation_id)


class FakeGateway(ModelGatewayPort):
    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self._response = response or {
            "output_text": "Hello from model",
            "finish_reason": "stop",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "model_concrete": "gpt-4o-2024-05-13",
        }
        self._error = error
        self.calls: list[dict] = []

    def invoke_model(self, *, agent_invocation_id: UUID, model_alias: str,
                     messages: list[dict], workspace_id: UUID,
                     correlation_id: UUID, max_tokens: int | None = None,
                     temperature: float | None = None,
                     tools: list[dict] | None = None,
                     timeout_ms: int | None = None) -> dict:
        self.calls.append({
            "agent_invocation_id": agent_invocation_id,
            "model_alias": model_alias,
            "messages": messages,
            "workspace_id": workspace_id,
            "correlation_id": correlation_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools": tools,
        })
        if self._error:
            raise self._error
        return self._response


class FakeArtifactService(ArtifactServicePort):
    """In-memory artifact service that tracks calls."""

    def __init__(self, *, error_on: str | None = None):
        self.calls: list[dict] = []
        self._artifact_id = uuid4()
        self._error_on = error_on  # method name to raise on

    def _maybe_raise(self, method: str):
        if self._error_on == method:
            raise RuntimeError(f"Simulated {method} failure")

    def register_artifact(self, **kwargs) -> dict:
        self.calls.append({"method": "register_artifact", **kwargs})
        self._maybe_raise("register_artifact")
        return {"artifact_id": str(self._artifact_id), "status": "REGISTERED"}

    def begin_writing(self, artifact_id, **kwargs) -> dict:
        self.calls.append({"method": "begin_writing", "artifact_id": artifact_id, **kwargs})
        self._maybe_raise("begin_writing")
        return {"status": "WRITING"}

    def finalize_artifact(self, artifact_id, **kwargs) -> dict:
        self.calls.append({"method": "finalize_artifact", "artifact_id": artifact_id, **kwargs})
        self._maybe_raise("finalize_artifact")
        return {"status": "READY"}

    def fail_artifact(self, artifact_id, **kwargs) -> dict:
        self.calls.append({"method": "fail_artifact", "artifact_id": artifact_id, **kwargs})
        self._maybe_raise("fail_artifact")
        return {"status": "FAILED"}

    def write_content(self, artifact_id, content: bytes) -> dict:
        self.calls.append({"method": "write_content", "artifact_id": artifact_id})
        self._maybe_raise("write_content")
        return {"status": "OK"}


# ── Helpers ──────────────────────────────────────────────────────

def make_request(**overrides) -> ExecutionRequest:
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


def make_handler(
    gateway: FakeGateway | None = None,
    uow: FakeUnitOfWork | None = None,
    artifact_service: FakeArtifactService | None = None,
) -> tuple[ExecuteInvocationHandler, FakeUnitOfWork, FakeGateway]:
    fake_uow = uow or FakeUnitOfWork()
    gw = gateway or FakeGateway()
    handler = ExecuteInvocationHandler(
        unit_of_work=fake_uow,
        gateway=gw,
        artifact_service=artifact_service,
    )
    return handler, fake_uow, gw


# ── Happy path ───────────────────────────────────────────────────

class TestHappyPath:
    def test_execute_success(self):
        handler, uow, gw = make_handler()
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.agent_invocation_id == req.agent_invocation_id
        assert result.status == ExecutionStatus.COMPLETED
        assert result.output_payload["output_text"] == "Hello from model"

    def test_invocation_reaches_completed(self):
        handler, uow, _ = make_handler()
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv is not None
        assert inv.invocation_status == InvocationStatus.COMPLETED

    def test_lifecycle_transitions(self):
        """Verify invocation goes through initializing -> starting -> running -> completed."""
        handler, uow, _ = make_handler()
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.started_at is not None
        assert inv.completed_at is not None
        assert inv.completed_at >= inv.started_at

    def test_gateway_called_with_correct_params(self):
        handler, _, gw = make_handler()
        req = make_request(
            model_profile=ModelProfile(model_alias="claude-sonnet", max_tokens=100, temperature=0.5),
        )
        handler.execute(req)

        assert len(gw.calls) == 1
        call = gw.calls[0]
        assert call["model_alias"] == "claude-sonnet"
        assert call["max_tokens"] == 100
        assert call["temperature"] == 0.5
        assert call["workspace_id"] == req.workspace_id
        assert call["correlation_id"] == req.correlation_id
        assert call["agent_invocation_id"] == req.agent_invocation_id

    def test_usage_recorded(self):
        handler, uow, _ = make_handler()
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5
        assert result.usage.model_concrete == "gpt-4o-2024-05-13"

    def test_output_persisted(self):
        handler, uow, _ = make_handler()
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.output_messages is not None
        assert inv.output_messages[0]["content"] == "Hello from model"
        assert inv.prompt_tokens == 10
        assert inv.completion_tokens == 5

    def test_events_emitted(self):
        handler, uow, _ = make_handler()
        req = make_request()
        handler.execute(req)

        assert len(uow.events) == 2
        assert uow.events[0]["event_type"] == "agent_invocation.started"
        assert uow.events[1]["event_type"] == "agent_invocation.completed"


# ── Failure path ─────────────────────────────────────────────────

class TestFailurePath:
    def test_gateway_error_maps_to_failed(self):
        gw = FakeGateway(error=ModelGatewayError("HTTP_500", "server error", retryable=True))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionFailure)
        assert result.status == ExecutionStatus.FAILED
        assert result.error_code == "HTTP_500"
        assert result.retryable is True

    def test_failed_invocation_persisted(self):
        gw = FakeGateway(error=ModelGatewayError("HTTP_500", "server error"))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.invocation_status == InvocationStatus.FAILED
        assert inv.error_detail is not None
        assert inv.error_detail["error_code"] == "HTTP_500"

    def test_connection_error_maps_to_failed(self):
        gw = FakeGateway(error=ModelGatewayError("CONNECTION_ERROR", "refused", retryable=True))
        handler, _, _ = make_handler(gateway=gw)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionFailure)
        assert result.error_code == "CONNECTION_ERROR"
        assert result.retryable is True

    def test_unexpected_error_maps_to_failed(self):
        gw = FakeGateway(error=RuntimeError("unexpected crash"))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionFailure)
        assert result.error_code == "GATEWAY_ERROR"
        assert result.retryable is False

    def test_failure_events_emitted(self):
        gw = FakeGateway(error=ModelGatewayError("HTTP_500", "error"))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        assert len(uow.events) == 2
        assert uow.events[0]["event_type"] == "agent_invocation.started"
        assert uow.events[1]["event_type"] == "agent_invocation.failed"


# ── Timeout path ─────────────────────────────────────────────────

class TestTimeoutPath:
    def test_timeout_maps_to_timed_out(self):
        gw = FakeGateway(error=ModelGatewayError("TIMEOUT", "timed out", retryable=True))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionFailure)
        assert result.status == ExecutionStatus.TIMED_OUT
        assert result.error_code == "TIMEOUT"
        assert result.retryable is True

    def test_timed_out_invocation_persisted(self):
        gw = FakeGateway(error=ModelGatewayError("TIMEOUT", "timed out"))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.invocation_status == InvocationStatus.TIMED_OUT
        assert inv.completed_at is not None

    def test_timeout_events_emitted(self):
        gw = FakeGateway(error=ModelGatewayError("TIMEOUT", "timed out"))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        assert uow.events[-1]["event_type"] == "agent_invocation.timed_out"


# ── Input/output mapping ────────────────────────────────────────

class TestInputOutputMapping:
    def test_instruction_becomes_input_message(self):
        handler, uow, _ = make_handler()
        req = make_request(instruction="What is 2+2?")
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.input_messages == [{"role": "user", "content": "What is 2+2?"}]

    def test_model_response_becomes_output_message(self):
        gw = FakeGateway(response={
            "output_text": "The answer is 4.",
            "prompt_tokens": 5,
            "completion_tokens": 3,
            "model_concrete": "gpt-4o",
        })
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.output_messages == [{"role": "assistant", "content": "The answer is 4."}]

    def test_error_metadata_persisted(self):
        gw = FakeGateway(error=ModelGatewayError("RATE_LIMITED", "too many requests", retryable=True))
        handler, uow, _ = make_handler(gateway=gw)
        req = make_request()
        handler.execute(req)

        inv = uow.get_last(req.agent_invocation_id)
        assert inv.error_detail["error_code"] == "RATE_LIMITED"
        assert "too many requests" in inv.error_detail["error_message"]


# ── Artifact integration ────────────────────────────────────────

class TestArtifactIntegration:
    def test_artifact_created_on_success(self):
        fake_art = FakeArtifactService()
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.artifact_id == fake_art._artifact_id
        methods = [c["method"] for c in fake_art.calls]
        assert methods == ["register_artifact", "begin_writing", "finalize_artifact"]

    def test_artifact_register_params(self):
        fake_art = FakeArtifactService()
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request(
            model_profile=ModelProfile(model_alias="claude-sonnet", temperature=0.5, max_tokens=100),
        )
        result = handler.execute(req)

        reg = fake_art.calls[0]
        assert reg["workspace_id"] == req.workspace_id
        assert reg["task_id"] == req.task_id
        assert reg["run_id"] == req.run_id
        assert reg["step_id"] == req.step_id
        assert reg["agent_invocation_id"] == req.agent_invocation_id
        assert reg["artifact_type"] == "model_output"
        assert reg["root_type"] == "generated"
        assert reg["model_temperature"] == 0.5
        assert reg["model_max_tokens"] == 100
        assert reg["correlation_id"] == req.correlation_id

    def test_artifact_checksum_correct(self):
        fake_art = FakeArtifactService()
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request()
        handler.execute(req)

        finalize = fake_art.calls[2]
        output_bytes = b"Hello from model"
        expected_checksum = hashlib.sha256(output_bytes).hexdigest()
        assert finalize["checksum"] == expected_checksum
        assert finalize["size_bytes"] == len(output_bytes)

    def test_no_artifact_when_service_not_configured(self):
        handler, _, _ = make_handler(artifact_service=None)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.artifact_id is None

    def test_artifact_failure_does_not_block_result(self):
        """Best-effort: artifact failure → result still returned with artifact_id=None."""
        fake_art = FakeArtifactService(error_on="register_artifact")
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.artifact_id is None

    def test_begin_writing_failure_triggers_fail_artifact(self):
        """If begin_writing fails, attempt to mark artifact as FAILED."""
        fake_art = FakeArtifactService(error_on="begin_writing")
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.artifact_id is None
        methods = [c["method"] for c in fake_art.calls]
        assert "fail_artifact" in methods

    def test_finalize_failure_triggers_fail_artifact(self):
        fake_art = FakeArtifactService(error_on="finalize_artifact")
        handler, _, _ = make_handler(artifact_service=fake_art)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionResult)
        assert result.artifact_id is None
        methods = [c["method"] for c in fake_art.calls]
        assert "fail_artifact" in methods

    def test_no_artifact_on_gateway_failure(self):
        """Artifact creation should not happen when gateway call fails."""
        fake_art = FakeArtifactService()
        gw = FakeGateway(error=ModelGatewayError("HTTP_500", "error"))
        handler, _, _ = make_handler(gateway=gw, artifact_service=fake_art)
        req = make_request()
        result = handler.execute(req)

        assert isinstance(result, ExecutionFailure)
        assert len(fake_art.calls) == 0

    def test_model_concrete_passed_to_artifact(self):
        """model_concrete from gateway response is used for model_name_concrete."""
        fake_art = FakeArtifactService()
        gw = FakeGateway(response={
            "output_text": "test",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "model_concrete": "gpt-4o-2024-05-13",
            "provider_name": "openai",
        })
        handler, _, _ = make_handler(gateway=gw, artifact_service=fake_art)
        req = make_request()
        handler.execute(req)

        reg = fake_art.calls[0]
        assert reg["model_name_concrete"] == "gpt-4o-2024-05-13"
        assert reg["model_provider"] == "openai"
