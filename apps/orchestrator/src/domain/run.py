"""Run domain model with state machine.

State machine transitions per doc 05, section 2.
Source of truth: Orchestrator (doc 04, section 3.8).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    ImmutableFieldError,
    InvalidTransitionError,
    TerminalStateError,
)


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    APPROVAL = "approval"


# Valid transitions: source → set of targets (doc 05, section 2.3)
_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.PREPARING, RunStatus.CANCELLED}),
    RunStatus.PREPARING: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset({
        RunStatus.WAITING_APPROVAL,
        RunStatus.COMPLETING,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    }),
    RunStatus.WAITING_APPROVAL: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.COMPLETING: frozenset({RunStatus.COMPLETED, RunStatus.FAILED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.TIMED_OUT: frozenset({RunStatus.CANCELLED}),
    RunStatus.CANCELLED: frozenset(),
}

# TIMED_OUT is not terminal because it can still transition to CANCELLED
# (system cleanup, doc 05 section 2.3). However, no resume is allowed from
# TIMED_OUT (doc 05 section 2.7) — this is enforced by the transition table
# which only permits timed_out → cancelled.
_RUN_TERMINAL = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


class Run:
    """Run entity — one execution attempt of a Task.

    Invariants:
    - run_config is immutable after Run leaves QUEUED (doc 04).
    - No resume from failed/cancelled/timed_out (doc 05, section 2.7).
    - duration_ms >= 0.
    """

    __slots__ = (
        "id",
        "task_id",
        "workspace_id",
        "run_status",
        "trigger_type",
        "triggered_by_id",
        "started_at",
        "completed_at",
        "duration_ms",
        "run_config",
        "error_summary",
        "created_at",
        "updated_at",
        "_config_locked",
    )

    def __init__(
        self,
        *,
        task_id: UUID,
        workspace_id: UUID,
        trigger_type: TriggerType = TriggerType.MANUAL,
        triggered_by_id: UUID | None = None,
        run_config: dict[str, Any] | None = None,
        # For reconstitution:
        id: UUID | None = None,
        run_status: RunStatus = RunStatus.QUEUED,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        duration_ms: int | None = None,
        error_summary: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if duration_ms is not None and duration_ms < 0:
            raise DomainValidationError("Run", "duration_ms must be >= 0")

        self.id = id or uuid4()
        self.task_id = task_id
        self.workspace_id = workspace_id
        self.run_status = run_status
        self.trigger_type = trigger_type
        self.triggered_by_id = triggered_by_id
        self.started_at = started_at
        self.completed_at = completed_at
        self.duration_ms = duration_ms
        self.run_config = run_config or {}
        self.error_summary = error_summary
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or self.created_at
        # Config locked after leaving QUEUED (doc 05, section 2.5)
        self._config_locked = run_status != RunStatus.QUEUED

    def _compute_duration(self, end: datetime) -> int | None:
        if self.started_at is None:
            return None
        return max(0, int((end - self.started_at).total_seconds() * 1000))

    # ── Config management ───────────────────────────────────────

    def update_config(self, config: dict[str, Any]) -> None:
        """Update run_config. Only allowed while QUEUED."""
        if self._config_locked:
            raise ImmutableFieldError("Run", "run_config", "locked after leaving queued")
        self.run_config = config

    # ── Transition helpers ──────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Run) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def _transition(self, target: RunStatus) -> RunStatus:
        current = self.run_status
        if current in _RUN_TERMINAL:
            raise TerminalStateError("Run", current.value, target.value)
        allowed = _RUN_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("Run", current.value, target.value)
        self.run_status = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ───────────────────────────────────

    def prepare(self) -> RunStatus:
        """queued → preparing  (side effect: lock run_config)"""
        prev = self._transition(RunStatus.PREPARING)
        self._config_locked = True
        return prev

    def start(self) -> RunStatus:
        """preparing → running  (side effect: set started_at, create first Step)"""
        prev = self._transition(RunStatus.RUNNING)
        self.started_at = self.started_at or datetime.now(timezone.utc)
        return prev

    def request_approval(self) -> RunStatus:
        """running → waiting_approval"""
        return self._transition(RunStatus.WAITING_APPROVAL)

    def approve(self) -> RunStatus:
        """waiting_approval → running"""
        return self._transition(RunStatus.RUNNING)

    def begin_completing(self) -> RunStatus:
        """running → completing"""
        return self._transition(RunStatus.COMPLETING)

    def complete(self) -> RunStatus:
        """completing → completed  (side effect: set completed_at, duration_ms)"""
        prev = self._transition(RunStatus.COMPLETED)
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.duration_ms = self._compute_duration(now)
        return prev

    def fail(self, error_summary: str | None = None) -> RunStatus:
        """preparing/running/completing → failed"""
        prev = self._transition(RunStatus.FAILED)
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.duration_ms = self._compute_duration(now)
        if error_summary:
            self.error_summary = error_summary
        return prev

    def cancel(self) -> RunStatus:
        """queued/preparing/running/waiting_approval/timed_out → cancelled

        Side effect: all active Steps must be cancelled (cascade).
        """
        prev = self._transition(RunStatus.CANCELLED)
        now = datetime.now(timezone.utc)
        self.completed_at = self.completed_at or now
        self.duration_ms = self._compute_duration(self.completed_at)
        return prev

    def time_out(self) -> RunStatus:
        """running → timed_out  (side effect: terminate all Steps + AgentInvocations)"""
        prev = self._transition(RunStatus.TIMED_OUT)
        now = datetime.now(timezone.utc)
        self.completed_at = now
        self.duration_ms = self._compute_duration(now)
        return prev

    # ── Query helpers ───────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.run_status in _RUN_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.run_status in (
            RunStatus.QUEUED,
            RunStatus.PREPARING,
            RunStatus.RUNNING,
            RunStatus.WAITING_APPROVAL,
            RunStatus.COMPLETING,
        )
