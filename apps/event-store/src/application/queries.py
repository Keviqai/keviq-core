"""Query handlers for event-store timeline APIs.

Read-only operations — never mutate state.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.domain.event import StoredEvent

from .ports import EventRepository


def get_task_timeline(
    task_id: UUID,
    workspace_id: UUID,
    repo: EventRepository,
    after: datetime | None = None,
    limit: int = 100,
) -> list[StoredEvent]:
    """Get ordered events for a task scoped to a workspace."""
    return repo.list_by_task(task_id, workspace_id, after=after, limit=min(limit, 500))


def get_run_timeline(
    run_id: UUID,
    workspace_id: UUID,
    repo: EventRepository,
    after: datetime | None = None,
    limit: int = 100,
) -> list[StoredEvent]:
    """Get ordered events for a run scoped to a workspace."""
    return repo.list_by_run(run_id, workspace_id, after=after, limit=min(limit, 500))


def get_workspace_events(
    workspace_id: UUID,
    repo: EventRepository,
    after_event_id: UUID | None = None,
    limit: int = 100,
) -> list[StoredEvent]:
    """Get events for a workspace (for SSE replay)."""
    return repo.list_by_workspace(
        workspace_id, after_event_id=after_event_id, limit=min(limit, 500),
    )


def get_workspace_activity(
    workspace_id: UUID,
    repo: EventRepository,
    *,
    event_type: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[StoredEvent], int]:
    """Get workspace activity feed (newest first) with total count."""
    return repo.list_workspace_activity(
        workspace_id,
        event_type=event_type,
        after=after,
        before=before,
        limit=min(limit, 100),
        offset=min(offset, 10000),
    )


def get_run_events_after(
    run_id: UUID,
    workspace_id: UUID,
    repo: EventRepository,
    after_event_id: UUID | None = None,
    limit: int = 100,
) -> list[StoredEvent]:
    """Get events for a run scoped to a workspace after a specific event (for SSE replay)."""
    return repo.list_by_run_after_event(
        run_id, workspace_id, after_event_id=after_event_id, limit=min(limit, 500),
    )
