"""Workspace API routes."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status

from src.api.schemas import (
    CreateWorkspaceRequest,
    InviteMemberRequest,
    MemberResponse,
    UpdateMemberRoleRequest,
    UpdateWorkspaceRequest,
)
from src.application import workspace_service
from src.application.bootstrap import get_session_factory
from src.domain.capabilities import resolve_capabilities
from src.domain.workspace_errors import (
    InvalidRole,
    MemberAlreadyExists,
    MemberNotFound,
    SlugAlreadyExists,
    WorkspaceNotFound,
)

router = APIRouter()


def _get_db():
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _get_user_id(x_user_id: str = Header(...)) -> uuid.UUID:
    """Extract user_id from X-User-Id header (injected by api-gateway)."""
    return uuid.UUID(x_user_id)


def _get_correlation_id(x_correlation_id: str | None = Header(None)) -> uuid.UUID | None:
    """Extract correlation_id from header if present."""
    if x_correlation_id:
        return uuid.UUID(x_correlation_id)
    return None


def _inject_capabilities(ws: dict, role: str | None) -> dict:
    """Inject _capabilities into workspace dict based on user's role.
    Non-members (role=None) get empty capabilities."""
    ws['_capabilities'] = resolve_capabilities(role) if role else []
    return ws


def _get_user_role(db, workspace_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    """Look up user's role in workspace. Returns None if not a member."""
    try:
        member = workspace_service.get_member(db, workspace_id, user_id)
        return member['role']
    except MemberNotFound:
        return None


def _require_membership(db, workspace_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Require user to be a workspace member. Returns role or raises 404."""
    role = _get_user_role(db, workspace_id, user_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return role


@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "workspace-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Workspaces ─────────────────────────────────────────────────────


@router.post("/v1/workspaces", status_code=status.HTTP_201_CREATED)
def create_workspace(
    body: CreateWorkspaceRequest,
    user_id: uuid.UUID = Depends(_get_user_id),
    correlation_id: uuid.UUID | None = Depends(_get_correlation_id),
    db=Depends(_get_db),
):
    try:
        result = workspace_service.create_workspace(
            db, body.slug, body.display_name, user_id,
            correlation_id=correlation_id,
        )
        return _inject_capabilities(result, 'owner')
    except SlugAlreadyExists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")


@router.get("/v1/workspaces")
def list_workspaces(
    user_id: uuid.UUID = Depends(_get_user_id),
    db=Depends(_get_db),
    limit: int = 50,
    offset: int = 0,
):
    workspaces = workspace_service.list_workspaces(db, user_id, limit=limit, offset=offset)
    for ws in workspaces:
        # _member_role is included from the JOIN query — no extra DB call
        role = ws.pop('_member_role', None)
        _inject_capabilities(ws, role)
    return workspaces


@router.get("/v1/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(_get_user_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    try:
        ws = workspace_service.get_workspace(db, workspace_id)
        return _inject_capabilities(ws, role)
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.patch("/v1/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: uuid.UUID,
    body: UpdateWorkspaceRequest,
    user_id: uuid.UUID = Depends(_get_user_id),
    correlation_id: uuid.UUID | None = Depends(_get_correlation_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    if role not in ('owner', 'admin'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        result = workspace_service.update_workspace(
            db, workspace_id, updates,
            actor_id=user_id, correlation_id=correlation_id,
        )
        return _inject_capabilities(result, role)
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


@router.delete("/v1/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(_get_user_id),
    correlation_id: uuid.UUID | None = Depends(_get_correlation_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    if role != 'owner':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only workspace owner can delete")
    try:
        workspace_service.delete_workspace(
            db, workspace_id,
            actor_id=user_id, correlation_id=correlation_id,
        )
    except WorkspaceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


# ── Members ────────────────────────────────────────────────────────


@router.get("/v1/workspaces/{workspace_id}/members", response_model=list[MemberResponse])
def list_members(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(_get_user_id),
    db=Depends(_get_db),
    limit: int = 200,
    offset: int = 0,
):
    _require_membership(db, workspace_id, user_id)
    return workspace_service.list_members(db, workspace_id, limit=limit, offset=offset)


@router.post(
    "/v1/workspaces/{workspace_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    workspace_id: uuid.UUID,
    body: InviteMemberRequest,
    user_id: uuid.UUID = Depends(_get_user_id),
    correlation_id: uuid.UUID | None = Depends(_get_correlation_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    if role not in ('owner', 'admin'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        return workspace_service.invite_member(
            db,
            workspace_id=workspace_id,
            user_id=uuid.UUID(body.user_id),
            role=body.role,
            invited_by_id=user_id,
            correlation_id=correlation_id,
        )
    except MemberAlreadyExists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")
    except InvalidRole:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")


@router.patch("/v1/workspaces/{workspace_id}/members/{member_user_id}", response_model=MemberResponse)
def update_member_role(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    user_id: uuid.UUID = Depends(_get_user_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    if role not in ('owner', 'admin'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        return workspace_service.update_member_role(db, workspace_id, member_user_id, body.role)
    except MemberNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    except InvalidRole:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")


@router.delete("/v1/workspaces/{workspace_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user_id: uuid.UUID = Depends(_get_user_id),
    correlation_id: uuid.UUID | None = Depends(_get_correlation_id),
    db=Depends(_get_db),
):
    role = _require_membership(db, workspace_id, user_id)
    # Members can remove themselves; only owner/admin can remove others
    if member_user_id != user_id and role not in ('owner', 'admin'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    try:
        workspace_service.remove_member(
            db, workspace_id, member_user_id,
            actor_id=user_id, correlation_id=correlation_id,
        )
    except MemberNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
