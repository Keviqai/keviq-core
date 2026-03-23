"""Terminal session application service.

Manages terminal session lifecycle and command execution.
Reuses DockerExecutionBackend.exec_in_sandbox() for command execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.errors import DomainError
from src.domain.sandbox import SandboxStatus
from src.domain.terminal_command import TerminalCommand
from src.domain.terminal_contracts import CreateTerminalSessionRequest, ExecCommandRequest
from src.domain.terminal_session import TerminalSession

from .events import terminal_command_executed_event
from .ports import ToolExecutionBackend, UnitOfWork

logger = logging.getLogger(__name__)

_MAX_OUTPUT_SIZE = 1_000_000  # 1 MB


def create_session(
    request: CreateTerminalSessionRequest,
    uow: UnitOfWork,
) -> TerminalSession:
    """Create a new terminal session bound to a sandbox."""
    with uow:
        sandbox = uow.sandboxes.get_by_id(request.sandbox_id)
        if sandbox is None:
            raise DomainError(f"Sandbox {request.sandbox_id} not found")

        if sandbox.sandbox_status not in (
            SandboxStatus.READY, SandboxStatus.IDLE,
        ):
            raise DomainError(
                f"Sandbox {request.sandbox_id} is not available "
                f"(status={sandbox.sandbox_status.value})"
            )

        existing = uow.terminal_sessions.get_active_by_run(request.run_id)
        if existing is not None:
            return existing

        session = TerminalSession(
            id=uuid4(),
            sandbox_id=request.sandbox_id,
            run_id=request.run_id,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
        )
        uow.terminal_sessions.save(session)
        uow.commit()

    logger.info(
        "Terminal session %s created (sandbox=%s, run=%s)",
        session.id, request.sandbox_id, request.run_id,
    )
    return session


def execute_command(
    request: ExecCommandRequest,
    uow: UnitOfWork,
    backend: ToolExecutionBackend,
    *,
    user_id: str | None = None,
) -> TerminalCommand:
    """Execute a command in a terminal session's sandbox."""
    command_id = uuid4()
    correlation_id = uuid4()

    with uow:
        session = uow.terminal_sessions.get_by_id(request.session_id)
        if session is None:
            raise DomainError(
                f"Terminal session {request.session_id} not found"
            )
        if user_id is not None and session.user_id != user_id:
            raise DomainError(
                f"Terminal session {request.session_id} not found"
            )
        if not session.is_active:
            raise DomainError(
                f"Terminal session {request.session_id} is closed"
            )
        if uow.terminal_commands.has_running(request.session_id):
            raise DomainError(
                f"Terminal session {request.session_id} already has "
                "a running command"
            )

        workspace_id = session.workspace_id
        sandbox_id = session.sandbox_id

        cmd = TerminalCommand(
            id=command_id,
            session_id=request.session_id,
            command=request.command,
        )
        uow.terminal_commands.save(cmd)
        uow.commit()

    started_at = datetime.now(timezone.utc)

    try:
        exec_result = backend.exec_in_sandbox(
            sandbox_id=sandbox_id,
            command=["sh", "-c", request.command],
            timeout_s=request.timeout_s,
        )
        stdout = exec_result.stdout
        stderr = exec_result.stderr
        if len(stdout) > _MAX_OUTPUT_SIZE:
            stdout = stdout[:_MAX_OUTPUT_SIZE]
        if len(stderr) > _MAX_OUTPUT_SIZE:
            stderr = stderr[:_MAX_OUTPUT_SIZE]

        cmd.mark_completed(
            stdout=stdout,
            stderr=stderr,
            exit_code=exec_result.exit_code,
        )
    except TimeoutError:
        cmd.mark_timed_out(timeout_s=request.timeout_s)
    except Exception as exc:
        logger.error("Terminal exec error: %s", exc)
        cmd.mark_failed(error_message=str(exc))

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    with uow:
        uow.terminal_commands.save(cmd)
        uow.outbox.write(terminal_command_executed_event(
            sandbox_id=sandbox_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            session_id=request.session_id,
            command_id=command_id,
            command=request.command,
            exit_code=cmd.exit_code,
            duration_ms=duration_ms,
        ))
        uow.commit()

    return cmd


def get_session(
    session_id: UUID,
    uow: UnitOfWork,
    *,
    user_id: str | None = None,
) -> TerminalSession:
    """Get a terminal session by ID. Raises DomainError if not found.

    If user_id is provided, validates ownership.
    """
    with uow:
        session = uow.terminal_sessions.get_by_id(session_id)
        if session is None:
            raise DomainError(f"Terminal session {session_id} not found")
        if user_id is not None and session.user_id != user_id:
            raise DomainError(f"Terminal session {session_id} not found")
        return session


def get_session_by_run(
    run_id: UUID,
    uow: UnitOfWork,
) -> TerminalSession | None:
    """Get active terminal session for a run, or None."""
    with uow:
        return uow.terminal_sessions.get_active_by_run(run_id)


def list_commands(
    session_id: UUID,
    uow: UnitOfWork,
    *,
    user_id: str | None = None,
    limit: int = 100,
) -> list[TerminalCommand]:
    """List command history for a session."""
    with uow:
        session = uow.terminal_sessions.get_by_id(session_id)
        if session is None:
            raise DomainError(f"Terminal session {session_id} not found")
        if user_id is not None and session.user_id != user_id:
            raise DomainError(f"Terminal session {session_id} not found")
        return uow.terminal_commands.list_by_session(session_id, limit=limit)


def close_session(
    session_id: UUID,
    uow: UnitOfWork,
    *,
    user_id: str | None = None,
) -> TerminalSession:
    """Close a terminal session."""
    with uow:
        session = uow.terminal_sessions.get_by_id(session_id)
        if session is None:
            raise DomainError(f"Terminal session {session_id} not found")
        if user_id is not None and session.user_id != user_id:
            raise DomainError(f"Terminal session {session_id} not found")
        session.close()
        uow.terminal_sessions.save(session)
        uow.commit()

    logger.info("Terminal session %s closed", session_id)
    return session
