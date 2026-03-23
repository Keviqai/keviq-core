"""Artifact-service tag routes: get tags, add tag, remove tag.

Tag CRUD endpoints for artifact tagging functionality.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.bootstrap import get_uow
from src.internal_auth import require_service

from src.api.route_helpers import parse_uuid, verify_workspace

_MAX_TAG_LENGTH = 128
_MAX_TAGS_PER_ARTIFACT = 50
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

tags_router = APIRouter()


# ── Query: Get Artifact Tags ─────────────────────────────────

@tags_router.get("/internal/v1/artifacts/{artifact_id}/tags")
def get_artifact_tags_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Get all tags for an artifact."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        verify_workspace(artifact, wid)
        tags = uow.tags.get_tags(aid)

    return {"artifact_id": str(aid), "tags": tags}


# ── Command: Add Tag ─────────────────────────────────────────

@tags_router.post("/internal/v1/artifacts/{artifact_id}/tags", status_code=201)
def add_artifact_tag_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    tag: str = Query(..., description="Tag value to add"),
    _claims=Depends(require_service("api-gateway")),
):
    """Add a tag to an artifact."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    if not tag or not tag.strip():
        raise HTTPException(status_code=400, detail="tag must not be blank")
    tag = tag.strip()

    if len(tag) > _MAX_TAG_LENGTH:
        raise HTTPException(status_code=400, detail=f"tag must be at most {_MAX_TAG_LENGTH} characters")
    if _CONTROL_CHAR_RE.search(tag):
        raise HTTPException(status_code=400, detail="tag must not contain control characters")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        verify_workspace(artifact, wid)
        existing_tags = uow.tags.get_tags(aid)
        if len(existing_tags) >= _MAX_TAGS_PER_ARTIFACT:
            raise HTTPException(status_code=400, detail=f"artifact already has {_MAX_TAGS_PER_ARTIFACT} tags")
        uow.tags.add_tag(aid, wid, tag)
        uow.commit()

    return {"artifact_id": str(aid), "tag": tag}


# ── Command: Remove Tag ──────────────────────────────────────

@tags_router.delete("/internal/v1/artifacts/{artifact_id}/tags/{tag}")
def remove_artifact_tag_endpoint(
    artifact_id: str,
    tag: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Remove a tag from an artifact."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        verify_workspace(artifact, wid)
        removed = uow.tags.remove_tag(aid, tag)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Tag '{tag}' not found on artifact")
        uow.commit()

    return {"artifact_id": str(aid), "tag": tag, "removed": True}
