"""Pydantic request/response schemas for workspace API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$')
    display_name: str = Field(..., min_length=1, max_length=200)


class UpdateWorkspaceRequest(BaseModel):
    display_name: str | None = None
    settings: dict | None = None


class WorkspaceResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    plan: str
    deployment_mode: str
    owner_id: str
    created_at: str
    updated_at: str
    settings: dict


class InviteMemberRequest(BaseModel):
    user_id: str
    role: str = 'viewer'


class UpdateMemberRoleRequest(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    joined_at: str
    updated_at: str
    invited_by_id: str | None
    display_name: str | None = None
    email: str | None = None
