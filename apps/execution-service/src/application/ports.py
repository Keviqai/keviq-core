"""Application-layer port interfaces (abstractions).

Infrastructure layer implements these. Application layer depends on these only.
No SQLAlchemy, no FastAPI, no Docker imports allowed here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.sandbox import Sandbox
    from src.domain.terminal_command import TerminalCommand
    from src.domain.terminal_session import TerminalSession

    from .events import OutboxEvent


# ── Repository ───────────────────────────────────────────────


class SandboxRepository(ABC):
    @abstractmethod
    def save(self, sandbox: Sandbox) -> None: ...

    @abstractmethod
    def get_by_id(self, sandbox_id: UUID) -> Sandbox | None: ...

    @abstractmethod
    def get_by_invocation(self, agent_invocation_id: UUID) -> Sandbox | None: ...

    @abstractmethod
    def list_active(self, limit: int = 50) -> list[Sandbox]: ...

    @abstractmethod
    def get_by_id_for_update(self, sandbox_id: UUID) -> Sandbox | None:
        """Load sandbox with row-level lock (SELECT FOR UPDATE).

        Use when you need a consistent read that serializes against
        concurrent claims or recovery sweeps.
        """
        ...

    @abstractmethod
    def claim_for_execution(self, sandbox_id: UUID) -> Sandbox:
        """Atomically load sandbox with row lock and transition to EXECUTING.

        Uses SELECT ... FOR UPDATE to serialize concurrent claims.
        Raises SandboxBusyError if sandbox is not in READY/IDLE.
        Raises DomainError if sandbox not found.
        """
        ...

    @abstractmethod
    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Sandbox]:
        """Find sandboxes stuck in given statuses since before the cutoff."""
        ...


class ExecutionAttemptRepository(ABC):
    @abstractmethod
    def save(self, attempt_data: dict[str, Any]) -> None: ...

    @abstractmethod
    def get(self, attempt_id: UUID) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_by_sandbox_and_index(
        self, sandbox_id: UUID, attempt_index: int,
    ) -> dict[str, Any] | None: ...


# ── Outbox ───────────────────────────────────────────────────


class OutboxWriter(ABC):
    @abstractmethod
    def write(self, event: OutboxEvent) -> None: ...


# ── Sandbox Backend ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BackendInfo:
    """Metadata returned by sandbox backend after provisioning."""

    container_id: str
    host: str = "localhost"
    port: int = 0


class SandboxBackend(ABC):
    """Port for provisioning/terminating real sandbox instances.

    Implementation can be Docker, subprocess, or remote.
    The backend is NOT part of the DB transaction — it's a side effect.
    """

    @abstractmethod
    def provision(
        self,
        *,
        sandbox_id: UUID,
        sandbox_type: str,
        resource_limits: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> BackendInfo: ...

    @abstractmethod
    def terminate(self, sandbox_id: UUID) -> None: ...

    @abstractmethod
    def is_alive(self, sandbox_id: UUID) -> bool: ...


# ── Tool Execution Backend ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExecResult:
    """Raw result from executing a command in a sandbox container."""

    exit_code: int
    stdout: str
    stderr: str


class ToolExecutionBackend(ABC):
    """Port for executing commands inside sandbox containers.

    Separate from SandboxBackend (lifecycle) to keep concerns clear:
    - SandboxBackend = provision/terminate containers
    - ToolExecutionBackend = run commands inside containers
    """

    @abstractmethod
    def exec_in_sandbox(
        self,
        *,
        sandbox_id: UUID,
        command: list[str],
        timeout_s: int = 30,
    ) -> ExecResult: ...


# ── Unit of Work ─────────────────────────────────────────────


class TerminalSessionRepository(ABC):
    @abstractmethod
    def save(self, session: TerminalSession) -> None: ...

    @abstractmethod
    def get_by_id(self, session_id: UUID) -> TerminalSession | None: ...

    @abstractmethod
    def get_active_by_run(self, run_id: UUID) -> TerminalSession | None:
        """Find the active terminal session for a run, if any."""
        ...


class TerminalCommandRepository(ABC):
    @abstractmethod
    def save(self, command: TerminalCommand) -> None: ...

    @abstractmethod
    def list_by_session(
        self, session_id: UUID, *, limit: int = 100,
    ) -> list[TerminalCommand]: ...

    @abstractmethod
    def has_running(self, session_id: UUID) -> bool:
        """Check if session has any running commands."""
        ...


class UnitOfWork(ABC):
    """Transaction boundary. State mutation + outbox write in same commit."""

    sandboxes: SandboxRepository
    attempts: ExecutionAttemptRepository
    terminal_sessions: TerminalSessionRepository
    terminal_commands: TerminalCommandRepository
    outbox: OutboxWriter

    @abstractmethod
    def __enter__(self) -> UnitOfWork: ...

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
