"""Artifact-service content routes: upload, download, preview."""

from __future__ import annotations

import json
import logging
import mimetypes
import os

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response

from src.application.bootstrap import get_uow, get_storage_backend
from src.application.services import upload_artifact
from src.domain.artifact import ArtifactStatus
from src.internal_auth import require_service
from src.api.route_helpers import (
    PREVIEW_MAX_BYTES, parse_uuid, repair_double_encoded_utf8,
    resolve_preview_kind, verify_workspace,
)

logger = logging.getLogger(__name__)
content_router = APIRouter()

UPLOAD_MAX_BYTES = int(os.getenv("ARTIFACT_UPLOAD_MAX_BYTES", str(25 * 1024 * 1024)))


def _detect_mime_type(filename: str | None, client_content_type: str | None) -> str:
    """Determine mime type from filename extension, falling back to client hint."""
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    if client_content_type and client_content_type != "application/octet-stream":
        return client_content_type
    return "application/octet-stream"


# ── Command: Upload Artifact ─────────────────────────────────

@content_router.post("/internal/v1/workspaces/{workspace_id}/artifacts/upload")
def upload_artifact_endpoint(
    workspace_id: str,
    request: Request,
    file: UploadFile = File(...),
    artifact_name: str = Query(None, description="Display name (defaults to filename)"),
    artifact_type: str = Query("file", description="Artifact type"),
    _claims=Depends(require_service("api-gateway")),
):
    """Upload a file as a new artifact with root_type=uploaded.

    Returns 201 with artifact details, or 413 if file exceeds size limit.
    """
    wid = parse_uuid(workspace_id, "workspace_id")
    uploader_user_id = request.headers.get("x-user-id", "unknown")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(65_536)
        if not chunk:
            break
        total += len(chunk)
        if total > UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds upload limit of {UPLOAD_MAX_BYTES} bytes",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    original_filename = file.filename or "unnamed"
    name = artifact_name or original_filename
    mime_type = _detect_mime_type(original_filename, file.content_type)

    storage = get_storage_backend()
    uow = get_uow()

    try:
        artifact = upload_artifact(
            workspace_id=wid, name=name, artifact_type=artifact_type,
            mime_type=mime_type, content=content,
            uploader_user_id=uploader_user_id,
            original_filename=original_filename,
            uow=uow, storage_backend=storage, correlation_id=None,
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")

    return Response(
        content=json.dumps({
            "id": str(artifact.id),
            "name": artifact.name,
            "artifact_type": artifact.artifact_type.value,
            "root_type": artifact.root_type.value,
            "artifact_status": artifact.artifact_status.value,
            "mime_type": artifact.mime_type,
            "size_bytes": artifact.size_bytes,
            "checksum": artifact.checksum,
            "workspace_id": str(artifact.workspace_id),
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            "uploader_user_id": uploader_user_id,
            "original_filename": original_filename,
        }),
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
    )


# ── Query: Download Artifact Content ─────────────────────────

@content_router.get("/internal/v1/artifacts/{artifact_id}/download")
def download_artifact_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Stream artifact content. Only READY artifacts are downloadable."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact {artifact_id} not found")
    verify_workspace(artifact, wid)

    if artifact.artifact_status != ArtifactStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Artifact {artifact_id} is not downloadable — "
                   f"status is {artifact.artifact_status.value}, expected ready",
        )

    storage = get_storage_backend()
    storage_key = artifact.storage_ref
    if not storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact {artifact_id} has no storage reference")

    if storage_key.startswith("inline://"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This artifact was created with an older storage format. Content is not available for download.",
        )

    try:
        content = storage.read_content(storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact content not found at storage location")

    content_type = artifact.mime_type or "application/octet-stream"
    safe_name = (artifact.name
                  .replace('\\', '_').replace('"', '_')
                  .replace('\n', '_').replace('\r', '_').replace('\x00', '_'))
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "X-Content-Type-Options": "nosniff",
    }
    if artifact.checksum:
        headers["ETag"] = f'"{artifact.checksum}"'
    if artifact.size_bytes is not None:
        headers["Content-Length"] = str(len(content))

    return Response(content=content, media_type=content_type, headers=headers)


# ── Query: Preview Artifact Content ──────────────────────────

@content_router.get("/internal/v1/artifacts/{artifact_id}/preview")
def preview_artifact_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Return a JSON preview payload for text-based artifacts."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)

    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact {artifact_id} not found")
    verify_workspace(artifact, wid)

    if artifact.artifact_status != ArtifactStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Artifact {artifact_id} is not previewable — "
                   f"status is {artifact.artifact_status.value}, expected ready",
        )

    preview_kind = resolve_preview_kind(artifact.mime_type, artifact.artifact_type)

    if preview_kind == "unsupported":
        return {
            "artifact_id": artifact_id, "mime_type": artifact.mime_type,
            "preview_kind": "unsupported", "size_bytes": artifact.size_bytes,
            "truncated": False, "content": None,
        }

    if artifact.size_bytes is not None and artifact.size_bytes > PREVIEW_MAX_BYTES:
        return {
            "artifact_id": artifact_id, "mime_type": artifact.mime_type,
            "preview_kind": "too_large", "size_bytes": artifact.size_bytes,
            "truncated": False, "content": None,
        }

    storage = get_storage_backend()
    storage_key = artifact.storage_ref
    if not storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Artifact {artifact_id} has no storage reference")

    if storage_key.startswith("inline://"):
        return {
            "artifact_id": artifact_id, "mime_type": artifact.mime_type,
            "preview_kind": "unavailable", "size_bytes": artifact.size_bytes,
            "truncated": False, "content": None,
        }

    try:
        raw = storage.read_content(storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact content not found at storage location")

    truncated = len(raw) > PREVIEW_MAX_BYTES
    if truncated:
        raw = raw[:PREVIEW_MAX_BYTES]

    text = raw.decode("utf-8", errors="replace")
    text = repair_double_encoded_utf8(text)

    if preview_kind == "json":
        try:
            json.loads(text)
        except (json.JSONDecodeError, ValueError):
            preview_kind = "text"

    return {
        "artifact_id": artifact_id, "mime_type": artifact.mime_type,
        "preview_kind": preview_kind, "size_bytes": artifact.size_bytes,
        "truncated": truncated, "content": text,
    }
