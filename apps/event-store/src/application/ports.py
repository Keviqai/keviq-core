"""Application-layer port interfaces for event-store.

Infrastructure layer implements these.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from src.domain.event import StoredEvent


class EventRepository(ABC):
    """Append-only event store."""

    @abstractmethod
    def ingest(self, event: StoredEvent) -> bool:
        """Ingest an event. Returns True if new, False if duplicate (idempotent)."""
        ...

    @abstractmethod
    def ingest_batch(self, events: list[StoredEvent]) -> list[bool]:
        """Ingest multiple events in a single transaction. Returns list of is_new flags."""
        ...

    @abstractmethod
    def list_by_task(
        self,
        task_id: UUID,
        workspace_id: UUID,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Get events for a task scoped to a workspace, ordered by occurred_at."""
        ...

    @abstractmethod
    def list_by_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
        after: datetime | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Get events for a run scoped to a workspace, ordered by occurred_at."""
        ...

    @abstractmethod
    def list_by_workspace(
        self,
        workspace_id: UUID,
        after_event_id: UUID | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Get events for a workspace, ordered by occurred_at.

        If after_event_id is provided, return events after that event.
        Used for SSE Last-Event-ID replay.
        """
        ...

    @abstractmethod
    def list_by_run_after_event(
        self,
        run_id: UUID,
        workspace_id: UUID,
        after_event_id: UUID | None = None,
        limit: int = 100,
    ) -> list[StoredEvent]:
        """Get events for a run scoped to a workspace after a specific event ID.

        Used for run-scoped SSE Last-Event-ID replay.
        """
        ...

    @abstractmethod
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
        """Get workspace activity feed (newest first) with total count.

        Optional filters: event_type prefix, time range.
        """
        ...

    @abstractmethod
    def get_by_id(self, event_id: UUID) -> StoredEvent | None:
        """Get a single event by ID."""
        ...

    def close(self) -> None:
        """Release underlying resources (session, connection)."""
