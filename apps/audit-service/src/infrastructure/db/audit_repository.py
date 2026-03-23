"""Audit repository — raw SQL implementation for audit_core.audit_events."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.domain.audit_event import AuditEvent
from src.application.ports import AuditRepository

SCHEMA = 'audit_core'

_SELECT_COLS = (
    'event_id, actor_id, actor_type, action, target_id, target_type, '
    'workspace_id, metadata, occurred_at'
)


def _row_to_dict(row) -> dict:
    return {
        'event_id': str(row.event_id),
        'actor_id': row.actor_id,
        'actor_type': row.actor_type,
        'action': row.action,
        'target_id': row.target_id,
        'target_type': row.target_type,
        'workspace_id': str(row.workspace_id),
        'metadata': dict(row.metadata) if row.metadata else {},
        'occurred_at': row.occurred_at.isoformat() if hasattr(row.occurred_at, 'isoformat') else str(row.occurred_at),
    }


def insert(db: Session, event: AuditEvent) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.audit_events
                (event_id, actor_id, actor_type, action, target_id, target_type,
                 workspace_id, metadata, occurred_at)
            VALUES
                (:event_id, :actor_id, :actor_type, :action, :target_id, :target_type,
                 :workspace_id, CAST(:metadata AS jsonb), :occurred_at)
            ON CONFLICT (event_id) DO NOTHING
            RETURNING {_SELECT_COLS}
        """),
        {
            'event_id': str(event.event_id),
            'actor_id': event.actor_id,
            'actor_type': event.actor_type,
            'action': event.action,
            'target_id': event.target_id,
            'target_type': event.target_type,
            'workspace_id': str(event.workspace_id),
            'metadata': json.dumps(event.metadata),
            'occurred_at': event.occurred_at,
        },
    ).fetchone()
    db.commit()

    if row is None:
        # Duplicate event_id — idempotent, return minimal dict
        return {
            'event_id': str(event.event_id),
            'actor_id': event.actor_id,
            'actor_type': event.actor_type,
            'action': event.action,
            'target_id': event.target_id,
            'target_type': event.target_type,
            'workspace_id': str(event.workspace_id),
            'metadata': event.metadata,
            'occurred_at': event.occurred_at.isoformat(),
        }
    return _row_to_dict(row)


def find_by_workspace(
    db: Session,
    workspace_id: UUID,
    *,
    action: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conditions = ['workspace_id = :workspace_id']
    params: dict = {'workspace_id': str(workspace_id), 'limit': limit, 'offset': offset}

    if action:
        conditions.append('action = :action')
        params['action'] = action
    if actor_id:
        conditions.append('actor_id = :actor_id')
        params['actor_id'] = actor_id
    if target_id:
        conditions.append('target_id = :target_id')
        params['target_id'] = target_id

    where = ' AND '.join(conditions)
    rows = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.audit_events
            WHERE {where}
            ORDER BY occurred_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


class AuditRepositoryAdapter(AuditRepository):
    def insert(self, db, event: AuditEvent) -> dict:
        return insert(db, event)

    def find_by_workspace(self, db, workspace_id, *, action=None, actor_id=None,
                          target_id=None, limit=50, offset=0) -> list[dict]:
        return find_by_workspace(
            db, workspace_id, action=action, actor_id=actor_id,
            target_id=target_id, limit=limit, offset=offset,
        )
