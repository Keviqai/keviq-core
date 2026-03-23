"""Fire-and-forget notification delivery for orchestrator approval events.

Used for:
1. approval.requested → notify reviewer (or workspace managers) — Q4-S4
2. approval.decided  → notify requester — Q5-S2

All functions are designed to be called via FastAPI BackgroundTasks (post-response).
Logs errors but never raises — notification delivery is best-effort.
Fail-open when NOTIFICATION_SERVICE_URL not configured (dev/test environments).
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

import httpx

from src.internal_auth import get_auth_client
from src.infrastructure.service_clients import get_artifact_name

logger = logging.getLogger(__name__)

_NOTIFICATION_SERVICE_URL = os.environ.get("NOTIFICATION_SERVICE_URL", "").rstrip("/")
_WORKSPACE_SERVICE_URL = os.environ.get("WORKSPACE_SERVICE_URL", "").rstrip("/")
_TIMEOUT = 5.0


def notify_approval_requested(
    approval_id: UUID,
    workspace_id: UUID,
    requested_by: str,
    reviewer_id: UUID | None,
) -> None:
    """Push notification(s) for approval.requested event (Q4-S4).

    Notifies reviewer_id if assigned, otherwise workspace owners/admins.
    """
    if not _NOTIFICATION_SERVICE_URL:
        logger.warning("NOTIFICATION_SERVICE_URL not configured — approval notifications disabled")
        return

    recipients = [str(reviewer_id)] if reviewer_id else _get_workspace_manager_ids(workspace_id)
    if not recipients:
        logger.info("notify_approval_requested: no recipients for approval %s", approval_id)
        return

    body_text = f"{str(requested_by)[:8]}... requested an artifact approval"
    link = f"/workspaces/{workspace_id}/approvals/{approval_id}"
    headers = get_auth_client().auth_headers("notification-service")
    url = f"{_NOTIFICATION_SERVICE_URL}/internal/v1/workspaces/{workspace_id}/notifications"

    for user_id in recipients:
        _post_single_notification(url, user_id, "Approval requested", body_text, link, headers)


def notify_approval_decided(
    approval_id: UUID,
    workspace_id: UUID,
    requested_by: str,
    decision: str,
    target_id: UUID,
) -> None:
    """Push notification to requester when reviewer decides (Q5-S2).

    decision must be 'approved' or 'rejected'.
    Fetches artifact name for richer notification body (best-effort, falls back to 'artifact').
    """
    if not _NOTIFICATION_SERVICE_URL:
        logger.warning("NOTIFICATION_SERVICE_URL not configured — decided notification skipped")
        return

    if not requested_by:
        logger.warning("notify_approval_decided: no requested_by for approval %s", approval_id)
        return

    artifact_name = get_artifact_name(target_id, workspace_id)
    subject = artifact_name or "artifact"
    verb = "approved" if decision == "approved" else "rejected"
    body_text = f"Your approval request for '{subject}' was {verb}"
    link = f"/workspaces/{workspace_id}/approvals/{approval_id}"
    title = f"Approval {verb}"
    headers = get_auth_client().auth_headers("notification-service")
    url = f"{_NOTIFICATION_SERVICE_URL}/internal/v1/workspaces/{workspace_id}/notifications"

    _post_single_notification(url, requested_by, title, body_text, link, headers)


def _post_single_notification(
    url: str, user_id: str, title: str, body_text: str, link: str, headers: dict[str, str],
) -> None:
    """POST one notification to notification-service. Logs errors silently."""
    try:
        resp = httpx.post(
            url,
            json={
                "user_id": user_id,
                "title": title,
                "body": body_text,
                "category": "approval",
                "priority": "high",
                "link": link,
            },
            headers=headers,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 201:
            logger.warning(
                "notification-service returned %d for user %s", resp.status_code, user_id,
            )
    except Exception as exc:
        logger.error("Failed to create notification for user %s: %s", user_id, exc)


def _get_workspace_manager_ids(workspace_id: UUID) -> list[str]:
    """Return user_ids of workspace owners/admins for notification fallback.

    Returns empty list on any error — caller handles gracefully.
    """
    if not _WORKSPACE_SERVICE_URL:
        return []
    url = f"{_WORKSPACE_SERVICE_URL}/v1/workspaces/{workspace_id}/members"
    headers = get_auth_client().auth_headers("workspace-service")
    try:
        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(
                "workspace-service returned %d fetching managers for %s",
                resp.status_code, workspace_id,
            )
            return []
        members = resp.json()
        managers = [
            str(m.get("user_id"))
            for m in members
            if m.get("role") in ("owner", "admin") and m.get("user_id")
        ]
        if not managers and members:
            sample_roles = {m.get("role") for m in members[:5]}
            logger.warning(
                "No owners/admins found for workspace %s — possible role field mismatch "
                "(sample roles seen: %s)", workspace_id, sample_roles,
            )
        return managers
    except Exception as exc:
        logger.error("Failed to fetch workspace managers for %s: %s", workspace_id, exc)
        return []
