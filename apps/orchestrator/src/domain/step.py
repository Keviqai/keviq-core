"""Step domain model with state machine.

State machine transitions per doc 05, section 3.
Source of truth: Orchestrator (doc 04, section 3.9).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


class StepType(str, enum.Enum):
    AGENT_INVOCATION = "agent_invocation"
    TOOL_CALL = "tool_call"
    APPROVAL_GATE = "approval_gate"
    CONDITION = "condition"
    TRANSFORM = "transform"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# Valid transitions: source → set of targets (doc 05, section 3.3)
_STEP_TRANSITIONS: dict[StepStatus, frozenset[StepStatus]] = {
    StepStatus.PENDING: frozenset({StepStatus.RUNNING, StepStatus.SKIPPED, StepStatus.CANCELLED}),
    StepStatus.RUNNING: frozenset({
        StepStatus.WAITING_APPROVAL,
        StepStatus.BLOCKED,
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.CANCELLED,
    }),
    StepStatus.WAITING_APPROVAL: frozenset({StepStatus.RUNNING, StepStatus.CANCELLED}),
    StepStatus.BLOCKED: frozenset({StepStatus.RUNNING, StepStatus.FAILED, StepStatus.CANCELLED}),
    StepStatus.COMPLETED: frozenset(),
    StepStatus.FAILED: frozenset(),
    StepStatus.SKIPPED: frozenset(),
    StepStatus.CANCELLED: frozenset(),
}

_STEP_TERMINAL = frozenset({
    StepStatus.COMPLETED,
    StepStatus.FAILED,
    StepStatus.SKIPPED,
    StepStatus.CANCELLED,
})


class Step:
    """Step entity — smallest traceable execution unit in a Run.

    Invariants:
    - sequence > 0.
    - (run_id, sequence) is unique (enforced at DB level).
    - waiting_approval and blocked are distinct states (doc 05, section 3.2).
    - completed requires output_snapshot to have been set (doc 05, section 3.7).
    """

    __slots__ = (
        "id",
        "run_id",
        "workspace_id",
        "step_type",
        "step_status",
        "sequence",
        "parent_step_id",
        "input_snapshot",
        "output_snapshot",
        "started_at",
        "completed_at",
        "error_detail",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        *,
        run_id: UUID,
        workspace_id: UUID,
        sequence: int,
        step_type: StepType = StepType.AGENT_INVOCATION,
        parent_step_id: UUID | None = None,
        input_snapshot: dict[str, Any] | None = None,
        # For reconstitution:
        id: UUID | None = None,
        step_status: StepStatus = StepStatus.PENDING,
        output_snapshot: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_detail: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if sequence < 1:
            raise DomainValidationError("Step", "sequence must be > 0")

        self.id = id or uuid4()
        self.run_id = run_id
        self.workspace_id = workspace_id
        self.step_type = step_type
        self.step_status = step_status
        self.sequence = sequence
        self.parent_step_id = parent_step_id
        self.input_snapshot = input_snapshot
        self.output_snapshot = output_snapshot
        self.started_at = started_at
        self.completed_at = completed_at
        self.error_detail = error_detail
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.created_at

    # ── Transition helpers ──────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Step) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def _transition(self, target: StepStatus) -> StepStatus:
        current = self.step_status
        if current in _STEP_TERMINAL:
            raise TerminalStateError("Step", current.value, target.value)
        allowed = _STEP_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("Step", current.value, target.value)
        self.step_status = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ───────────────────────────────────

    def start(self, input_snapshot: dict[str, Any] | None = None) -> StepStatus:
        """pending → running

        Side effect: set started_at, record input_snapshot.
        Use approve() for waiting_approval → running, unblock() for blocked → running.
        """
        if self.step_status != StepStatus.PENDING:
            raise InvalidTransitionError(
                "Step", self.step_status.value, "running",
                reason="start only valid from pending; use approve() or unblock()",
            )
        prev = self._transition(StepStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc)
        if input_snapshot is not None:
            self.input_snapshot = input_snapshot
        return prev

    def complete(self, output_snapshot: dict[str, Any]) -> StepStatus:
        """running → completed

        Side effect: set completed_at, record output_snapshot.
        """
        prev = self._transition(StepStatus.COMPLETED)
        self.completed_at = datetime.now(timezone.utc)
        self.output_snapshot = output_snapshot
        return prev

    def fail(self, error_detail: dict[str, Any] | None = None) -> StepStatus:
        """running/blocked → failed

        Side effect: record error_detail.
        """
        prev = self._transition(StepStatus.FAILED)
        self.completed_at = datetime.now(timezone.utc)
        if error_detail is not None:
            self.error_detail = error_detail
        return prev

    def skip(self) -> StepStatus:
        """pending → skipped  (condition evaluated to false)"""
        prev = self._transition(StepStatus.SKIPPED)
        self.completed_at = datetime.now(timezone.utc)
        return prev

    def cancel(self) -> StepStatus:
        """pending/running/waiting_approval/blocked → cancelled

        Cascade from Run cancellation. No further side effects allowed.
        """
        prev = self._transition(StepStatus.CANCELLED)
        self.completed_at = self.completed_at or datetime.now(timezone.utc)
        return prev

    def request_approval(self) -> StepStatus:
        """running → waiting_approval"""
        return self._transition(StepStatus.WAITING_APPROVAL)

    def approve(self) -> StepStatus:
        """waiting_approval → running  (human approved)"""
        if self.step_status != StepStatus.WAITING_APPROVAL:
            raise InvalidTransitionError(
                "Step", self.step_status.value, "running",
                reason="approve only valid from waiting_approval",
            )
        return self._transition(StepStatus.RUNNING)

    def block(self) -> StepStatus:
        """running → blocked  (dependency not satisfied)"""
        return self._transition(StepStatus.BLOCKED)

    def unblock(self) -> StepStatus:
        """blocked → running  (dependency resolved)"""
        if self.step_status != StepStatus.BLOCKED:
            raise InvalidTransitionError(
                "Step", self.step_status.value, "running",
                reason="unblock only valid from blocked",
            )
        return self._transition(StepStatus.RUNNING)

    # ── Query helpers ───────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.step_status in _STEP_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.step_status in (
            StepStatus.PENDING,
            StepStatus.RUNNING,
            StepStatus.WAITING_APPROVAL,
            StepStatus.BLOCKED,
        )
