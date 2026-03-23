"""Application-layer port interfaces for agent-runtime.

Infrastructure layer implements these. Application layer depends on these only.
No SQLAlchemy, no FastAPI, no httpx imports allowed here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.agent_invocation import AgentInvocation
    from src.domain.execution_contracts import (
        ExecutionResult,
        ExecutionFailure,
    )


class AgentInvocationRepository(ABC):
    """Persistence port for AgentInvocation entities."""

    @abstractmethod
    def save(self, invocation: AgentInvocation) -> None: ...

    @abstractmethod
    def get_by_id(self, invocation_id: UUID, workspace_id: UUID) -> AgentInvocation | None: ...

    @abstractmethod
    def list_active(self, workspace_id: UUID, limit: int = 50) -> list[AgentInvocation]: ...

    @abstractmethod
    def list_by_step(self, step_id: UUID, workspace_id: UUID) -> list[AgentInvocation]: ...


class ModelGatewayPort(ABC):
    """Port for calling model-gateway service (S5 Gateway Pattern).

    Implementation will use httpx to call model-gateway HTTP API.
    This port ensures domain/application layer stays transport-agnostic.
    """

    @abstractmethod
    def invoke_model(
        self,
        *,
        agent_invocation_id: UUID,
        model_alias: str,
        messages: list[dict],
        workspace_id: UUID,
        correlation_id: UUID,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        """Call model-gateway and return raw response dict.

        Raises ModelGatewayError on failure.
        """
        ...


class InvocationUnitOfWork(ABC):
    """Port for transactional save+outbox writes.

    Ensures invocation state and outbox event are committed atomically.
    Infrastructure implements this with a DB transaction.
    """

    @abstractmethod
    def save_with_event(
        self,
        invocation: AgentInvocation,
        event_type: str,
        event_payload: dict,
    ) -> None:
        """Save invocation state and write outbox event in the same transaction."""
        ...


class ArtifactServicePort(ABC):
    """Port for creating artifacts via artifact-service.

    Implementation uses httpx to call artifact-service HTTP API.
    Artifact creation is best-effort in Slice 5 — failures are logged,
    not propagated to the caller.
    """

    @abstractmethod
    def register_artifact(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        name: str,
        artifact_type: str,
        root_type: str,
        mime_type: str | None = None,
        model_provider: str | None,
        model_name_concrete: str | None,
        model_version_concrete: str | None,
        model_temperature: float | None,
        model_max_tokens: int | None,
        run_config_hash: str | None,
        correlation_id: UUID | None,
    ) -> dict:
        """Register artifact → returns dict with artifact_id."""
        ...

    @abstractmethod
    def begin_writing(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        storage_ref: str,
        correlation_id: UUID | None,
    ) -> dict:
        """Transition artifact to WRITING state."""
        ...

    @abstractmethod
    def write_content(self, artifact_id: UUID, content: bytes) -> dict:
        """Write raw content bytes to artifact storage."""
        ...

    @abstractmethod
    def finalize_artifact(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        checksum: str,
        size_bytes: int,
        content_base64: str | None = None,
        correlation_id: UUID | None = None,
    ) -> dict:
        """Finalize artifact with checksum → READY state."""
        ...

    @abstractmethod
    def fail_artifact(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        failure_reason: str | None,
        correlation_id: UUID | None,
    ) -> dict:
        """Mark artifact as FAILED."""
        ...


class ExecutionServicePort(ABC):
    """Port for calling execution-service to run tools in sandboxes.

    Implementation uses httpx to call execution-service HTTP API.
    Used by the tool execution loop in ExecuteInvocationHandler.
    """

    @abstractmethod
    def call_tool(
        self,
        *,
        sandbox_id: UUID,
        tool_name: str,
        tool_input: dict,
        attempt_index: int = 0,
        timeout_ms: int = 30_000,
    ) -> dict:
        """Execute a tool in a sandbox. Returns result dict with stdout/stderr/exit_code.

        Raises on connection failure or timeout.
        """
        ...


class ToolApprovalServicePort(ABC):
    """Port for requesting tool approval from orchestrator.

    Implementation uses httpx to call orchestrator's tool-approval endpoint.
    Used by ExecuteInvocationHandler when tool approval policy gates a tool call.
    """

    @abstractmethod
    def request_tool_approval(
        self,
        *,
        workspace_id: UUID,
        invocation_id: UUID,
        run_id: UUID,
        task_id: UUID,
        tool_name: str,
        arguments_preview: str,
        risk_reason: str,
    ) -> dict:
        """Request human approval for a tool call.

        Returns dict with approval_id on success.
        Raises on connection failure or rejection.
        """
        ...


class ExecutionResultCallback(ABC):
    """Port for reporting execution results back to orchestrator.

    Implementation may use outbox events or direct HTTP callback.
    """

    @abstractmethod
    def report_success(self, result: ExecutionResult) -> None: ...

    @abstractmethod
    def report_failure(self, failure: ExecutionFailure) -> None: ...
