"""SQLAlchemy-backed Unit of Work.

Ensures state mutations and outbox writes share the same transaction.
If either fails, both are rolled back — no orphan events, no uncommitted state.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from src.application.ports import UnitOfWork

from .repositories import SqlExecutionAttemptRepository, SqlSandboxRepository
from .terminal_repository import SqlTerminalCommandRepository, SqlTerminalSessionRepository
from ..outbox.writer import SqlOutboxWriter


class SqlUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def __enter__(self) -> SqlUnitOfWork:
        self._session: Session = self._session_factory()
        self.sandboxes = SqlSandboxRepository(self._session)
        self.attempts = SqlExecutionAttemptRepository(self._session)
        self.terminal_sessions = SqlTerminalSessionRepository(self._session)
        self.terminal_commands = SqlTerminalCommandRepository(self._session)
        self.outbox = SqlOutboxWriter(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
