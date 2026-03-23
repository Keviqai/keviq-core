"""Domain model for stored events.

Pure data — no infrastructure imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """An event that has been ingested into the event store."""

    id: UUID  # event_id from source
    event_type: str
    schema_version: str
    workspace_id: UUID
    task_id: UUID | None
    run_id: UUID | None
    step_id: UUID | None
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime
    emitted_by: dict[str, str]
    actor: dict[str, str]
    payload: dict[str, Any]
    received_at: datetime


def event_to_dict(event: StoredEvent) -> dict[str, Any]:
    """Serialize a StoredEvent to dict for API response."""
    result: dict[str, Any] = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "workspace_id": str(event.workspace_id),
        "correlation_id": str(event.correlation_id),
        "occurred_at": event.occurred_at.isoformat(),
        "emitted_by": event.emitted_by,
        "actor": event.actor,
        "payload": event.payload,
        "received_at": event.received_at.isoformat(),
    }
    if event.task_id:
        result["task_id"] = str(event.task_id)
    if event.run_id:
        result["run_id"] = str(event.run_id)
    if event.step_id:
        result["step_id"] = str(event.step_id)
    if event.causation_id:
        result["causation_id"] = str(event.causation_id)
    return result
