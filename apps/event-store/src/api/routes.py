"""Event-store API routes — ingest + query (non-SSE).

SSE streaming endpoints are in sse.py.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.internal_auth import require_service

from src.application.bootstrap import get_repo
from src.application.ingest import ingest_event, ingest_event_batch
from src.application.queries import (
    get_run_timeline,
    get_task_timeline,
    get_workspace_activity,
)
from src.domain.event import event_to_dict

router = APIRouter()
logger = logging.getLogger(__name__)

# Maximum batch ingest size
_MAX_BATCH_SIZE = 500
# SSE heartbeat interval in seconds
_SSE_HEARTBEAT_INTERVAL = 15
# SSE poll interval for new events
_SSE_POLL_INTERVAL = 1


# ── Health ─────────────────────────────────────────────────────

@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "event-store"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Internal: Ingest ───────────────────────────────────────────

@router.post(
    "/internal/v1/events/ingest",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_endpoint(request: Request, _claims=Depends(require_service("orchestrator", "artifact-service"))):
    """Ingest an event envelope. Idempotent by event_id."""
    body = await request.json()

    repo = get_repo()
    try:
        is_new = ingest_event(body, repo)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    finally:
        repo.close()

    return {
        "status": "created" if is_new else "duplicate",
        "event_id": body.get("event_id"),
    }


@router.post(
    "/internal/v1/events/ingest/batch",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_batch_endpoint(request: Request, _claims=Depends(require_service("orchestrator", "artifact-service"))):
    """Ingest a batch of event envelopes in a single transaction."""
    body = await request.json()
    envelopes = body if isinstance(body, list) else body.get("events", [])

    if len(envelopes) > _MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size {len(envelopes)} exceeds maximum of {_MAX_BATCH_SIZE}",
        )

    repo = get_repo()
    try:
        results = ingest_event_batch(envelopes, repo)
    finally:
        repo.close()

    return {"results": results}


# ── Query: Task Timeline ──────────────────────────────────────

@router.get("/internal/v1/tasks/{task_id}/timeline")
def task_timeline_endpoint(task_id: str, workspace_id: str, after: str | None = None, limit: int = 100, _claims=Depends(require_service("api-gateway"))):
    """Get event timeline for a task scoped to a workspace, ordered by occurred_at."""
    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format",
        )
    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    after_dt = None
    if after:
        try:
            after_dt = datetime.fromisoformat(after)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'after' datetime format",
            )

    limit = max(1, min(limit, 500))
    repo = get_repo()
    try:
        events = get_task_timeline(tid, wid, repo, after=after_dt, limit=limit)
    finally:
        repo.close()

    return {
        "task_id": task_id,
        "workspace_id": workspace_id,
        "events": [event_to_dict(e) for e in events],
        "count": len(events),
    }


# ── Query: Run Timeline ───────────────────────────────────────

@router.get("/internal/v1/runs/{run_id}/timeline")
def run_timeline_endpoint(run_id: str, workspace_id: str, after: str | None = None, limit: int = 100, _claims=Depends(require_service("api-gateway"))):
    """Get event timeline for a run scoped to a workspace, ordered by occurred_at."""
    try:
        rid = UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format",
        )
    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    after_dt = None
    if after:
        try:
            after_dt = datetime.fromisoformat(after)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'after' datetime format",
            )

    limit = max(1, min(limit, 500))
    repo = get_repo()
    try:
        events = get_run_timeline(rid, wid, repo, after=after_dt, limit=limit)
    finally:
        repo.close()

    return {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "events": [event_to_dict(e) for e in events],
        "count": len(events),
    }


# ── Query: Workspace Activity ─────────────────────────────────

@router.get("/internal/v1/workspaces/{workspace_id}/activity")
def workspace_activity_endpoint(
    workspace_id: str,
    event_type: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _claims=Depends(require_service("api-gateway")),
):
    """Get workspace activity feed (newest first) with optional filters."""
    try:
        ws_id = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    after_dt = None
    if after:
        try:
            after_dt = datetime.fromisoformat(after)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'after' datetime format",
            )

    before_dt = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'before' datetime format",
            )

    limit = max(1, min(limit, 100))
    offset = max(0, min(offset, 10000))

    repo = get_repo()
    try:
        events, total = get_workspace_activity(
            ws_id, repo,
            event_type=event_type,
            after=after_dt,
            before=before_dt,
            limit=limit,
            offset=offset,
        )
    finally:
        repo.close()

    return {
        "workspace_id": workspace_id,
        "events": [event_to_dict(e) for e in events],
        "count": len(events),
        "total_count": total,
    }


# ── Cleanup: event retention ──────────────────────────────────

_EVENT_RETENTION_DAYS = int(os.getenv('EVENT_RETENTION_DAYS', '90'))
_CLEANUP_BATCH_SIZE = int(os.getenv('CLEANUP_BATCH_SIZE', '1000'))


@router.post("/internal/v1/events/cleanup")
def cleanup_old_events(
    request: Request,
    dry_run: bool = False,
    retention_days: int | None = None,
    batch_size: int | None = None,
):
    """Delete events older than retention period. Returns count deleted."""
    days = retention_days or _EVENT_RETENTION_DAYS
    batch = min(batch_size or _CLEANUP_BATCH_SIZE, 5000)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    repo = get_repo()
    try:
        from sqlalchemy import text
        session = repo._session

        # Count candidates
        count_result = session.execute(
            text("SELECT COUNT(*) FROM event_core.events WHERE occurred_at < :cutoff"),
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

        # Batched delete
        result = session.execute(
            text("""
                DELETE FROM event_core.events
                WHERE id IN (
                    SELECT id FROM event_core.events
                    WHERE occurred_at < :cutoff
                    ORDER BY occurred_at ASC
                    LIMIT :batch
                )
            """),
            {'cutoff': cutoff, 'batch': batch},
        )
        deleted = result.rowcount
        session.commit()

        logger.info("event cleanup: deleted %d events older than %s", deleted, cutoff.isoformat())
        return {
            "dry_run": False,
            "retention_days": days,
            "cutoff": cutoff.isoformat(),
            "candidates": count_result,
            "deleted": deleted,
        }
    finally:
        repo.close()
