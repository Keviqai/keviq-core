"""Notification-service API routes."""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.schemas import CreateNotificationRequest, NotificationResponse
from src.application import notification_service
from src.application.bootstrap import get_session_factory
from src.domain.notification import NotificationNotFound

router = APIRouter()


def _get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


# ── Health checks ──────────────────────────────────────────────


@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info() -> dict[str, str]:
    info: dict = {"service": "notification-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Notification API ──────────────────────────────────────────


@router.get(
    "/internal/v1/workspaces/{workspace_id}/notifications",
    response_model=list[NotificationResponse],
)
def list_notifications(
    workspace_id: uuid.UUID,
    request: Request,
    db=Depends(_get_db),
    is_read: bool | None = None,
    delivery_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    user_id = request.headers.get('x-user-id', '')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")
    if delivery_status and delivery_status not in ('pending', 'sent', 'failed', 'skipped'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid delivery_status")
    limit = max(1, min(limit, 200))
    offset = max(0, min(offset, 10000))
    return notification_service.list_notifications(
        db, workspace_id, user_id, is_read=is_read,
        delivery_status=delivery_status, limit=limit, offset=offset,
    )


@router.get("/internal/v1/workspaces/{workspace_id}/notifications/count")
def count_unread(
    workspace_id: uuid.UUID,
    request: Request,
    db=Depends(_get_db),
):
    user_id = request.headers.get('x-user-id', '')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")
    count = notification_service.count_unread(db, workspace_id, user_id)
    return {"workspace_id": str(workspace_id), "unread_count": count}


@router.post(
    "/internal/v1/workspaces/{workspace_id}/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification(
    workspace_id: uuid.UUID,
    body: CreateNotificationRequest,
    db=Depends(_get_db),
):
    try:
        result = notification_service.create_notification(
            db,
            workspace_id=workspace_id,
            user_id=body.user_id,
            title=body.title,
            body=body.body,
            category=body.category,
            priority=body.priority,
            link=body.link,
            recipient_email=body.recipient_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return NotificationResponse(**result)


@router.post(
    "/internal/v1/workspaces/{workspace_id}/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
)
def mark_read(
    workspace_id: uuid.UUID,
    notification_id: uuid.UUID,
    request: Request,
    db=Depends(_get_db),
):
    user_id = request.headers.get('x-user-id', '')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")
    try:
        notification_service.mark_read(db, notification_id, user_id, workspace_id=workspace_id)
    except NotificationNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


@router.post(
    "/internal/v1/workspaces/{workspace_id}/notifications/read-all",
    status_code=status.HTTP_200_OK,
)
def mark_all_read(
    workspace_id: uuid.UUID,
    request: Request,
    db=Depends(_get_db),
):
    user_id = request.headers.get('x-user-id', '')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")
    count = notification_service.mark_all_read(db, workspace_id, user_id)
    return {"marked_count": count}


# ── Cleanup: read notification retention ───────────────────────

logger = logging.getLogger(__name__)

_NOTIFICATION_RETENTION_DAYS = int(os.getenv('NOTIFICATION_RETENTION_DAYS', '30'))
_CLEANUP_BATCH_SIZE = int(os.getenv('CLEANUP_BATCH_SIZE', '1000'))


@router.post("/internal/v1/notifications/cleanup")
def cleanup_read_notifications(
    dry_run: bool = False,
    retention_days: int | None = None,
    batch_size: int | None = None,
    db=Depends(_get_db),
):
    """Delete read notifications older than retention period."""
    days = retention_days or _NOTIFICATION_RETENTION_DAYS
    batch = min(batch_size or _CLEANUP_BATCH_SIZE, 5000)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    from sqlalchemy import text

    count_result = db.execute(
        text("""
            SELECT COUNT(*) FROM notification_core.notifications
            WHERE is_read = true AND read_at < :cutoff
        """),
        {'cutoff': cutoff},
    ).scalar() or 0

    if dry_run or count_result == 0:
        return {
            "dry_run": dry_run,
            "retention_days": days,
            "cutoff": cutoff.isoformat(),
            "candidates": count_result,
            "deleted": 0,
        }

    result = db.execute(
        text("""
            DELETE FROM notification_core.notifications
            WHERE id IN (
                SELECT id FROM notification_core.notifications
                WHERE is_read = true AND read_at < :cutoff
                ORDER BY read_at ASC
                LIMIT :batch
            )
        """),
        {'cutoff': cutoff, 'batch': batch},
    )
    deleted = result.rowcount
    db.commit()

    logger.info("notification cleanup: deleted %d read notifications older than %s", deleted, cutoff.isoformat())
    return {
        "dry_run": False,
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "candidates": count_result,
        "deleted": deleted,
    }
