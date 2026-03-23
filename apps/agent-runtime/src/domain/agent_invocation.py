"""AgentInvocation domain model with state machine.

State machine transitions per doc 05, section 4.
Source of truth: Agent Runtime (doc 04, section 3.10).

The user's PR14 scope specifies these states for Slice 3:
  queued → starting → running → completed/failed/timed_out/cancelled/interrupted

Doc 05 states (initializing, waiting_human, waiting_tool, compensating, compensated)
are included for completeness but some are not exercised in Slice 3 happy path.

We reconcile by mapping:
  - PR14 "queued" = doc 05 "initializing" (entry state)
  - PR14 "starting" = new transitional state before "running"
  - compensating/compensated kept for future use
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from .errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


class InvocationStatus(str, enum.Enum):
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


# Valid transitions: source → set of targets (doc 05 section 4 + PR14 extensions)
_INVOCATION_TRANSITIONS: dict[InvocationStatus, frozenset[InvocationStatus]] = {
    InvocationStatus.INITIALIZING: frozenset({
        InvocationStatus.STARTING,
        InvocationStatus.CANCELLED,
        InvocationStatus.FAILED,
    }),
    InvocationStatus.STARTING: frozenset({
        InvocationStatus.RUNNING,
        InvocationStatus.FAILED,
        InvocationStatus.CANCELLED,
    }),
    InvocationStatus.RUNNING: frozenset({
        InvocationStatus.WAITING_HUMAN,
        InvocationStatus.WAITING_TOOL,
        InvocationStatus.COMPLETED,
        InvocationStatus.FAILED,
        InvocationStatus.TIMED_OUT,
        InvocationStatus.CANCELLED,
        InvocationStatus.INTERRUPTED,
    }),
    InvocationStatus.WAITING_HUMAN: frozenset({
        InvocationStatus.RUNNING,
        InvocationStatus.FAILED,
        InvocationStatus.CANCELLED,
        InvocationStatus.INTERRUPTED,
    }),
    InvocationStatus.WAITING_TOOL: frozenset({
        InvocationStatus.RUNNING,
        InvocationStatus.FAILED,
        InvocationStatus.CANCELLED,
        InvocationStatus.INTERRUPTED,
    }),
    InvocationStatus.COMPLETED: frozenset(),
    InvocationStatus.FAILED: frozenset({InvocationStatus.COMPENSATING}),
    InvocationStatus.TIMED_OUT: frozenset({InvocationStatus.COMPENSATING}),
    InvocationStatus.CANCELLED: frozenset(),
    InvocationStatus.INTERRUPTED: frozenset({InvocationStatus.COMPENSATING}),
    InvocationStatus.COMPENSATING: frozenset({
        InvocationStatus.COMPENSATED,
        InvocationStatus.FAILED,
    }),
    InvocationStatus.COMPENSATED: frozenset(),
}

_INVOCATION_TERMINAL = frozenset({
    InvocationStatus.COMPLETED,
    InvocationStatus.CANCELLED,
    InvocationStatus.COMPENSATED,
})


class AgentInvocation:
    """AgentInvocation entity — a single LLM execution within a Step.

    Invariants:
    - id is always supplied by orchestrator (no auto-generation).
    - step_id, run_id, workspace_id, agent_id, model_id are immutable.
    - Transitions enforced via domain methods, not free set.
    - Agent Runtime owns this lifecycle; Orchestrator only creates and reads.
    """

    __slots__ = (
        "id",
        "step_id",
        "run_id",
        "task_id",
        "workspace_id",
        "correlation_id",
        "agent_id",
        "model_id",
        "invocation_status",
        "prompt_tokens",
        "completion_tokens",
        "total_cost_usd",
        "input_messages",
        "output_messages",
        "tool_calls",
        "error_detail",
        "pending_tool_context",
        "started_at",
        "completed_at",
        "created_at",
    )

    def __init__(
        self,
        *,
        id: UUID,
        step_id: UUID,
        run_id: UUID,
        task_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
        agent_id: str,
        model_id: str,
        # For reconstitution:
        invocation_status: InvocationStatus = InvocationStatus.INITIALIZING,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_cost_usd: Decimal | None = None,
        input_messages: list[dict[str, Any]] | None = None,
        output_messages: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        error_detail: dict[str, Any] | None = None,
        pending_tool_context: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        created_at: datetime | None = None,
    ):
        if not agent_id or agent_id.isspace():
            raise DomainValidationError("AgentInvocation", "agent_id must not be blank")
        if not model_id or model_id.isspace():
            raise DomainValidationError("AgentInvocation", "model_id must not be blank")

        self.id = id
        self.step_id = step_id
        self.run_id = run_id
        self.task_id = task_id
        self.workspace_id = workspace_id
        self.correlation_id = correlation_id
        self.agent_id = agent_id
        self.model_id = model_id
        self.invocation_status = invocation_status
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_cost_usd = total_cost_usd
        self.input_messages = input_messages
        self.output_messages = output_messages
        self.tool_calls = tool_calls
        self.error_detail = error_detail
        self.pending_tool_context = pending_tool_context
        self.started_at = started_at
        self.completed_at = completed_at
        self.created_at = created_at or datetime.now(timezone.utc)

    # ── Identity ─────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AgentInvocation) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    # ── Transition core ──────────────────────────────────────────

    def _transition(self, target: InvocationStatus) -> InvocationStatus:
        current = self.invocation_status
        if current in _INVOCATION_TERMINAL:
            raise TerminalStateError("AgentInvocation", current.value, target.value)
        allowed = _INVOCATION_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("AgentInvocation", current.value, target.value)
        self.invocation_status = target
        return current

    # ── Public transition API ────────────────────────────────────

    def mark_starting(self) -> InvocationStatus:
        """initializing → starting"""
        return self._transition(InvocationStatus.STARTING)

    def mark_running(self, input_messages: list[dict[str, Any]] | None = None) -> InvocationStatus:
        """starting/waiting_human/waiting_tool → running

        Side effect: set started_at on first run, record input_messages.
        """
        prev = self._transition(InvocationStatus.RUNNING)
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        if input_messages is not None:
            self.input_messages = input_messages
        return prev

    def mark_waiting_human(
        self, pending_tool_context: dict[str, Any] | None = None,
    ) -> InvocationStatus:
        """running → waiting_human

        Side effect: store pending_tool_context for resume in O5-S2.
        """
        prev = self._transition(InvocationStatus.WAITING_HUMAN)
        if pending_tool_context is not None:
            self.pending_tool_context = pending_tool_context
        return prev

    def mark_waiting_tool(self) -> InvocationStatus:
        """running → waiting_tool"""
        return self._transition(InvocationStatus.WAITING_TOOL)

    def mark_completed(
        self,
        output_messages: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_cost_usd: Decimal | None = None,
    ) -> InvocationStatus:
        """running → completed

        Side effect: set completed_at, record output and usage.
        """
        prev = self._transition(InvocationStatus.COMPLETED)
        self.completed_at = datetime.now(timezone.utc)
        if output_messages is not None:
            self.output_messages = output_messages
        if tool_calls is not None:
            self.tool_calls = tool_calls
        if prompt_tokens is not None:
            self.prompt_tokens = prompt_tokens
        if completion_tokens is not None:
            self.completion_tokens = completion_tokens
        if total_cost_usd is not None:
            self.total_cost_usd = total_cost_usd
        return prev

    def mark_failed(self, error_detail: dict[str, Any] | None = None) -> InvocationStatus:
        """initializing/starting/running/waiting_tool/compensating → failed

        Side effect: set completed_at, record error.
        """
        prev = self._transition(InvocationStatus.FAILED)
        self.completed_at = self.completed_at or datetime.now(timezone.utc)
        if error_detail is not None:
            self.error_detail = error_detail
        return prev

    def mark_timed_out(self, error_detail: dict[str, Any] | None = None) -> InvocationStatus:
        """running → timed_out

        Side effect: set completed_at, record error.
        """
        prev = self._transition(InvocationStatus.TIMED_OUT)
        self.completed_at = datetime.now(timezone.utc)
        if error_detail is not None:
            self.error_detail = error_detail
        return prev

    def mark_cancelled(self) -> InvocationStatus:
        """initializing/starting/running/waiting_human/waiting_tool → cancelled

        Side effect: set completed_at.
        """
        prev = self._transition(InvocationStatus.CANCELLED)
        self.completed_at = self.completed_at or datetime.now(timezone.utc)
        return prev

    def mark_interrupted(self) -> InvocationStatus:
        """running/waiting_human/waiting_tool → interrupted

        Cascade from Step cancellation or external signal.
        """
        prev = self._transition(InvocationStatus.INTERRUPTED)
        self.completed_at = self.completed_at or datetime.now(timezone.utc)
        return prev

    def mark_compensating(self) -> InvocationStatus:
        """failed/timed_out/interrupted → compensating"""
        return self._transition(InvocationStatus.COMPENSATING)

    def mark_compensated(self) -> InvocationStatus:
        """compensating → compensated"""
        return self._transition(InvocationStatus.COMPENSATED)

    def resume_from_wait(self) -> InvocationStatus:
        """waiting_human/waiting_tool → running"""
        if self.invocation_status not in (InvocationStatus.WAITING_HUMAN, InvocationStatus.WAITING_TOOL):
            raise InvalidTransitionError(
                "AgentInvocation", self.invocation_status.value, "running",
                reason="resume_from_wait only valid from waiting_human/waiting_tool",
            )
        return self._transition(InvocationStatus.RUNNING)

    # ── Query helpers ────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.invocation_status in _INVOCATION_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.invocation_status in (
            InvocationStatus.INITIALIZING,
            InvocationStatus.STARTING,
            InvocationStatus.RUNNING,
            InvocationStatus.WAITING_HUMAN,
            InvocationStatus.WAITING_TOOL,
        )

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None
