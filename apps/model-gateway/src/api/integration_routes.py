"""Integration management API routes — workspace-scoped CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.integration_schemas import (
    CreateIntegrationRequest,
    IntegrationResponse,
    UpdateIntegrationRequest,
)
from src.application import integration_service
from src.application.integration_bootstrap import get_integration_session_factory
from src.domain.integration import IntegrationNotFound

integration_router = APIRouter()


def _get_db():
    db = get_integration_session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Integration CRUD ───────────────────────────────────────────


@integration_router.get(
    "/v1/workspaces/{workspace_id}/integrations",
    response_model=list[IntegrationResponse],
)
def list_integrations(
    workspace_id: uuid.UUID,
    db=Depends(_get_db),
    limit: int = 50,
    offset: int = 0,
):
    limit = max(1, min(limit, 200))
    offset = max(0, min(offset, 10000))
    return integration_service.list_integrations(
        db, workspace_id, limit=limit, offset=offset,
    )


@integration_router.post(
    "/v1/workspaces/{workspace_id}/integrations",
    response_model=IntegrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_integration(
    workspace_id: uuid.UUID,
    body: CreateIntegrationRequest,
    request: Request,
    db=Depends(_get_db),
):
    raw_user_id = request.headers.get('x-user-id', '')
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-User-Id header",
        )
    try:
        user_id = str(uuid.UUID(raw_user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-User-Id header",
        )
    try:
        result = integration_service.create_integration(
            db,
            workspace_id=workspace_id,
            name=body.name,
            integration_type=body.integration_type,
            provider_kind=body.provider_kind,
            created_by_id=user_id,
            endpoint_url=body.endpoint_url,
            default_model=body.default_model,
            api_key_secret_ref=body.api_key_secret_ref,
            description=body.description,
            is_enabled=body.is_enabled,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    return IntegrationResponse(**result)


@integration_router.get(
    "/v1/workspaces/{workspace_id}/integrations/{integration_id}",
    response_model=IntegrationResponse,
)
def get_integration(
    workspace_id: uuid.UUID,
    integration_id: uuid.UUID,
    db=Depends(_get_db),
):
    try:
        return integration_service.get_integration(db, integration_id, workspace_id)
    except IntegrationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )


@integration_router.patch(
    "/v1/workspaces/{workspace_id}/integrations/{integration_id}",
    response_model=IntegrationResponse,
)
def update_integration(
    workspace_id: uuid.UUID,
    integration_id: uuid.UUID,
    body: UpdateIntegrationRequest,
    db=Depends(_get_db),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    try:
        result = integration_service.update_integration(
            db, integration_id, updates, workspace_id,
        )
    except IntegrationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        )
    return IntegrationResponse(**result)


@integration_router.delete(
    "/v1/workspaces/{workspace_id}/integrations/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_integration(
    workspace_id: uuid.UUID,
    integration_id: uuid.UUID,
    db=Depends(_get_db),
):
    try:
        integration_service.delete_integration(db, integration_id, workspace_id)
    except IntegrationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )


@integration_router.post(
    "/v1/workspaces/{workspace_id}/integrations/{integration_id}/toggle",
    response_model=IntegrationResponse,
)
def toggle_integration(
    workspace_id: uuid.UUID,
    integration_id: uuid.UUID,
    db=Depends(_get_db),
):
    try:
        return integration_service.toggle_integration(db, integration_id, workspace_id)
    except IntegrationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
