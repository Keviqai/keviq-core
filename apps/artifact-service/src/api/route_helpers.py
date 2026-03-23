"""Shared helper functions for artifact-service API routes.

Provides parsing, validation, error mapping, and serialization utilities
used across all route modules.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import NoReturn
from uuid import UUID

from fastapi import HTTPException, Request, status

from src.domain.errors import (
    ArtifactNotFoundError,
    DomainError,
    DomainValidationError,
    IncompleteProvenanceError,
    InvalidTransitionError,
    LineageCycleError,
    LineageSelfLoopError,
    ModelAliasError,
)

logger = logging.getLogger(__name__)

_MAX_QUERY_LIMIT = 200


def artifact_to_dict(artifact) -> dict:
    """Serialize artifact domain object to API response dict.

    Note: storage_ref is NOT exposed (internal reference only, per doc 07).
    """
    return {
        "id": str(artifact.id),
        "workspace_id": str(artifact.workspace_id),
        "task_id": str(artifact.task_id),
        "run_id": str(artifact.run_id),
        "step_id": str(artifact.step_id) if artifact.step_id else None,
        "agent_invocation_id": str(artifact.agent_invocation_id) if artifact.agent_invocation_id else None,
        "artifact_type": artifact.artifact_type.value,
        "artifact_status": artifact.artifact_status.value,
        "root_type": artifact.root_type.value,
        "name": artifact.name,
        "mime_type": artifact.mime_type,
        "size_bytes": artifact.size_bytes,
        "checksum": artifact.checksum,
        "lineage": artifact.lineage,
        "metadata": artifact.metadata,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "updated_at": artifact.updated_at.isoformat() if artifact.updated_at else None,
        "ready_at": artifact.ready_at.isoformat() if artifact.ready_at else None,
        "failed_at": artifact.failed_at.isoformat() if artifact.failed_at else None,
    }


def parse_uuid(value: str, field_name: str) -> UUID:
    """Parse a string as UUID, raising 400 on invalid format."""
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format — expected UUID",
        )


def parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime string, raising 400 on invalid format."""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format — expected ISO 8601, got '{value}'",
        )


async def parse_body(request: Request) -> dict:
    """Parse JSON body, raising 400 on malformed input."""
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing JSON body",
        )


def require_fields(body: dict, fields: list[str]) -> None:
    """Check that all required fields are present and not None."""
    for f in fields:
        if f not in body or body[f] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {f}",
            )


def handle_domain_error(e: DomainError) -> NoReturn:
    """Map domain errors to HTTP exceptions. Always raises."""
    if isinstance(e, ArtifactNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (InvalidTransitionError, LineageCycleError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, LineageSelfLoopError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, (ModelAliasError, IncompleteProvenanceError, DomainValidationError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def verify_workspace(artifact, workspace_id: UUID) -> None:
    """Verify artifact belongs to workspace. Returns 404 to avoid leaking existence."""
    if artifact.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact.id} not found",
        )


def check_artifact_workspace(uow, artifact_id: UUID, workspace_id: UUID) -> None:
    """Verify artifact exists and belongs to workspace. Raises 404 if not."""
    artifact = uow.artifacts.get_by_id(artifact_id)
    if artifact is None:
        raise ArtifactNotFoundError(str(artifact_id))
    verify_workspace(artifact, workspace_id)


# ── Preview helpers ──────────────────────────────────────────

PREVIEW_MAX_BYTES = 1_048_576  # 1 MB
PREVIEWABLE_MIMES = frozenset({
    "text/plain", "text/markdown", "text/x-markdown", "application/json",
})


def repair_double_encoded_utf8(text: str) -> str:
    """Repair double-encoded UTF-8 in mixed content.

    Finds runs of non-ASCII chars that are cp1252-encodable, tries to
    decode the resulting bytes as UTF-8, and replaces if valid.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ord(ch) > 127:
            buf = bytearray()
            j = i
            while j < n and ord(text[j]) > 127:
                try:
                    buf.extend(text[j].encode("cp1252"))
                except UnicodeEncodeError:
                    break
                j += 1
            if buf:
                try:
                    result.append(buf.decode("utf-8"))
                    i = j
                    continue
                except UnicodeDecodeError:
                    pass
            result.append(ch)
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def resolve_preview_kind(mime_type: str | None, artifact_type: str | None = None) -> str:
    """Map a mime type to a preview_kind label.

    Falls back to text for model_output artifacts with unknown MIME type.
    """
    effective_mime = mime_type
    if not effective_mime and artifact_type == "model_output":
        effective_mime = "text/plain"
    if not effective_mime or effective_mime not in PREVIEWABLE_MIMES:
        return "unsupported"
    if effective_mime == "application/json":
        return "json"
    if effective_mime in ("text/markdown", "text/x-markdown"):
        return "markdown"
    return "text"
