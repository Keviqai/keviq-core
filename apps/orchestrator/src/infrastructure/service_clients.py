"""Lightweight HTTP clients for cross-service validation and context enrichment.

Used for:
1. Artifact belongs to the claimed workspace (cross-workspace guard on create).
2. Reviewer is a member of the workspace (reviewer assignment guard on create).
3. Fetch artifact context summary for approval detail enrichment (read-only).
4. Enrich approval list items with artifact names (Q5-S1).

Notification delivery functions live in notification_clients.py.
Fail-closed when service URL is configured and service is unreachable.
Fail-open (skip validation) when URL env var is not set — dev/test environments only.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

import httpx

from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_ARTIFACT_SERVICE_URL = os.environ.get("ARTIFACT_SERVICE_URL", "").rstrip("/")
_WORKSPACE_SERVICE_URL = os.environ.get("WORKSPACE_SERVICE_URL", "").rstrip("/")
_TIMEOUT = 5.0


def validate_artifact_in_workspace(artifact_id: UUID, workspace_id: UUID) -> bool:
    """Return True if artifact belongs to workspace. Fail-closed on error.

    Requires ARTIFACT_SERVICE_URL env var to be set.
    If not configured, returns True (skip validation — dev/test environments).
    """
    if not _ARTIFACT_SERVICE_URL:
        logger.warning("ARTIFACT_SERVICE_URL not configured — skipping artifact workspace check")
        return True

    url = f"{_ARTIFACT_SERVICE_URL}/internal/v1/artifacts/{artifact_id}"
    headers = get_auth_client().auth_headers("artifact-service")
    try:
        resp = httpx.get(
            url, headers=headers, timeout=_TIMEOUT,
            params={"workspace_id": str(workspace_id)},
        )
        if resp.status_code == 404:
            return False
        if resp.status_code != 200:
            logger.error("artifact-service returned %d for artifact %s", resp.status_code, artifact_id)
            return False
        return True
    except Exception as exc:
        logger.error("Failed to validate artifact %s against workspace %s: %s", artifact_id, workspace_id, exc)
        return False


def validate_workspace_member(workspace_id: UUID, user_id: UUID) -> bool:
    """Return True if user_id is a member of workspace. Fail-closed on error.

    Requires WORKSPACE_SERVICE_URL env var to be set.
    If not configured, returns True (skip validation — dev/test environments).
    """
    if not _WORKSPACE_SERVICE_URL:
        logger.warning("WORKSPACE_SERVICE_URL not configured — skipping reviewer membership check")
        return True

    url = f"{_WORKSPACE_SERVICE_URL}/v1/workspaces/{workspace_id}/members"
    headers = get_auth_client().auth_headers("workspace-service")
    try:
        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.error("workspace-service returned %d listing members for %s", resp.status_code, workspace_id)
            return False
        members = resp.json()
        return any(str(m.get("user_id")) == str(user_id) for m in members)
    except Exception as exc:
        logger.error("Failed to validate member %s in workspace %s: %s", user_id, workspace_id, exc)
        return False


def get_artifact_context(artifact_id: UUID, workspace_id: UUID) -> dict[str, Any] | None:
    """Fetch artifact context summary for approval detail enrichment.

    Returns dict with name, artifact_type, artifact_status, size_bytes,
    annotation_count. Returns None on any error (graceful degradation).

    Defense-in-depth: verifies artifact belongs to workspace_id before
    returning context, even though approval creation already enforces this.

    Requires ARTIFACT_SERVICE_URL env var to be set.
    If not configured, returns None (no context enrichment — dev/test environments).
    """
    if not _ARTIFACT_SERVICE_URL:
        logger.info("ARTIFACT_SERVICE_URL not configured — skipping artifact context enrichment")
        return None

    headers = get_auth_client().auth_headers("artifact-service")
    artifact_url = f"{_ARTIFACT_SERVICE_URL}/internal/v1/artifacts/{artifact_id}"
    annotations_url = f"{_ARTIFACT_SERVICE_URL}/internal/v1/artifacts/{artifact_id}/annotations"
    ws_param = {"workspace_id": str(workspace_id)}

    try:
        artifact_resp = httpx.get(artifact_url, headers=headers, timeout=_TIMEOUT, params=ws_param)
        if artifact_resp.status_code != 200:
            logger.warning(
                "artifact-service returned %d for context fetch of %s",
                artifact_resp.status_code, artifact_id,
            )
            return None
        data = artifact_resp.json()
    except Exception as exc:
        logger.error("Failed to fetch artifact context for %s: %s", artifact_id, exc)
        return None

    annotation_count = _fetch_annotation_count(annotations_url, headers, workspace_id)

    return {
        "name": data.get("name"),
        "artifact_type": data.get("artifact_type"),
        "artifact_status": data.get("artifact_status"),
        "size_bytes": data.get("size_bytes"),
        "annotation_count": annotation_count,
    }


def _fetch_annotation_count(
    annotations_url: str, headers: dict[str, str], workspace_id: UUID,
) -> int | None:
    """Return annotation count for an artifact, or None on error."""
    try:
        resp = httpx.get(
            annotations_url, headers=headers, timeout=_TIMEOUT,
            params={"workspace_id": str(workspace_id)},
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        items = body.get("items", [])
        return len(items)
    except Exception as exc:
        logger.warning("Failed to fetch annotation count: %s", exc)
        return None


def get_artifact_name(artifact_id: UUID, workspace_id: UUID) -> str | None:
    """Return artifact display name. Returns None on any error.

    Lightweight — only fetches the artifact record, does not fetch annotations.
    Requires ARTIFACT_SERVICE_URL env var to be set.
    """
    if not _ARTIFACT_SERVICE_URL:
        return None

    url = f"{_ARTIFACT_SERVICE_URL}/internal/v1/artifacts/{artifact_id}"
    headers = get_auth_client().auth_headers("artifact-service")
    try:
        resp = httpx.get(
            url, headers=headers, timeout=_TIMEOUT,
            params={"workspace_id": str(workspace_id)},
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("name")
    except Exception as exc:
        logger.warning("Failed to fetch artifact name for %s: %s", artifact_id, exc)
        return None


def enrich_approval_list_with_artifact_names(
    items: list[dict[str, Any]], approvals: list[Any],
) -> None:
    """Mutate items in-place to add artifact_name for artifact-type approvals (Q5-S1).

    Deduplicates HTTP calls — each unique artifact_id fetched once per request.
    items[i]["artifact_name"] = artifact display name if target_type=="artifact",
    else None. Fails silently — list still returns on any enrichment error.
    """
    if len(items) != len(approvals):
        raise ValueError(
            f"enrich: items/approvals length mismatch {len(items)} vs {len(approvals)}"
        )
    # Build name cache — one HTTP call per unique artifact_id (dedup for N=50 worst case)
    name_cache: dict[str, str | None] = {}
    for approval in approvals:
        if getattr(approval, "target_type", None) == "artifact":
            key = str(approval.target_id)
            if key not in name_cache:
                try:
                    name_cache[key] = get_artifact_name(
                        UUID(key), UUID(str(approval.workspace_id)),
                    )
                except Exception as exc:
                    logger.warning("artifact name cache build failed for %s: %s", key, exc)
                    name_cache[key] = None

    for item, approval in zip(items, approvals):
        if getattr(approval, "target_type", None) == "artifact":
            item["artifact_name"] = name_cache.get(str(approval.target_id))
        else:
            item["artifact_name"] = None

