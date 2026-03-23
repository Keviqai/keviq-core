"""SQL implementation of EventRepository — append-only event store."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.application.ports import EventRepository
from src.domain.event import StoredEvent

from .models import EventRow


def _row_to_domain(row: EventRow) -> StoredEvent:
    return StoredEvent(
        id=UUID(str(row.id)),
        event_type=row.event_type,
        schema_version=row.schema_version,
        workspace_id=UUID(str(row.workspace_id)),
        task_id=UUID(str(row.task_id)) if row.task_id else None,
        run_id=UUID(str(row.run_id)) if row.run_id else None,
        step_id=UUID(str(row.step_id)) if row.step_id else None,
        correlation_id=UUID(str(row.correlation_id)),
        causation_id=UUID(str(row.causation_id)) if row.causation_id else None,
        occurred_at=row.occurred_at,
        emitted_by=row.emitted_by,
        actor=row.actor,
        payload=row.payload,
        received_at=row.received_at,
    )


class SqlEventRepository(EventRepository):
    def __init__(self, session: Session):
        self._session = session

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def ingest(self, event: StoredEvent) -> bool:
        """Insert event. ON CONFLICT DO NOTHING for idempotency.

        Returns True if event was new, False if duplicate.
        """
        result = self._execute_insert(event)
        self._session.commit()
        return result.rowcount > 0

    def ingest_batch(self, events: list[StoredEvent]) -> list[bool]:
        """Insert multiple events in a single transaction.

        Returns list of booleans — True if new, False if duplicate.
        """
        results = []
        for event in events:
            result = self._execute_insert(event)
            results.append(result.rowcount > 0)
        self._session.commit()
        return results

    def _execute_insert(self, event: StoredEvent):
        """Execute an INSERT ... ON CONFLICT DO NOTHING for a single event."""
        stmt = (
            insert(EventRow)
            .values(
                id=str(event.id),
                event_type=event.event_type,
                schema_version=event.schema_version,
                workspace_id=str(event.workspace_id),
                task_id=str(event.task_id) if event.task_id else None,
                run_id=str(event.run_id) if event.run_id else None,
                step_id=str(event.step_id) if event.step_id else None,
                correlation_id=str(event.correlation_id),
                causation_id=str(event.causation_id) if event.causation_id else None,
                occurred_at=event.occurred_at,
                emitted_by=event.emitted_by,
                actor=event.actor,
                payload=event.payload,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        return self._session.execute(stmt)

    def list_by_task(
        self,
        task_id: UUID,
        workspace_id: UUID,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        stmt = (
            select(EventRow)
            .where(EventRow.task_id == str(task_id))
            .where(EventRow.workspace_id == str(workspace_id))
        )
        if after:
            stmt = stmt.where(EventRow.occurred_at > after)
        stmt = stmt.order_by(EventRow.occurred_at, EventRow.id).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_domain(r) for r in rows]

    def list_by_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        stmt = (
            select(EventRow)
            .where(EventRow.run_id == str(run_id))
            .where(EventRow.workspace_id == str(workspace_id))
        )
        if after:
            stmt = stmt.where(EventRow.occurred_at > after)
        stmt = stmt.order_by(EventRow.occurred_at, EventRow.id).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_domain(r) for r in rows]

    def list_by_workspace(
        self,
        workspace_id: UUID,
        after_event_id: UUID | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        stmt = select(EventRow).where(
            EventRow.workspace_id == str(workspace_id)
        )
        if after_event_id:
            # Find the occurred_at of the reference event, scoped to same workspace
            ref = self._session.execute(
                select(EventRow.occurred_at, EventRow.id)
                .where(EventRow.id == str(after_event_id))
                .where(EventRow.workspace_id == str(workspace_id))
            ).first()
            if ref is None:
                return []  # Unknown Last-Event-ID — empty result
            stmt = stmt.where(
                (EventRow.occurred_at > ref[0])
                | ((EventRow.occurred_at == ref[0]) & (EventRow.id > str(after_event_id)))
            )
        stmt = stmt.order_by(EventRow.occurred_at, EventRow.id).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_domain(r) for r in rows]

    def list_by_run_after_event(
        self,
        run_id: UUID,
        workspace_id: UUID,
        after_event_id: UUID | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        stmt = select(EventRow).where(
            EventRow.run_id == str(run_id),
            EventRow.workspace_id == str(workspace_id),
        )
        if after_event_id:
            ref = self._session.execute(
                select(EventRow.occurred_at, EventRow.id)
                .where(EventRow.id == str(after_event_id))
                .where(EventRow.workspace_id == str(workspace_id))
            ).first()
            if ref is None:
                return []
            stmt = stmt.where(
                (EventRow.occurred_at > ref[0])
                | ((EventRow.occurred_at == ref[0]) & (EventRow.id > str(after_event_id)))
            )
        stmt = stmt.order_by(EventRow.occurred_at, EventRow.id).limit(limit)
        rows = self._session.execute(stmt).scalars().all()
        return [_row_to_domain(r) for r in rows]

    def list_workspace_activity(
        self,
        workspace_id: UUID,
        *,
        event_type: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[StoredEvent], int]:
        """Workspace activity feed — newest first, with filters and total count."""
        base = select(EventRow).where(
            EventRow.workspace_id == str(workspace_id)
        )
        if event_type:
            base = base.where(EventRow.event_type.like(f"{event_type}%"))
        if after:
            base = base.where(EventRow.occurred_at > after)
        if before:
            base = base.where(EventRow.occurred_at < before)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = self._session.execute(count_stmt).scalar() or 0

        query = base.order_by(
            EventRow.occurred_at.desc(), EventRow.id.desc(),
        ).limit(limit).offset(offset)
        rows = self._session.execute(query).scalars().all()
        return [_row_to_domain(r) for r in rows], total

    def get_by_id(self, event_id: UUID) -> StoredEvent | None:
        row = self._session.execute(
            select(EventRow).where(EventRow.id == str(event_id))
        ).scalar_one_or_none()
        return _row_to_domain(row) if row else None
