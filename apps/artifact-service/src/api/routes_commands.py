"""Artifact command routes: register, begin_writing, write_content, finalize, fail."""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from src.application.bootstrap import get_uow, get_storage_backend
from src.application.services import (
    RegisterArtifactCommand, begin_writing, fail_artifact,
    finalize_artifact, register_artifact,
)
from src.domain.errors import DomainError
from src.internal_auth import require_service
from src.api.route_helpers import (
    check_artifact_workspace, handle_domain_error,
    parse_body, parse_uuid, require_fields,
)

logger = logging.getLogger(__name__)
commands_router = APIRouter()


@commands_router.post(
    "/internal/v1/artifacts/register",
    status_code=status.HTTP_202_ACCEPTED,
)
async def register_artifact_endpoint(request: Request, _claims=Depends(require_service("agent-runtime"))):
    """Register a new artifact in PENDING state. Returns 202 Accepted."""
    body = await parse_body(request)

    require_fields(body, ["workspace_id", "task_id", "run_id", "name", "artifact_type"])

    try:
        cmd = RegisterArtifactCommand(
            workspace_id=parse_uuid(body["workspace_id"], "workspace_id"),
            task_id=parse_uuid(body["task_id"], "task_id"),
            run_id=parse_uuid(body["run_id"], "run_id"),
            name=body["name"],
            artifact_type=body["artifact_type"],
            root_type=body.get("root_type", "generated"),
            step_id=parse_uuid(body["step_id"], "step_id") if body.get("step_id") else None,
            agent_invocation_id=parse_uuid(body["agent_invocation_id"], "agent_invocation_id") if body.get("agent_invocation_id") else None,
            mime_type=body.get("mime_type"),
            model_provider=body.get("model_provider"),
            model_name_concrete=body.get("model_name_concrete"),
            model_version_concrete=body.get("model_version_concrete"),
            model_temperature=body.get("model_temperature"),
            model_max_tokens=body.get("model_max_tokens"),
            system_prompt_hash=body.get("system_prompt_hash"),
            run_config_hash=body.get("run_config_hash"),
            tool_name=body.get("tool_name"),
            tool_version=body.get("tool_version"),
            tool_config_hash=body.get("tool_config_hash"),
            input_snapshot=body.get("input_snapshot"),
            lineage_chain=body.get("lineage_chain"),
            correlation_id=parse_uuid(body["correlation_id"], "correlation_id") if body.get("correlation_id") else None,
        )
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    try:
        artifact = register_artifact(cmd, uow)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate artifact — agent_invocation_id already has an artifact registered",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value: {e}",
        )
    except DomainError as e:
        handle_domain_error(e)

    return {
        "artifact_id": str(artifact.id),
        "status": "accepted",
        "artifact_status": artifact.artifact_status.value,
    }


# ── Command: Begin Writing ────────────────────────────────────

@commands_router.post(
    "/internal/v1/artifacts/{artifact_id}/begin-writing",
    status_code=status.HTTP_202_ACCEPTED,
)
async def begin_writing_endpoint(artifact_id: str, request: Request, _claims=Depends(require_service("agent-runtime"))):
    """Transition artifact from PENDING to WRITING. Returns 202 Accepted."""
    aid = parse_uuid(artifact_id, "artifact_id")
    body = await parse_body(request)

    require_fields(body, ["workspace_id", "storage_ref"])

    wid = parse_uuid(body["workspace_id"], "workspace_id")
    cid = parse_uuid(body["correlation_id"], "correlation_id") if body.get("correlation_id") else None

    uow = get_uow()
    try:
        with uow:
            check_artifact_workspace(uow, aid, wid)

        artifact = begin_writing(
            aid,
            storage_ref=body["storage_ref"],
            uow=get_uow(),
            correlation_id=cid,
        )
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value: {e}",
        )
    except DomainError as e:
        handle_domain_error(e)

    return {
        "artifact_id": str(artifact.id),
        "status": "accepted",
        "artifact_status": artifact.artifact_status.value,
    }


# ── Command: Write Artifact Content ──────────────────────────
@commands_router.post("/internal/v1/artifacts/{artifact_id}/content")
async def write_content_endpoint(
    artifact_id: str, request: Request,
    _claims=Depends(require_service("agent-runtime")),
):
    """Write base64-encoded content to an artifact in WRITING state."""
    aid = parse_uuid(artifact_id, "artifact_id")
    body = await parse_body(request)

    content_b64 = body.get("content_base64")
    if not content_b64:
        raise HTTPException(status_code=400, detail="content_base64 is required")

    try:
        content = base64.b64decode(content_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if artifact.artifact_status.value != "writing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Artifact must be in 'writing' state, got '{artifact.artifact_status.value}'",
            )
        storage_key = artifact.storage_ref
        if not storage_key:
            raise HTTPException(status_code=400, detail="Artifact has no storage_ref")

    storage = get_storage_backend()
    storage.write_content(storage_key, content)

    return {"artifact_id": str(aid), "bytes_written": len(content)}


def _write_inline_content(aid, artifact_id: str, content_b64: str) -> None:
    """Decode base64 content and write to artifact storage."""
    try:
        content_bytes = base64.b64decode(content_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 in content_base64")

    uow_pre = get_uow()
    with uow_pre:
        art = uow_pre.artifacts.get_by_id(aid)
        if art and art.storage_ref:
            storage = get_storage_backend()
            storage.write_content(art.storage_ref, content_bytes)
            logger.info(
                "Content written for artifact %s (%d bytes) at %s",
                artifact_id, len(content_bytes), art.storage_ref,
            )
        else:
            logger.warning(
                "Cannot write content for artifact %s: art=%s storage_ref=%s",
                artifact_id, art is not None, getattr(art, 'storage_ref', None),
            )


# ── Command: Finalize Artifact ────────────────────────────────
@commands_router.post(
    "/internal/v1/artifacts/{artifact_id}/finalize",
    status_code=status.HTTP_202_ACCEPTED,
)
async def finalize_artifact_endpoint(artifact_id: str, request: Request, _claims=Depends(require_service("agent-runtime"))):
    """Validate provenance + checksum, transition to READY. Returns 202 Accepted."""
    aid = parse_uuid(artifact_id, "artifact_id")
    body = await parse_body(request)

    require_fields(body, ["workspace_id", "checksum", "size_bytes"])

    wid = parse_uuid(body["workspace_id"], "workspace_id")
    cid = parse_uuid(body["correlation_id"], "correlation_id") if body.get("correlation_id") else None

    # Validate size_bytes before passing to service
    try:
        size_bytes = int(body["size_bytes"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="size_bytes must be a valid integer",
        )

    # If content_base64 is provided, write content before finalizing
    content_b64 = body.get("content_base64")
    if content_b64:
        _write_inline_content(aid, artifact_id, content_b64)

    uow = get_uow()
    try:
        with uow:
            check_artifact_workspace(uow, aid, wid)

        artifact = finalize_artifact(
            aid,
            checksum=body["checksum"],
            size_bytes=size_bytes,
            uow=get_uow(),
            correlation_id=cid,
        )
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value: {e}",
        )
    except DomainError as e:
        handle_domain_error(e)

    return {
        "artifact_id": str(artifact.id),
        "status": "accepted",
        "artifact_status": artifact.artifact_status.value,
        "checksum": artifact.checksum,
    }


# ── Command: Fail Artifact ───────────────────────────────────

@commands_router.post(
    "/internal/v1/artifacts/{artifact_id}/fail",
    status_code=status.HTTP_202_ACCEPTED,
)
async def fail_artifact_endpoint(artifact_id: str, request: Request, _claims=Depends(require_service("agent-runtime"))):
    """Transition artifact to FAILED state. Returns 202 Accepted."""
    aid = parse_uuid(artifact_id, "artifact_id")
    body = await parse_body(request)

    require_fields(body, ["workspace_id"])

    wid = parse_uuid(body["workspace_id"], "workspace_id")
    cid = parse_uuid(body["correlation_id"], "correlation_id") if body.get("correlation_id") else None

    uow = get_uow()
    try:
        with uow:
            check_artifact_workspace(uow, aid, wid)

        artifact = fail_artifact(
            aid,
            failure_reason=body.get("failure_reason"),
            partial_data=body.get("partial_data", False),
            uow=get_uow(),
            correlation_id=cid,
        )
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value: {e}",
        )
    except DomainError as e:
        handle_domain_error(e)

    return {
        "artifact_id": str(artifact.id),
        "status": "accepted",
        "artifact_status": artifact.artifact_status.value,
    }
