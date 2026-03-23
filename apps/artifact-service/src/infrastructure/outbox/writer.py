"""Outbox writer — writes events to the artifact-service outbox table.

Uses the same SQLAlchemy session as the repositories,
ensuring state mutation + event write share one transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.application.events import OutboxEvent
from src.application.ports import OutboxWriter
from src.infrastructure.db.models import OutboxRow


class SqlOutboxWriter(OutboxWriter):
    def __init__(self, session: Session):
        self._session = session

    def write(self, event: OutboxEvent) -> None:
        row = OutboxRow(
            id=str(event.event_id),
            event_type=event.event_type,
            payload={
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "schema_version": "1.0",
                "workspace_id": str(event.workspace_id),
                "artifact_id": str(event.artifact_id) if event.artifact_id else None,
                "run_id": str(event.run_id) if event.run_id else None,
                "correlation_id": str(event.correlation_id),
                "causation_id": str(event.causation_id) if event.causation_id else None,
                "occurred_at": event.occurred_at.isoformat(),
                "emitted_by": {"service": "artifact-service", "instance_id": "local"},
                "actor": {"type": "system", "id": "artifact-service"},
                "payload": event.payload,
            },
            correlation_id=str(event.correlation_id),
            created_at=event.occurred_at,
        )
        self._session.add(row)
