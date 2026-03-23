"""ApprovalRequest domain model with state machine.

Human-in-the-loop approval for task/run/step entities.
State machine: pending → approved | rejected | timed_out | cancelled.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


class ApprovalDecision(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class ApprovalTargetType(str, enum.Enum):
    TASK = "task"
    RUN = "run"
    STEP = "step"
    ARTIFACT = "artifact"
    TOOL_CALL = "tool_call"


_APPROVAL_TRANSITIONS: dict[ApprovalDecision, frozenset[ApprovalDecision]] = {
    ApprovalDecision.PENDING: frozenset({
        ApprovalDecision.APPROVED,
        ApprovalDecision.REJECTED,
        ApprovalDecision.TIMED_OUT,
        ApprovalDecision.CANCELLED,
    }),
    ApprovalDecision.APPROVED: frozenset(),
    ApprovalDecision.REJECTED: frozenset(),
    ApprovalDecision.TIMED_OUT: frozenset(),
    ApprovalDecision.CANCELLED: frozenset(),
}

_APPROVAL_TERMINAL = frozenset({
    ApprovalDecision.APPROVED,
    ApprovalDecision.REJECTED,
    ApprovalDecision.TIMED_OUT,
    ApprovalDecision.CANCELLED,
})


class ApprovalRequest:
    """Approval request aggregate.

    Invariants:
    - Only one decision per approval (pending → terminal).
    - workspace_id, target_type, target_id are immutable after creation.
    - decided_by_id and decided_at set only on approve/reject.
    """

    __slots__ = (
        "id",
        "workspace_id",
        "target_type",
        "target_id",
        "requested_by",
        "reviewer_id",
        "prompt",
        "timeout_at",
        "decision",
        "decided_by_id",
        "decided_at",
        "decision_comment",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        *,
        workspace_id: UUID,
        target_type: ApprovalTargetType,
        target_id: UUID,
        requested_by: str,
        reviewer_id: UUID | None = None,
        prompt: str | None = None,
        timeout_at: datetime | None = None,
        # For reconstitution from persistence:
        id: UUID | None = None,
        decision: ApprovalDecision = ApprovalDecision.PENDING,
        decided_by_id: UUID | None = None,
        decided_at: datetime | None = None,
        decision_comment: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not requested_by or not requested_by.strip():
            raise DomainValidationError("ApprovalRequest", "requested_by must not be blank")

        now = datetime.now(timezone.utc)
        self.id = id or uuid4()
        self.workspace_id = workspace_id
        self.target_type = target_type
        self.target_id = target_id
        self.requested_by = requested_by
        self.reviewer_id = reviewer_id
        self.prompt = prompt
        self.timeout_at = timeout_at
        self.decision = decision
        self.decided_by_id = decided_by_id
        self.decided_at = decided_at
        self.decision_comment = decision_comment
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ApprovalRequest) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def _transition(self, target: ApprovalDecision) -> ApprovalDecision:
        current = self.decision
        if current in _APPROVAL_TERMINAL:
            raise TerminalStateError("ApprovalRequest", current.value, target.value)
        allowed = _APPROVAL_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("ApprovalRequest", current.value, target.value)
        self.decision = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ───────────────────────────────────

    def approve(self, decided_by_id: UUID, comment: str | None = None) -> ApprovalDecision:
        """pending → approved"""
        prev = self._transition(ApprovalDecision.APPROVED)
        self.decided_by_id = decided_by_id
        self.decided_at = datetime.now(timezone.utc)
        self.decision_comment = comment
        return prev

    def reject(self, decided_by_id: UUID, comment: str | None = None) -> ApprovalDecision:
        """pending → rejected"""
        prev = self._transition(ApprovalDecision.REJECTED)
        self.decided_by_id = decided_by_id
        self.decided_at = datetime.now(timezone.utc)
        self.decision_comment = comment
        return prev

    def time_out(self) -> ApprovalDecision:
        """pending → timed_out"""
        return self._transition(ApprovalDecision.TIMED_OUT)

    def cancel(self) -> ApprovalDecision:
        """pending → cancelled"""
        return self._transition(ApprovalDecision.CANCELLED)

    # ── Query helpers ───────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.decision in _APPROVAL_TERMINAL

    @property
    def is_pending(self) -> bool:
        return self.decision == ApprovalDecision.PENDING

    @property
    def is_expired(self) -> bool:
        if self.timeout_at is None:
            return False
        return datetime.now(timezone.utc) > self.timeout_at
