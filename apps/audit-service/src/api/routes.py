"""Audit service API routes."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.application import audit_service
from src.application.bootstrap import get_session_factory
from src.internal_auth import require_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_db():
    db = get_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
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
    info: dict = {"service": "audit-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Write: internal endpoint (called by other services) ───────


@router.post(
    "/internal/v1/audit-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_service("orchestrator"))],
)
async def create_audit_event(request: Request, db=Depends(_get_db)):
    """Record an audit event from an internal service.

    Caller must provide internal auth token. actor_id, action, workspace_id required.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    actor_id = str(body.get("actor_id", "")).strip()
    action = str(body.get("action", "")).strip()
    workspace_id_str = str(body.get("workspace_id", "")).strip()

    if not actor_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="actor_id is required")
    if not action:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="action is required")
    if not workspace_id_str:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="workspace_id is required")

    try:
        workspace_id = uuid.UUID(workspace_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="workspace_id must be a valid UUID")

    actor_type = str(body.get("actor_type", "user")).strip() or "user"
    target_id = body.get("target_id") or None
    target_type = body.get("target_type") or None
    metadata = body.get("metadata") or {}

    if not isinstance(metadata, dict):
        metadata = {}

    try:
        result = audit_service.record_audit_event(
            db,
            actor_id=actor_id,
            action=action,
            workspace_id=workspace_id,
            actor_type=actor_type,
            target_id=str(target_id) if target_id else None,
            target_type=str(target_type) if target_type else None,
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return result


# ── Read: gateway-proxied (JWT + workspace:view) ───────────────


@router.get(
    "/v1/workspaces/{workspace_id}/audit-events",
    dependencies=[Depends(require_service("api-gateway"))],
)
def list_audit_events(
    workspace_id: str,
    db=Depends(_get_db),
    action: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List audit events for a workspace. Proxied from gateway (JWT + workspace:view)."""
    try:
        wid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace_id")

    return audit_service.list_audit_events(
        db, wid,
        action=action,
        actor_id=actor_id,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
