"""SQLAlchemy repository implementations.

All writes go through execution_core schema only (S1 principle).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import ExecutionAttemptRepository, SandboxRepository
from src.domain.errors import DomainError, SandboxBusyError
from src.domain.sandbox import Sandbox, SandboxStatus

from .mapping import attempt_row_to_dict, sandbox_domain_to_row, sandbox_row_to_domain
from .models import SandboxAttemptRow, SandboxRow


class SqlSandboxRepository(SandboxRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, sandbox: Sandbox) -> None:
        data = sandbox_domain_to_row(sandbox)
        stmt = pg_insert(SandboxRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, sandbox_id: UUID) -> Sandbox | None:
        row = self._session.get(SandboxRow, str(sandbox_id))
        if row is None:
            return None
        return sandbox_row_to_domain(row)

    def get_by_invocation(self, agent_invocation_id: UUID) -> Sandbox | None:
        stmt = select(SandboxRow).where(
            SandboxRow.agent_invocation_id == str(agent_invocation_id),
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return sandbox_row_to_domain(row)

    def list_active(self, limit: int = 50) -> list[Sandbox]:
        terminal_statuses = [
            SandboxStatus.TERMINATED.value,
            SandboxStatus.FAILED.value,
        ]
        stmt = (
            select(SandboxRow)
            .where(SandboxRow.sandbox_status.notin_(terminal_statuses))
            .order_by(SandboxRow.created_at.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [sandbox_row_to_domain(r) for r in rows]

    def get_by_id_for_update(self, sandbox_id: UUID) -> Sandbox | None:
        stmt = (
            select(SandboxRow)
            .where(SandboxRow.id == str(sandbox_id))
            .with_for_update()
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return sandbox_row_to_domain(row)

    def claim_for_execution(self, sandbox_id: UUID) -> Sandbox:
        """Atomically load + lock sandbox row and transition to EXECUTING.

        Uses SELECT ... FOR UPDATE to serialize concurrent claims.
        """
        stmt = (
            select(SandboxRow)
            .where(SandboxRow.id == str(sandbox_id))
            .with_for_update()
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            raise DomainError(f"Sandbox {sandbox_id} not found")

        sandbox = sandbox_row_to_domain(row)

        if sandbox.sandbox_status not in (SandboxStatus.READY, SandboxStatus.IDLE):
            raise SandboxBusyError(str(sandbox_id), sandbox.sandbox_status.value)

        sandbox.mark_executing()
        self.save(sandbox)
        return sandbox

    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Sandbox]:
        """Find sandboxes stuck in given statuses since before the cutoff."""
        stmt = (
            select(SandboxRow)
            .where(
                SandboxRow.sandbox_status.in_(statuses),
                SandboxRow.updated_at < stuck_before,
            )
            .order_by(SandboxRow.updated_at.asc())
            .limit(100)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [sandbox_row_to_domain(r) for r in rows]


class SqlExecutionAttemptRepository(ExecutionAttemptRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, attempt_data: dict[str, Any]) -> None:
        stmt = pg_insert(SandboxAttemptRow).values(**attempt_data).on_conflict_do_update(
            constraint="uq_sandbox_attempts_sandbox_attempt",
            set_={k: v for k, v in attempt_data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get(self, attempt_id: UUID) -> dict[str, Any] | None:
        row = self._session.get(SandboxAttemptRow, str(attempt_id))
        if row is None:
            return None
        return attempt_row_to_dict(row)

    def get_by_sandbox_and_index(
        self, sandbox_id: UUID, attempt_index: int,
    ) -> dict[str, Any] | None:
        stmt = select(SandboxAttemptRow).where(
            SandboxAttemptRow.sandbox_id == str(sandbox_id),
            SandboxAttemptRow.attempt_index == attempt_index,
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return attempt_row_to_dict(row)
