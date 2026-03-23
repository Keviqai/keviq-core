"""Execution contracts — transport-agnostic value objects.

These contracts define the boundary between agent-runtime and
execution-service for sandbox provisioning, tool execution, and
sandbox termination.  They are pure data classes with no framework
dependencies (no FastAPI, SQLAlchemy, or httpx).

Ownership: execution-service defines these contracts.
Consumers: agent-runtime-service (via HTTP adapter).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


# ── Sandbox Provisioning ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SandboxProvisionRequest:
    """Request to provision a new sandbox environment.

    Sent by agent-runtime to execution-service when an invocation
    needs a sandbox for tool execution.
    """
    workspace_id: UUID
    task_id: UUID
    run_id: UUID
    step_id: UUID
    agent_invocation_id: UUID
    sandbox_type: str  # 'container' | 'subprocess'
    policy_snapshot: dict[str, Any] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)
    network_egress_policy: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 300_000  # 5 min default

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": str(self.workspace_id),
            "task_id": str(self.task_id),
            "run_id": str(self.run_id),
            "step_id": str(self.step_id),
            "agent_invocation_id": str(self.agent_invocation_id),
            "sandbox_type": self.sandbox_type,
            "policy_snapshot": self.policy_snapshot,
            "resource_limits": self.resource_limits,
            "network_egress_policy": self.network_egress_policy,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxProvisionRequest:
        return cls(
            workspace_id=UUID(data["workspace_id"]),
            task_id=UUID(data["task_id"]),
            run_id=UUID(data["run_id"]),
            step_id=UUID(data["step_id"]),
            agent_invocation_id=UUID(data["agent_invocation_id"]),
            sandbox_type=data["sandbox_type"],
            policy_snapshot=data.get("policy_snapshot", {}),
            resource_limits=data.get("resource_limits", {}),
            network_egress_policy=data.get("network_egress_policy", {}),
            timeout_ms=data.get("timeout_ms", 300_000),
        )


@dataclass(frozen=True, slots=True)
class SandboxProvisionResult:
    """Result of sandbox provisioning.

    Returned by execution-service after successfully provisioning
    a sandbox, or with error details on failure.
    """
    sandbox_id: UUID
    status: str  # 'ready' | 'failed'
    error_code: str | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sandbox_id": str(self.sandbox_id),
            "status": self.status,
        }
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.error_message is not None:
            result["error_message"] = self.error_message
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxProvisionResult:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            status=data["status"],
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
        )


# ── Tool Execution ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolExecutionRequest:
    """Request to execute a tool inside an active sandbox.

    Sent by agent-runtime to execution-service.  The sandbox must
    be in 'ready' or 'idle' state to accept tool executions.
    """
    sandbox_id: UUID
    attempt_index: int
    tool_name: str
    tool_input: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30_000  # 30s default per tool call

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_id": str(self.sandbox_id),
            "attempt_index": self.attempt_index,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "timeout_ms": self.timeout_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolExecutionRequest:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            attempt_index=data["attempt_index"],
            tool_name=data["tool_name"],
            tool_input=data.get("tool_input", {}),
            timeout_ms=data.get("timeout_ms", 30_000),
        )


class ToolExecutionStatus(str, enum.Enum):
    """Outcome of a single tool execution."""
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Result of executing a tool inside a sandbox.

    Returned by execution-service after tool execution completes,
    fails, or times out.
    """
    sandbox_id: UUID
    attempt_index: int
    status: ToolExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    truncated: bool = False
    error_code: str | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.status == ToolExecutionStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sandbox_id": str(self.sandbox_id),
            "attempt_index": self.attempt_index,
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
        }
        if self.exit_code is not None:
            result["exit_code"] = self.exit_code
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.error_message is not None:
            result["error_message"] = self.error_message
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolExecutionResult:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            attempt_index=data["attempt_index"],
            status=ToolExecutionStatus(data["status"]),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code"),
            truncated=data.get("truncated", False),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
        )


# ── Sandbox Termination ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SandboxTerminationRequest:
    """Request to terminate an active sandbox.

    Sent by agent-runtime or orchestrator (via event) when a sandbox
    is no longer needed or must be force-terminated.
    """
    sandbox_id: UUID
    reason: str = "completed"  # completed | timeout | policy_violation | error | manual

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_id": str(self.sandbox_id),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxTerminationRequest:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            reason=data.get("reason", "completed"),
        )


@dataclass(frozen=True, slots=True)
class SandboxTerminationResult:
    """Result of sandbox termination."""
    sandbox_id: UUID
    status: str  # 'terminated' | 'failed'
    error_message: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "terminated"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "sandbox_id": str(self.sandbox_id),
            "status": self.status,
        }
        if self.error_message is not None:
            result["error_message"] = self.error_message
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxTerminationResult:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            status=data["status"],
            error_message=data.get("error_message"),
        )
