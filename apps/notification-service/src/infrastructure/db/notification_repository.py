"""Notification repository — database access for notification_core tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SCHEMA = 'notification_core'

_MAX_LIMIT = 200

_SELECT_COLS = (
    'id, workspace_id, user_id, title, body, category, '
    'priority, link, is_read, created_at, read_at, '
    'delivery_status, delivery_attempts, last_delivery_error, delivered_at'
)


def find_by_workspace_user(
    db: Session, workspace_id: uuid.UUID, user_id: str,
    *, is_read: bool | None = None, delivery_status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    where = 'WHERE workspace_id = :workspace_id AND user_id = :user_id'
    params: dict = {
        'workspace_id': str(workspace_id),
        'user_id': user_id,
        'limit': limit,
        'offset': offset,
    }
    if is_read is not None:
        where += ' AND is_read = :is_read'
        params['is_read'] = is_read
    if delivery_status is not None:
        where += ' AND delivery_status = :delivery_status'
        params['delivery_status'] = delivery_status
    rows = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.notifications
            {where}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_unread(db: Session, workspace_id: uuid.UUID, user_id: str) -> int:
    result = db.execute(
        text(f"""
            SELECT COUNT(*)
            FROM {SCHEMA}.notifications
            WHERE workspace_id = :workspace_id AND user_id = :user_id AND is_read = false
        """),
        {'workspace_id': str(workspace_id), 'user_id': user_id},
    ).scalar()
    return result or 0


def find_by_id(db: Session, notification_id: uuid.UUID) -> dict | None:
    row = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.notifications
            WHERE id = :id
        """),
        {'id': str(notification_id)},
    ).fetchone()
    return _row_to_dict(row) if row else None


def insert(db: Session, notification: dict) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.notifications
                (id, workspace_id, user_id, title, body, category,
                 priority, link, is_read, created_at, read_at,
                 delivery_status, delivery_attempts, last_delivery_error, delivered_at)
            VALUES
                (:id, :workspace_id, :user_id, :title, :body, :category,
                 :priority, :link, :is_read, :created_at, :read_at,
                 :delivery_status, :delivery_attempts, :last_delivery_error, :delivered_at)
            RETURNING {_SELECT_COLS}
        """),
        {
            'id': str(notification['id']),
            'workspace_id': str(notification['workspace_id']),
            'user_id': notification['user_id'],
            'title': notification['title'],
            'body': notification['body'],
            'category': notification['category'],
            'priority': notification['priority'],
            'link': notification['link'],
            'is_read': notification['is_read'],
            'created_at': notification['created_at'],
            'read_at': notification['read_at'],
            'delivery_status': notification.get('delivery_status', 'pending'),
            'delivery_attempts': notification.get('delivery_attempts', 0),
            'last_delivery_error': notification.get('last_delivery_error'),
            'delivered_at': notification.get('delivered_at'),
        },
    ).fetchone()
    db.commit()
    return _row_to_dict(row)


def mark_read(
    db: Session, notification_id: uuid.UUID, user_id: str,
    workspace_id: uuid.UUID | None = None,
) -> bool:
    now = datetime.now(timezone.utc)
    where = 'WHERE id = :id AND user_id = :user_id AND is_read = false'
    params: dict = {'id': str(notification_id), 'user_id': user_id, 'read_at': now}
    if workspace_id:
        where += ' AND workspace_id = :wid'
        params['wid'] = str(workspace_id)
    result = db.execute(
        text(f"""
            UPDATE {SCHEMA}.notifications
            SET is_read = true, read_at = :read_at
            {where}
        """),
        params,
    )
    db.commit()
    return result.rowcount > 0


def mark_all_read(db: Session, workspace_id: uuid.UUID, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        text(f"""
            UPDATE {SCHEMA}.notifications
            SET is_read = true, read_at = :read_at
            WHERE workspace_id = :workspace_id AND user_id = :user_id AND is_read = false
        """),
        {'workspace_id': str(workspace_id), 'user_id': user_id, 'read_at': now},
    )
    db.commit()
    return result.rowcount


def update_delivery_status(
    db: Session, notification_id: uuid.UUID, *,
    delivery_status: str, delivery_attempts: int,
    last_delivery_error: str | None, delivered_at=None,
) -> None:
    """Update delivery tracking fields on a notification row."""
    db.execute(
        text(f"""
            UPDATE {SCHEMA}.notifications
            SET delivery_status = :status,
                delivery_attempts = :attempts,
                last_delivery_error = :error,
                delivered_at = :delivered_at
            WHERE id = :id
        """),
        {
            'id': str(notification_id),
            'status': delivery_status,
            'attempts': delivery_attempts,
            'error': last_delivery_error,
            'delivered_at': delivered_at,
        },
    )
    db.commit()


def _row_to_dict(row) -> dict:
    """Convert DB row to dict."""
    d = {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'user_id': row.user_id,
        'title': row.title,
        'body': row.body or '',
        'category': row.category,
        'priority': row.priority,
        'link': row.link or '',
        'is_read': row.is_read,
        'created_at': row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
        'read_at': row.read_at.isoformat() if row.read_at and hasattr(row.read_at, 'isoformat') else None,
    }
    if hasattr(row, 'delivery_status'):
        d['delivery_status'] = row.delivery_status
        d['delivery_attempts'] = row.delivery_attempts or 0
        d['last_delivery_error'] = row.last_delivery_error
        d['delivered_at'] = row.delivered_at.isoformat() if row.delivered_at and hasattr(row.delivered_at, 'isoformat') else None
    return d


from src.application.ports import NotificationRepository as NotificationRepositoryPort


class NotificationRepositoryAdapter(NotificationRepositoryPort):
    """Infrastructure adapter implementing NotificationRepository port."""

    def find_by_workspace_user(self, db, workspace_id, user_id, *, is_read=None,
                               delivery_status=None, limit=50, offset=0):
        return find_by_workspace_user(
            db, workspace_id, user_id, is_read=is_read,
            delivery_status=delivery_status, limit=limit, offset=offset,
        )

    def count_unread(self, db, workspace_id, user_id):
        return count_unread(db, workspace_id, user_id)

    def find_by_id(self, db, notification_id):
        return find_by_id(db, notification_id)

    def insert(self, db, notification):
        return insert(db, notification)

    def mark_read(self, db, notification_id, user_id, workspace_id=None):
        return mark_read(db, notification_id, user_id, workspace_id=workspace_id)

    def mark_all_read(self, db, workspace_id, user_id):
        return mark_all_read(db, workspace_id, user_id)

    def update_delivery_status(self, db, notification_id, *,
                               delivery_status, delivery_attempts,
                               last_delivery_error, delivered_at=None):
        return update_delivery_status(
            db, notification_id, delivery_status=delivery_status,
            delivery_attempts=delivery_attempts,
            last_delivery_error=last_delivery_error,
            delivered_at=delivered_at,
        )
