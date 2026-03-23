"""Sandbox domain entity with state machine.

Source of truth: execution-service (SVC-04).
State machine: doc 05 § 5 — Sandbox Lifecycle.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


# ── Enums ──────────────────────────────────────────────────────


class SandboxType(str, enum.Enum):
    """Type of sandbox environment."""
    CONTAINER = "container"
    SUBPROCESS = "subprocess"


class SandboxStatus(str, enum.Enum):
    """Sandbox lifecycle states — from doc 05 § 5.2."""
    PROVISIONING = "provisioning"
    READY = "ready"
    EXECUTING = "executing"
    IDLE = "idle"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    FAILED = "failed"


class TerminationReason(str, enum.Enum):
    """Why a sandbox was terminated — from doc 04 § 3.11."""
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    POLICY_VIOLATION = "policy_violation"
    ERROR = "error"
    MANUAL = "manual"


# ── State Machine ─────────────────────────────────────────────


_SANDBOX_TRANSITIONS: dict[SandboxStatus, frozenset[SandboxStatus]] = {
    SandboxStatus.PROVISIONING: frozenset({
        SandboxStatus.READY,
        SandboxStatus.FAILED,
    }),
    SandboxStatus.READY: frozenset({
        SandboxStatus.EXECUTING,
        SandboxStatus.TERMINATING,
    }),
    SandboxStatus.EXECUTING: frozenset({
        SandboxStatus.IDLE,
        SandboxStatus.FAILED,
        SandboxStatus.TERMINATING,
    }),
    SandboxStatus.IDLE: frozenset({
        SandboxStatus.EXECUTING,
        SandboxStatus.TERMINATING,
    }),
    SandboxStatus.FAILED: frozenset({
        SandboxStatus.TERMINATING,
    }),
    SandboxStatus.TERMINATING: frozenset({
        SandboxStatus.TERMINATED,
    }),
    SandboxStatus.TERMINATED: frozenset(),
}

# FAILED is intentionally excluded: it can still transition to TERMINATING
# for cleanup.  Only TERMINATED is truly terminal (no outbound edges).
_SANDBOX_TERMINAL = frozenset({
    SandboxStatus.TERMINATED,
})


# ── Entity ─────────────────────────────────────────────────────


class Sandbox:
    """Sandbox domain entity.

    Represents an ephemeral execution environment provisioned for a
    single agent invocation.  Does not persist state across invocations.

    Identity: sandbox_id assigned by execution-service.
    Ownership: execution-service (SVC-04) — orchestrator/runtime hold reference only.
    """

    __slots__ = (
        "id",
        "workspace_id",
        "task_id",
        "run_id",
        "step_id",
        "agent_invocation_id",
        "sandbox_type",
        "sandbox_status",
        "policy_snapshot",
        "resource_limits",
        "network_egress_policy",
        "started_at",
        "terminated_at",
        "termination_reason",
        "error_detail",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        *,
        id: UUID,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        sandbox_type: SandboxType,
        sandbox_status: SandboxStatus = SandboxStatus.PROVISIONING,
        policy_snapshot: dict[str, Any] | None = None,
        resource_limits: dict[str, Any] | None = None,
        network_egress_policy: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        terminated_at: datetime | None = None,
        termination_reason: TerminationReason | None = None,
        error_detail: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not id:
            raise DomainValidationError("Sandbox", "id is required")
        if not workspace_id:
            raise DomainValidationError("Sandbox", "workspace_id is required")
        if not task_id:
            raise DomainValidationError("Sandbox", "task_id is required")
        if not run_id:
            raise DomainValidationError("Sandbox", "run_id is required")
        if not step_id:
            raise DomainValidationError("Sandbox", "step_id is required")
        if not agent_invocation_id:
            raise DomainValidationError(
                "Sandbox", "agent_invocation_id is required",
            )

        now = datetime.now(timezone.utc)
        self.id = id
        self.workspace_id = workspace_id
        self.task_id = task_id
        self.run_id = run_id
        self.step_id = step_id
        self.agent_invocation_id = agent_invocation_id
        self.sandbox_type = sandbox_type
        self.sandbox_status = sandbox_status
        self.policy_snapshot = policy_snapshot or {}
        self.resource_limits = resource_limits or {}
        self.network_egress_policy = network_egress_policy or {}
        self.started_at = started_at
        self.terminated_at = terminated_at
        self.termination_reason = termination_reason
        self.error_detail = error_detail
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sandbox) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    # ── Transition helpers ─────────────────────────────────────

    def _transition(self, target: SandboxStatus) -> SandboxStatus:
        """Validate and apply state transition. Returns previous status."""
        current = self.sandbox_status
        if current in _SANDBOX_TERMINAL:
            raise TerminalStateError(
                "Sandbox", current.value, target.value,
            )
        allowed = _SANDBOX_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError(
                "Sandbox", current.value, target.value,
            )
        self.sandbox_status = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ──────────────────────────────────

    def mark_ready(self) -> SandboxStatus:
        """Sandbox provisioned and ready to accept tool executions."""
        prev = self._transition(SandboxStatus.READY)
        self.started_at = datetime.now(timezone.utc)
        return prev

    def mark_executing(self) -> SandboxStatus:
        """Sandbox begins executing a tool."""
        return self._transition(SandboxStatus.EXECUTING)

    def mark_idle(self) -> SandboxStatus:
        """Tool execution completed, sandbox waiting for next command."""
        return self._transition(SandboxStatus.IDLE)

    def mark_failed(
        self,
        error_detail: dict[str, Any] | None = None,
    ) -> SandboxStatus:
        """Sandbox encountered an unrecoverable error."""
        prev = self._transition(SandboxStatus.FAILED)
        self.error_detail = error_detail
        return prev

    def mark_terminating(
        self,
        reason: TerminationReason = TerminationReason.COMPLETED,
    ) -> SandboxStatus:
        """Begin sandbox shutdown."""
        prev = self._transition(SandboxStatus.TERMINATING)
        self.termination_reason = reason
        return prev

    def mark_terminated(self) -> SandboxStatus:
        """Sandbox fully shut down."""
        prev = self._transition(SandboxStatus.TERMINATED)
        self.terminated_at = datetime.now(timezone.utc)
        return prev

    # ── Query helpers ──────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.sandbox_status in _SANDBOX_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.sandbox_status not in (
            SandboxStatus.TERMINATED, SandboxStatus.FAILED,
        )
