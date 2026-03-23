"""Fire-and-forget audit event recording for orchestrator actions.

Fail-open: if audit-service is unavailable, logs warning and returns.
Never raises — audit failure must not break product flows.

Used for:
1. approval.requested — when a user initiates an approval
2. approval.decided   — when a reviewer approves or rejects
3. task.created       — when a task is launched (emit from handler)
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

import httpx

from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_AUDIT_SERVICE_URL = os.environ.get("AUDIT_SERVICE_URL", "").rstrip("/")
_TIMEOUT = 5.0


def record_audit(
    *,
    actor_id: str,
    action: str,
    workspace_id: UUID,
    actor_type: str = 'user',
    target_id: str | None = None,
    target_type: str | None = None,
    metadata: dict | None = None,
) -> None:
    """POST an audit entry to audit-service. Fail-open on any error."""
    if not _AUDIT_SERVICE_URL:
        logger.warning("AUDIT_SERVICE_URL not configured — audit event '%s' not recorded", action)
        return

    payload = {
        "actor_id": str(actor_id),
        "actor_type": actor_type,
        "action": action,
        "workspace_id": str(workspace_id),
        "target_id": str(target_id) if target_id else None,
        "target_type": target_type,
        "metadata": metadata or {},
    }
    headers = get_auth_client().auth_headers("audit-service")

    try:
        resp = httpx.post(
            f"{_AUDIT_SERVICE_URL}/internal/v1/audit-events",
            json=payload,
            headers=headers,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 201:
            logger.warning(
                "audit-service returned %d for action '%s' (actor=%s workspace=%s)",
                resp.status_code, action, actor_id, workspace_id,
            )
    except Exception as exc:
        logger.error(
            "Failed to record audit event '%s' for actor %s: %s",
            action, actor_id, exc,
        )
