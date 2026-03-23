"""Outbox repository — insert event rows into workspace_core.outbox."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SCHEMA = 'workspace_core'
SERVICE_NAME = 'workspace-service'
INSTANCE_ID = os.getenv('HOSTNAME', 'workspace-service-local')


def insert_event(
    db: Session,
    event_type: str,
    workspace_id: uuid.UUID,
    payload: dict,
    correlation_id: uuid.UUID,
    actor_id: str,
    actor_type: str = 'user',
    causation_id: uuid.UUID | None = None,
) -> None:
    """Insert an event into the outbox (same transaction as the caller)."""
    now = datetime.now(timezone.utc)
    event_id = uuid.uuid4()

    envelope = {
        'event_id': str(event_id),
        'event_type': event_type,
        'schema_version': '1.0',
        'workspace_id': str(workspace_id),
        'task_id': None,
        'run_id': None,
        'step_id': None,
        'agent_invocation_id': None,
        'sandbox_id': None,
        'artifact_id': None,
        'correlation_id': str(correlation_id),
        'causation_id': str(causation_id) if causation_id else None,
        'occurred_at': now.isoformat(),
        'emitted_by': {
            'service': SERVICE_NAME,
            'instance_id': INSTANCE_ID,
        },
        'actor': {
            'type': actor_type,
            'id': actor_id,
        },
        'payload': payload,
    }

    db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.outbox
                (id, event_type, payload, correlation_id, created_at)
            VALUES
                (:id, :event_type, :payload, :correlation_id, :created_at)
        """),
        {
            'id': str(event_id),
            'event_type': event_type,
            'payload': json.dumps(envelope),
            'correlation_id': str(correlation_id),
            'created_at': now,
        },
    )


from src.application.ports import OutboxWriter as OutboxWriterPort


class OutboxWriterAdapter(OutboxWriterPort):
    """Infrastructure adapter implementing OutboxWriter port."""

    def insert_event(self, db, event_type, workspace_id, payload, correlation_id, actor_id, actor_type='user', causation_id=None):
        return insert_event(db, event_type, workspace_id, payload, correlation_id, actor_id, actor_type=actor_type, causation_id=causation_id)
