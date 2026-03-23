"""Policy API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas import (
    CheckPermissionRequest,
    CheckPermissionResponse,
    CreatePolicyRequest,
    PolicyResponse,
    UpdatePolicyRequest,
)
from src.application import policy_service
from src.application.bootstrap import get_session_factory
from src.domain.policy_errors import PolicyNotFound

router = APIRouter()


def _get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "policy-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Internal API (called by api-gateway) ──────────────────────────


@router.post("/internal/v1/check-permission", response_model=CheckPermissionResponse)
def check_permission(body: CheckPermissionRequest, db=Depends(_get_db)):
    result = policy_service.check_permission(
        db,
        actor_id=uuid.UUID(body.actor_id),
        workspace_id=uuid.UUID(body.workspace_id),
        permission=body.permission,
        role=body.role,
        resource_id=body.resource_id,
    )
    return CheckPermissionResponse(**result)


# ── Public API (proxied via api-gateway) ───────────────────────────


@router.get("/v1/workspaces/{workspace_id}/policies", response_model=list[PolicyResponse])
def list_policies(
    workspace_id: uuid.UUID,
    db=Depends(_get_db),
    limit: int = 50,
    offset: int = 0,
):
    return policy_service.list_policies(db, workspace_id, limit=limit, offset=offset)


@router.post(
    "/v1/workspaces/{workspace_id}/policies",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_policy(
    workspace_id: uuid.UUID,
    body: CreatePolicyRequest,
    db=Depends(_get_db),
):
    result = policy_service.create_policy(
        db,
        workspace_id=workspace_id,
        name=body.name,
        scope=body.scope,
        rules=body.rules,
    )
    return PolicyResponse(**result)


@router.get("/v1/workspaces/{workspace_id}/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(workspace_id: uuid.UUID, policy_id: uuid.UUID, db=Depends(_get_db)):
    try:
        policy = policy_service.get_policy(db, policy_id)
    except PolicyNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    if str(policy['workspace_id']) != str(workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return PolicyResponse(**policy)


@router.patch("/v1/workspaces/{workspace_id}/policies/{policy_id}", response_model=PolicyResponse)
def update_policy(
    workspace_id: uuid.UUID,
    policy_id: uuid.UUID,
    body: UpdatePolicyRequest,
    db=Depends(_get_db),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        result = policy_service.update_policy(db, policy_id, updates)
    except PolicyNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    if str(result['workspace_id']) != str(workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return PolicyResponse(**result)
