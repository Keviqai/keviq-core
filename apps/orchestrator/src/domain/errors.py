"""Domain errors for orchestrator service."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class InvalidTransitionError(DomainError):
    """Raised when a state machine transition is not allowed."""

    def __init__(self, entity: str, current: str, target: str, reason: str | None = None):
        self.entity = entity
        self.current_status = current
        self.target_status = target
        self.reason = reason
        msg = f"{entity}: transition {current!r} → {target!r} is not allowed"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class TerminalStateError(InvalidTransitionError):
    """Raised when trying to transition from a terminal state."""

    def __init__(self, entity: str, current: str, target: str):
        super().__init__(entity, current, target, reason="terminal state")


class ImmutableFieldError(DomainError):
    """Raised when trying to modify an immutable field."""

    def __init__(self, entity: str, field: str, reason: str | None = None):
        self.entity = entity
        self.field = field
        msg = f"{entity}: field {field!r} is immutable"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class DomainValidationError(DomainError):
    """Raised when a domain invariant is violated."""

    def __init__(self, entity: str, message: str):
        self.entity = entity
        super().__init__(f"{entity}: {message}")
