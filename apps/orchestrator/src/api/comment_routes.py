"""Task comment routes for orchestrator.

P6-S2: Create and list comments on tasks. Workspace-scoped.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text

from src.application.bootstrap import get_uow
from src.internal_auth import require_service

logger = logging.getLogger(__name__)

router = APIRouter()

SCHEMA = "orchestrator_core"
_MAX_BODY = 2000
_MAX_LIMIT = 100


@router.get("/internal/v1/workspaces/{workspace_id}/tasks/{task_id}/comments")
def list_task_comments(
    workspace_id: str,
    task_id: str,
    limit: int = 50,
    offset: int = 0,
    _claims=Depends(require_service("api-gateway")),
):
    """List comments for a task, oldest first."""
    limit = max(1, min(limit, _MAX_LIMIT))
    offset = max(0, offset)

    try:
        wid = UUID(workspace_id)
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    uow = get_uow()
    with uow:
        rows = uow._session_factory().execute(
            text(f"""
                SELECT id, workspace_id, task_id, author_id, body, created_at
                FROM {SCHEMA}.task_comments
                WHERE workspace_id = :wid AND task_id = :tid
                ORDER BY created_at ASC
                LIMIT :limit OFFSET :offset
            """),
            {"wid": str(wid), "tid": str(tid), "limit": limit, "offset": offset},
        ).fetchall()

    items = [
        {
            "id": str(r.id),
            "workspace_id": str(r.workspace_id),
            "task_id": str(r.task_id),
            "author_id": str(r.author_id),
            "body": r.body,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


@router.post(
    "/internal/v1/workspaces/{workspace_id}/tasks/{task_id}/comments",
    status_code=status.HTTP_201_CREATED,
)
async def create_task_comment(
    workspace_id: str,
    task_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Create a comment on a task."""
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    comment_body = str(body.get("body", "")).strip()
    if not comment_body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="body is required")
    if len(comment_body) > _MAX_BODY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"body too long (max {_MAX_BODY} characters)",
        )

    try:
        wid = UUID(workspace_id)
        tid = UUID(task_id)
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    comment_id = uuid4()
    now = datetime.now(timezone.utc)

    uow = get_uow()
    with uow:
        session = uow._session_factory()
        session.execute(
            text(f"""
                INSERT INTO {SCHEMA}.task_comments (id, workspace_id, task_id, author_id, body, created_at)
                VALUES (:id, :wid, :tid, :uid, :body, :created_at)
            """),
            {
                "id": str(comment_id),
                "wid": str(wid),
                "tid": str(tid),
                "uid": str(uid),
                "body": comment_body,
                "created_at": now,
            },
        )
        # Emit comment.created outbox event for activity feed
        event_id = uuid4()
        correlation_id = uuid4()
        session.execute(
            text(f"""
                INSERT INTO {SCHEMA}.outbox (id, event_type, correlation_id, payload, created_at)
                VALUES (:id, :event_type, :correlation_id, CAST(:payload AS jsonb), :created_at)
            """),
            {
                "id": str(event_id),
                "event_type": "comment.created",
                "correlation_id": str(correlation_id),
                "payload": json.dumps({
                    "event_id": str(event_id),
                    "event_type": "comment.created",
                    "schema_version": "1.0",
                    "workspace_id": str(wid),
                    "task_id": str(tid),
                    "run_id": None,
                    "step_id": None,
                    "correlation_id": str(correlation_id),
                    "causation_id": None,
                    "occurred_at": now.isoformat(),
                    "emitted_by": {"service": "orchestrator", "instance_id": "local"},
                    "actor": {"type": "user", "id": str(uid)},
                    "payload": {
                        "comment_id": str(comment_id),
                        "author_id": str(uid),
                        "body_preview": comment_body[:100],
                    },
                }),
                "created_at": now,
            },
        )
        session.commit()

    logger.info("Task comment created: id=%s task=%s author=%s", comment_id, tid, uid)

    return {
        "id": str(comment_id),
        "workspace_id": str(wid),
        "task_id": str(tid),
        "author_id": str(uid),
        "body": comment_body,
        "created_at": now.isoformat(),
    }
