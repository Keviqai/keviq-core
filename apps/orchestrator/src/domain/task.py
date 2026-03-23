"""Task domain model with state machine.

State machine transitions per doc 05, section 1.
Source of truth: Orchestrator (doc 04, section 3.7).
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


class TaskType(str, enum.Enum):
    CODING = "coding"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    OPERATION = "operation"
    CUSTOM = "custom"


class TaskStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


# Valid transitions: source → set of targets (doc 05, section 1.3)
# NOTE: draft → cancelled is an intentional extension — users should be able
# to discard a draft without first submitting it.
_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.PENDING, TaskStatus.CANCELLED}),
    TaskStatus.PENDING: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset({
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.WAITING_APPROVAL: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset({TaskStatus.ARCHIVED}),
    TaskStatus.FAILED: frozenset({TaskStatus.PENDING, TaskStatus.ARCHIVED}),
    TaskStatus.CANCELLED: frozenset({TaskStatus.ARCHIVED}),
    TaskStatus.ARCHIVED: frozenset(),
}

_TASK_TERMINAL = frozenset({TaskStatus.ARCHIVED})

VALID_RISK_LEVELS = frozenset({'low', 'medium', 'high'})


class Task:
    """Task aggregate root.

    Invariants:
    - Only orchestrator mutates task_status (PP1).
    - Transitions enforced via methods, not free set.
    - workspace_id, created_by_id are immutable after creation.
    """

    __slots__ = (
        "id",
        "workspace_id",
        "title",
        "description",
        "task_type",
        "task_status",
        "input_config",
        "repo_snapshot_id",
        "policy_id",
        "parent_task_id",
        "created_by_id",
        "created_at",
        "updated_at",
        # Q1 brief fields
        "goal",
        "context",
        "constraints",
        "desired_output",
        "template_id",
        "agent_template_id",
        "risk_level",
    )

    def __init__(
        self,
        *,
        workspace_id: UUID,
        title: str,
        task_type: TaskType,
        created_by_id: UUID,
        description: str | None = None,
        input_config: dict[str, Any] | None = None,
        repo_snapshot_id: UUID | None = None,
        policy_id: UUID | None = None,
        parent_task_id: UUID | None = None,
        # Q1 brief fields
        goal: str | None = None,
        context: str | None = None,
        constraints: str | None = None,
        desired_output: str | None = None,
        template_id: UUID | None = None,
        agent_template_id: UUID | None = None,
        risk_level: str | None = None,
        # For reconstitution from persistence:
        id: UUID | None = None,
        task_status: TaskStatus = TaskStatus.DRAFT,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not title or not title.strip():
            raise DomainValidationError("Task", "title must not be blank")
        if risk_level and risk_level not in VALID_RISK_LEVELS:
            raise DomainValidationError("Task", f"invalid risk_level: {risk_level}")

        now = datetime.now(timezone.utc)
        self.id = id or uuid4()
        self.workspace_id = workspace_id
        self.title = title
        self.description = description
        self.task_type = task_type
        self.task_status = task_status
        self.input_config = input_config or {}
        self.repo_snapshot_id = repo_snapshot_id
        self.policy_id = policy_id
        self.parent_task_id = parent_task_id
        self.created_by_id = created_by_id
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self._init_brief(goal, context, constraints, desired_output,
                         template_id, agent_template_id, risk_level)

    def _init_brief(
        self,
        goal: str | None,
        context: str | None,
        constraints: str | None,
        desired_output: str | None,
        template_id: UUID | None,
        agent_template_id: UUID | None,
        risk_level: str | None,
    ) -> None:
        """Initialize Q1 brief fields."""
        self.goal = goal
        self.context = context
        self.constraints = constraints
        self.desired_output = desired_output
        self.template_id = template_id
        self.agent_template_id = agent_template_id
        self.risk_level = risk_level

    # ── Brief mutation ──────────────────────────────────────────

    def update_brief(self, **fields: Any) -> None:
        """Update brief fields on a draft task. Only allowed in DRAFT status."""
        if self.task_status != TaskStatus.DRAFT:
            raise DomainValidationError(
                "Task", f"cannot update brief in status {self.task_status.value}"
            )
        allowed = {
            'title', 'goal', 'context', 'constraints',
            'desired_output', 'description', 'template_id',
            'agent_template_id', 'risk_level',
        }
        for key, value in fields.items():
            if key not in allowed:
                raise DomainValidationError("Task", f"cannot update field: {key}")
            if key == 'title' and (not value or not value.strip()):
                raise DomainValidationError("Task", "title must not be blank")
            if key == 'risk_level' and value and value not in ('low', 'medium', 'high'):
                raise DomainValidationError("Task", f"invalid risk_level: {value}")
            setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)

    # ── Transition helpers ──────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Task) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def _transition(self, target: TaskStatus) -> TaskStatus:
        """Execute a state transition, returning the previous status.

        Raises InvalidTransitionError or TerminalStateError.
        """
        current = self.task_status
        if current in _TASK_TERMINAL:
            raise TerminalStateError("Task", current.value, target.value)
        allowed = _TASK_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("Task", current.value, target.value)
        self.task_status = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ───────────────────────────────────

    def submit(self) -> TaskStatus:
        """draft → pending"""
        return self._transition(TaskStatus.PENDING)

    def start(self) -> TaskStatus:
        """pending → running  (side effect: orchestrator creates first Run)"""
        return self._transition(TaskStatus.RUNNING)

    def request_approval(self) -> TaskStatus:
        """running → waiting_approval"""
        return self._transition(TaskStatus.WAITING_APPROVAL)

    def approve(self) -> TaskStatus:
        """waiting_approval → running"""
        return self._transition(TaskStatus.RUNNING)

    def complete(self) -> TaskStatus:
        """running → completed"""
        return self._transition(TaskStatus.COMPLETED)

    def fail(self) -> TaskStatus:
        """running → failed"""
        return self._transition(TaskStatus.FAILED)

    def cancel(self) -> TaskStatus:
        """draft/pending/running/waiting_approval → cancelled

        Side effect: all active Runs must be cancelled (cascade).
        """
        return self._transition(TaskStatus.CANCELLED)

    def retry(self) -> TaskStatus:
        """failed → pending  (side effect: orchestrator creates new Run, no resume)"""
        return self._transition(TaskStatus.PENDING)

    def archive(self) -> TaskStatus:
        """completed/failed/cancelled → archived"""
        return self._transition(TaskStatus.ARCHIVED)

    # ── Query helpers ───────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.task_status in _TASK_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.task_status in (
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.WAITING_APPROVAL,
        )
