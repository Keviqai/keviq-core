"""SQLAlchemy repository implementations for terminal sessions and commands."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import TerminalCommandRepository, TerminalSessionRepository
from src.domain.terminal_command import TerminalCommand
from src.domain.terminal_session import TerminalCommandStatus, TerminalSession, TerminalSessionStatus

from .terminal_models import TerminalCommandRow, TerminalSessionRow


# -- Mapping helpers ------------------------------------------------------

def _session_to_row(s: TerminalSession) -> dict:
    return {
        "id": str(s.id),
        "sandbox_id": str(s.sandbox_id),
        "run_id": str(s.run_id),
        "workspace_id": str(s.workspace_id),
        "user_id": s.user_id,
        "status": s.status.value,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "closed_at": s.closed_at,
    }


def _row_to_session(row: TerminalSessionRow) -> TerminalSession:
    return TerminalSession(
        id=UUID(row.id),
        sandbox_id=UUID(row.sandbox_id),
        run_id=UUID(row.run_id),
        workspace_id=UUID(row.workspace_id),
        user_id=row.user_id,
        status=TerminalSessionStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
    )


def _command_to_row(c: TerminalCommand) -> dict:
    return {
        "id": str(c.id),
        "session_id": str(c.session_id),
        "command": c.command,
        "stdout": c.stdout,
        "stderr": c.stderr,
        "exit_code": c.exit_code,
        "status": c.status.value,
        "created_at": c.created_at,
        "completed_at": c.completed_at,
    }


def _row_to_command(row: TerminalCommandRow) -> TerminalCommand:
    return TerminalCommand(
        id=UUID(row.id),
        session_id=UUID(row.session_id),
        command=row.command,
        stdout=row.stdout or "",
        stderr=row.stderr or "",
        exit_code=row.exit_code,
        status=TerminalCommandStatus(row.status),
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


# -- Repositories ---------------------------------------------------------


class SqlTerminalSessionRepository(TerminalSessionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, ts: TerminalSession) -> None:
        data = _session_to_row(ts)
        stmt = pg_insert(TerminalSessionRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, session_id: UUID) -> TerminalSession | None:
        row = self._session.get(TerminalSessionRow, str(session_id))
        if row is None:
            return None
        return _row_to_session(row)

    def get_active_by_run(self, run_id: UUID) -> TerminalSession | None:
        stmt = (
            select(TerminalSessionRow)
            .where(
                TerminalSessionRow.run_id == str(run_id),
                TerminalSessionRow.status == TerminalSessionStatus.ACTIVE.value,
            )
            .limit(1)
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return _row_to_session(row)


class SqlTerminalCommandRepository(TerminalCommandRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, command: TerminalCommand) -> None:
        data = _command_to_row(command)
        stmt = pg_insert(TerminalCommandRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def list_by_session(
        self, session_id: UUID, *, limit: int = 100,
    ) -> list[TerminalCommand]:
        stmt = (
            select(TerminalCommandRow)
            .where(TerminalCommandRow.session_id == str(session_id))
            .order_by(TerminalCommandRow.created_at.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_command(r) for r in rows]

    def has_running(self, session_id: UUID) -> bool:
        stmt = (
            select(TerminalCommandRow.id)
            .where(
                TerminalCommandRow.session_id == str(session_id),
                TerminalCommandRow.status == TerminalCommandStatus.RUNNING.value,
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalars().first() is not None
