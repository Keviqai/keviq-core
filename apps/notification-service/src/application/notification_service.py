"""Notification application service — CRUD + delivery tracking."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import structlog

from src.domain.notification import VALID_CATEGORIES, VALID_PRIORITIES, NotificationNotFound

from .bootstrap import get_email_adapter, get_notification_repo

log = structlog.get_logger("notification.service")

# Retry policy — keep simple, no exponential backoff library needed
MAX_DELIVERY_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = [1.0, 3.0, 9.0]  # attempt 1, 2, 3


def list_notifications(
    db, workspace_id: uuid.UUID, user_id: str,
    *, is_read: bool | None = None, delivery_status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[dict]:
    """List notifications for a user in a workspace."""
    return get_notification_repo().find_by_workspace_user(
        db, workspace_id, user_id, is_read=is_read,
        delivery_status=delivery_status, limit=limit, offset=offset,
    )


def count_unread(db, workspace_id: uuid.UUID, user_id: str) -> int:
    """Count unread notifications for a user in a workspace."""
    return get_notification_repo().count_unread(db, workspace_id, user_id)


def create_notification(
    db,
    workspace_id: uuid.UUID,
    user_id: str,
    title: str,
    body: str | None = None,
    category: str = 'system',
    priority: str = 'normal',
    link: str | None = None,
    recipient_email: str | None = None,
) -> dict:
    """Create a notification and attempt email delivery with retry.

    Row creation always succeeds. Email delivery is best-effort with retry.
    Delivery status is tracked on the notification row.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}")

    now = datetime.now(timezone.utc)
    notification = {
        'id': uuid.uuid4(),
        'workspace_id': workspace_id,
        'user_id': user_id,
        'title': title,
        'body': body or '',
        'category': category,
        'priority': priority,
        'link': link or '',
        'is_read': False,
        'created_at': now,
        'read_at': None,
        'delivery_status': 'pending',
        'delivery_attempts': 0,
        'last_delivery_error': None,
        'delivered_at': None,
    }
    result = get_notification_repo().insert(db, notification)
    notification_id = result.get('id') or notification['id']

    # Attempt email delivery with retry for approval notifications
    if category == 'approval':
        delivery_result = _attempt_email_delivery_with_retry(
            db=db,
            notification_id=notification_id,
            recipient_email=recipient_email,
            title=title,
            body=body or '',
            link=link or '',
        )
        # Update the returned result with delivery info
        result.update(delivery_result)

    return result


def _attempt_email_delivery_with_retry(
    *,
    db,
    notification_id,
    recipient_email: str | None,
    title: str,
    body: str,
    link: str,
) -> dict:
    """Attempt email delivery with retry. Updates notification row. Never raises."""
    repo = get_notification_repo()
    adapter = get_email_adapter()

    # Skip: no recipient email
    if not recipient_email:
        log.debug("email delivery skipped: no recipient_email provided")
        _update_delivery(db, repo, notification_id, 'skipped', 0, None)
        return {'delivery_status': 'skipped', 'delivery_attempts': 0}

    # Skip: no SMTP adapter configured
    if adapter is None:
        log.info("email delivery skipped: SMTP not configured (set SMTP_HOST to enable)")
        _update_delivery(db, repo, notification_id, 'skipped', 0, 'SMTP not configured')
        return {'delivery_status': 'skipped', 'delivery_attempts': 0, 'last_delivery_error': 'SMTP not configured'}

    body_text = body
    if link:
        body_text = f"{body}\n\nView: {link}"

    last_error = None
    for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
        success = adapter.send(to_email=recipient_email, subject=title, body_text=body_text)

        if success:
            now = datetime.now(timezone.utc)
            _update_delivery(db, repo, notification_id, 'sent', attempt, None, now)
            log.info("email delivered", to=recipient_email, attempt=attempt)
            return {'delivery_status': 'sent', 'delivery_attempts': attempt, 'delivered_at': now.isoformat()}

        last_error = f"SMTP send failed on attempt {attempt}"
        log.warning("email delivery attempt failed", to=recipient_email, attempt=attempt, max=MAX_DELIVERY_ATTEMPTS)

        # Sleep before retry (except after last attempt)
        if attempt < MAX_DELIVERY_ATTEMPTS:
            delay = RETRY_DELAYS_SECONDS[attempt - 1] if attempt - 1 < len(RETRY_DELAYS_SECONDS) else 9.0
            time.sleep(delay)

    # All attempts exhausted
    _update_delivery(db, repo, notification_id, 'failed', MAX_DELIVERY_ATTEMPTS, last_error)
    log.error("email delivery failed after all retries", to=recipient_email, attempts=MAX_DELIVERY_ATTEMPTS)
    return {'delivery_status': 'failed', 'delivery_attempts': MAX_DELIVERY_ATTEMPTS, 'last_delivery_error': last_error}


def _update_delivery(db, repo, notification_id, status, attempts, error, delivered_at=None):
    """Update delivery tracking fields on the notification row."""
    try:
        repo.update_delivery_status(
            db, notification_id,
            delivery_status=status,
            delivery_attempts=attempts,
            last_delivery_error=error,
            delivered_at=delivered_at,
        )
    except Exception as exc:
        log.error("failed to update delivery status", notification_id=str(notification_id), error=str(exc))


def mark_read(db, notification_id: uuid.UUID, user_id: str, workspace_id: uuid.UUID | None = None) -> None:
    """Mark a notification as read. Raises NotificationNotFound if missing."""
    updated = get_notification_repo().mark_read(db, notification_id, user_id, workspace_id=workspace_id)
    if not updated:
        raise NotificationNotFound(str(notification_id))


def mark_all_read(db, workspace_id: uuid.UUID, user_id: str) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    return get_notification_repo().mark_all_read(db, workspace_id, user_id)
