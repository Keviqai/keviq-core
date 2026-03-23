"""Terminal command record — value object for command execution history.

Each record captures a single command execution within a terminal session:
the command string, output, exit code, and timing metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.domain.terminal_session import TerminalCommandStatus


class TerminalCommand:
    """Record of a single terminal command execution."""

    __slots__ = (
        "id",
        "session_id",
        "command",
        "stdout",
        "stderr",
        "exit_code",
        "status",
        "created_at",
        "completed_at",
    )

    def __init__(
        self,
        *,
        id: UUID,
        session_id: UUID,
        command: str,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = None,
        status: TerminalCommandStatus = TerminalCommandStatus.RUNNING,
        created_at: datetime | None = None,
        completed_at: datetime | None = None,
    ):
        now = datetime.now(timezone.utc)
        self.id = id
        self.session_id = session_id
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.status = status
        self.created_at = created_at or now
        self.completed_at = completed_at

    def mark_completed(
        self, *, stdout: str, stderr: str, exit_code: int,
    ) -> None:
        """Mark command as successfully completed."""
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.status = TerminalCommandStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, *, error_message: str) -> None:
        """Mark command as failed (sandbox error, not exit code)."""
        self.stderr = error_message
        self.status = TerminalCommandStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    def mark_timed_out(self, *, timeout_s: int) -> None:
        """Mark command as timed out."""
        self.stderr = f"Command timed out after {timeout_s}s"
        self.status = TerminalCommandStatus.TIMED_OUT
        self.completed_at = datetime.now(timezone.utc)
