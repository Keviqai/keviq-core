"""Terminal session domain entity.

A terminal session represents a user's interactive command-line session
against an active sandbox. Commands are executed one at a time via
POST+JSON (command-response model, not PTY).

Ownership: execution-service (SVC-04).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import UUID

from src.domain.errors import DomainValidationError, InvalidTransitionError


# -- Enums ---------------------------------------------------------------


class TerminalSessionStatus(str, enum.Enum):
    """Terminal session lifecycle states."""
    ACTIVE = "active"
    CLOSED = "closed"


class TerminalCommandStatus(str, enum.Enum):
    """Status of a single terminal command execution."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


# -- State Machine -------------------------------------------------------

_SESSION_TRANSITIONS: dict[TerminalSessionStatus, frozenset[TerminalSessionStatus]] = {
    TerminalSessionStatus.ACTIVE: frozenset({TerminalSessionStatus.CLOSED}),
    TerminalSessionStatus.CLOSED: frozenset(),
}


# -- Entity ---------------------------------------------------------------


class TerminalSession:
    """Terminal session entity.

    Represents an interactive command session bound to a sandbox.
    One session per sandbox at a time. Commands execute sequentially.
    """

    __slots__ = (
        "id",
        "sandbox_id",
        "run_id",
        "workspace_id",
        "user_id",
        "status",
        "created_at",
        "updated_at",
        "closed_at",
    )

    def __init__(
        self,
        *,
        id: UUID,
        sandbox_id: UUID,
        run_id: UUID,
        workspace_id: UUID,
        user_id: str,
        status: TerminalSessionStatus = TerminalSessionStatus.ACTIVE,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        closed_at: datetime | None = None,
    ):
        if not id:
            raise DomainValidationError("TerminalSession", "id is required")
        if not sandbox_id:
            raise DomainValidationError("TerminalSession", "sandbox_id is required")
        if not run_id:
            raise DomainValidationError("TerminalSession", "run_id is required")
        if not workspace_id:
            raise DomainValidationError("TerminalSession", "workspace_id is required")
        if not user_id:
            raise DomainValidationError("TerminalSession", "user_id is required")

        now = datetime.now(timezone.utc)
        self.id = id
        self.sandbox_id = sandbox_id
        self.run_id = run_id
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.status = status
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.closed_at = closed_at

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TerminalSession) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    # -- Transitions ------------------------------------------------------

    def close(self) -> None:
        """Close the terminal session."""
        allowed = _SESSION_TRANSITIONS[self.status]
        target = TerminalSessionStatus.CLOSED
        if target not in allowed:
            raise InvalidTransitionError(
                "TerminalSession", self.status.value, target.value,
            )
        self.status = target
        now = datetime.now(timezone.utc)
        self.updated_at = now
        self.closed_at = now

    # -- Query helpers ----------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status == TerminalSessionStatus.ACTIVE
