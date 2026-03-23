"""Audit application service — record and query audit events."""

from __future__ import annotations

import logging
from uuid import UUID

from src.domain.audit_event import AuditEvent
from .bootstrap import get_audit_repo

logger = logging.getLogger(__name__)

_MAX_LIMIT = 200


def record_audit_event(
    db,
    *,
    actor_id: str,
    action: str,
    workspace_id: UUID,
    actor_type: str = 'user',
    target_id: str | None = None,
    target_type: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create and persist an audit event. Returns the stored record."""
    event = AuditEvent.create(
        actor_id=actor_id,
        action=action,
        workspace_id=workspace_id,
        actor_type=actor_type,
        target_id=target_id,
        target_type=target_type,
        metadata=metadata or {},
    )
    stored = get_audit_repo().insert(db, event)
    logger.info(
        "Audit event recorded: action=%s actor=%s target=%s/%s workspace=%s",
        action, actor_id, target_type, target_id, workspace_id,
    )
    return stored


def list_audit_events(
    db,
    workspace_id: UUID,
    *,
    action: str | None = None,
    actor_id: str | None = None,
    target_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List audit events for a workspace with optional filters."""
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    return get_audit_repo().find_by_workspace(
        db, workspace_id,
        action=action,
        actor_id=actor_id,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
