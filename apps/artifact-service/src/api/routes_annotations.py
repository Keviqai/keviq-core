"""Artifact annotation routes (Q3-S3).

Separate file because routes.py exceeds 300-line limit.
GET  /internal/v1/artifacts/{artifact_id}/annotations
POST /internal/v1/artifacts/{artifact_id}/annotations
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.application.bootstrap import get_uow
from src.domain.annotation import ArtifactAnnotation
from src.domain.errors import DomainValidationError
from src.internal_auth import require_service

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_LIMIT = 100


# ── Helpers ────────────────────────────────────────────────────


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format — expected UUID",
        )


def _annotation_to_dict(a: ArtifactAnnotation) -> dict:
    return {
        "id": str(a.id),
        "artifact_id": str(a.artifact_id),
        "workspace_id": str(a.workspace_id),
        "author_id": str(a.author_id),
        "body": a.body,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ── Routes ─────────────────────────────────────────────────────


@router.get("/internal/v1/artifacts/{artifact_id}/annotations")
def list_annotations(
    artifact_id: str,
    workspace_id: str = Query(...),
    limit: int = Query(50, ge=1, le=_MAX_LIMIT),
    _auth: None = Depends(require_service("api-gateway", "orchestrator")),
):
    aid = _parse_uuid(artifact_id, "artifact_id")
    wid = _parse_uuid(workspace_id, "workspace_id")

    with get_uow() as uow:
        artifact = uow.artifacts.get_by_id(aid)
        if artifact is None or artifact.workspace_id != wid:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        items = uow.annotations.list_by_artifact(aid, wid, limit=limit)

    return {"items": [_annotation_to_dict(a) for a in items], "count": len(items)}


@router.post("/internal/v1/artifacts/{artifact_id}/annotations", status_code=status.HTTP_201_CREATED)
async def create_annotation(
    artifact_id: str,
    request: Request,
    workspace_id: str = Query(...),
    _auth: None = Depends(require_service("api-gateway")),
):
    aid = _parse_uuid(artifact_id, "artifact_id")
    wid = _parse_uuid(workspace_id, "workspace_id")

    try:
        body_raw = await request.body()
        data = json.loads(body_raw) if body_raw else {}
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    # author_id MUST come from the gateway-injected X-User-Id header (from JWT).
    # Client-supplied author_id is ignored — prevents audit-trail spoofing.
    author_id_str = request.headers.get("X-User-Id")
    body_text = data.get("body")

    if not author_id_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing author_id")
    if not body_text or not isinstance(body_text, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid body")

    author_id = _parse_uuid(str(author_id_str), "author_id")

    try:
        annotation = ArtifactAnnotation.create(
            artifact_id=aid,
            workspace_id=wid,
            author_id=author_id,
            body=str(body_text),
        )
    except DomainValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    with get_uow() as uow:
        artifact = uow.artifacts.get_by_id(aid)
        if artifact is None or artifact.workspace_id != wid:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        uow.annotations.save(annotation)
        uow.commit()

    return _annotation_to_dict(annotation)
