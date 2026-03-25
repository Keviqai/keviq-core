"""Secret-broker API routes."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.api.schemas import CreateSecretRequest, SecretResponse, UpdateSecretMetadataRequest
from src.application import secret_service
from src.application import key_rotation_service
from src.application.bootstrap import get_session_factory
from src.domain.secret_errors import SecretNotFound
from src.internal_auth import require_service

router = APIRouter()


def _get_db():
    db = get_session_factory()()
    try:
        yield db
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
    info: dict = {"service": "secret-broker"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Secret CRUD (called via api-gateway) ─────────────────────


@router.get("/v1/workspaces/{workspace_id}/secrets", response_model=list[SecretResponse])
def list_secrets(
    workspace_id: uuid.UUID,
    db=Depends(_get_db),
    limit: int = 50,
    offset: int = 0,
):
    return secret_service.list_secrets(db, workspace_id, limit=limit, offset=offset)


@router.post(
    "/v1/workspaces/{workspace_id}/secrets",
    response_model=SecretResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_secret(
    workspace_id: uuid.UUID,
    body: CreateSecretRequest,
    request: Request,
    db=Depends(_get_db),
):
    user_id = request.headers.get('x-user-id', '')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")

    try:
        result = secret_service.create_secret(
            db,
            workspace_id=workspace_id,
            name=body.name,
            secret_type=body.secret_type,
            raw_value=body.value,
            created_by_id=user_id,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SecretResponse(**result)


@router.delete(
    "/v1/workspaces/{workspace_id}/secrets/{secret_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_secret(workspace_id: uuid.UUID, secret_id: uuid.UUID, db=Depends(_get_db)):
    try:
        secret_service.delete_secret(db, secret_id, workspace_id=workspace_id)
    except SecretNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")


@router.patch(
    "/v1/workspaces/{workspace_id}/secrets/{secret_id}",
    response_model=SecretResponse,
)
def update_secret_metadata(
    workspace_id: uuid.UUID,
    secret_id: uuid.UUID,
    body: UpdateSecretMetadataRequest,
    db=Depends(_get_db),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        result = secret_service.update_secret_metadata(db, secret_id, updates, workspace_id=workspace_id)
    except SecretNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    return SecretResponse(**result)


# ── Internal: Decrypt secret value ────────────────────────────
# Only callable by model-gateway (service-to-service auth).
# Secret values are NEVER exposed via public API (docs/07-api-contracts.md).


@router.get(
    "/internal/v1/secrets/{secret_id}/value",
    dependencies=[Depends(require_service("model-gateway"))],
)
def get_secret_value(
    secret_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(..., description="Workspace scope for IDOR prevention"),
    db=Depends(_get_db),
):
    """Decrypt and return a secret value. Internal service use only."""
    try:
        value = secret_service.retrieve_secret_value(db, secret_id, workspace_id)
    except SecretNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return {"value": value}


# ── Internal: Key Rotation ─────────────────────────────────────
# Triggers re-encryption of workspace secrets with current key version.


@router.post(
    "/internal/v1/workspaces/{workspace_id}/secrets/rotate",
    dependencies=[Depends(require_service("secret-broker"))],
)
def rotate_workspace_secrets(
    workspace_id: uuid.UUID,
    db=Depends(_get_db),
):
    """Re-encrypt all secrets in a workspace to the current key version."""
    result = key_rotation_service.rotate_workspace_secrets(db, workspace_id)
    return {
        "rotated": result.rotated,
        "already_current": result.already_current,
        "errors": result.errors,
    }


@router.get(
    "/internal/v1/workspaces/{workspace_id}/secrets/rotation-status",
    dependencies=[Depends(require_service("secret-broker"))],
)
def get_rotation_status(
    workspace_id: uuid.UUID,
    db=Depends(_get_db),
):
    """Return count of secrets per key version for a workspace."""
    counts = key_rotation_service.get_rotation_status(db, workspace_id)
    return {
        "versions": [{"version": c.version, "count": c.count} for c in counts],
    }
