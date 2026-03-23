"""Terminal session contracts — request/response DTOs.

Transport-agnostic value objects for terminal session operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateTerminalSessionRequest:
    """Request to create a new terminal session."""
    sandbox_id: UUID
    run_id: UUID
    workspace_id: UUID
    user_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], user_id: str) -> CreateTerminalSessionRequest:
        return cls(
            sandbox_id=UUID(data["sandbox_id"]),
            run_id=UUID(data["run_id"]),
            workspace_id=UUID(data["workspace_id"]),
            user_id=user_id,
        )


@dataclass(frozen=True, slots=True)
class ExecCommandRequest:
    """Request to execute a command in a terminal session."""
    session_id: UUID
    command: str
    timeout_s: int = 30

    MAX_COMMAND_LENGTH = 10_000

    @classmethod
    def from_dict(cls, data: dict[str, Any], session_id: UUID) -> ExecCommandRequest:
        command = data["command"]
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        if len(command) > cls.MAX_COMMAND_LENGTH:
            raise ValueError(
                f"command exceeds maximum length of {cls.MAX_COMMAND_LENGTH} chars"
            )
        timeout = min(data.get("timeout_s", 30), 120)
        return cls(
            session_id=session_id,
            command=command,
            timeout_s=max(1, timeout),
        )
