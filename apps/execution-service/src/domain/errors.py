"""Domain errors for execution-service."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all execution-service domain errors."""


class InvalidTransitionError(DomainError):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(
        self, entity: str, current: str, target: str,
        reason: str | None = None,
    ):
        self.entity = entity
        self.current_status = current
        self.target_status = target
        self.reason = reason
        msg = f"{entity}: transition {current!r} → {target!r} is not allowed"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class TerminalStateError(InvalidTransitionError):
    """Raised when attempting to transition from a terminal state."""

    def __init__(self, entity: str, current: str, target: str):
        super().__init__(entity, current, target, reason="terminal state")


class SandboxBusyError(DomainError):
    """Raised when a sandbox is already claimed for execution.

    Indicates a concurrent execution attempt on a sandbox that is
    not in READY/IDLE state — typically because another caller
    already claimed it.
    """

    def __init__(self, sandbox_id: str, current_status: str):
        self.sandbox_id = sandbox_id
        self.current_status = current_status
        super().__init__(
            f"Sandbox {sandbox_id} is busy (status={current_status!r})"
        )


class DomainValidationError(DomainError):
    """Raised when domain validation fails."""

    def __init__(self, entity: str, message: str):
        self.entity = entity
        super().__init__(f"{entity}: {message}")
