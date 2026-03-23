"""Pydantic request/response schemas for policy API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CheckPermissionRequest(BaseModel):
    actor_id: str
    workspace_id: str
    permission: str
    role: str
    resource_id: str | None = None


class CheckPermissionResponse(BaseModel):
    allowed: bool
    reason: str


class CreatePolicyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scope: str = 'workspace'
    rules: list[dict] = Field(default_factory=list)


class UpdatePolicyRequest(BaseModel):
    name: str | None = None
    scope: str | None = None
    rules: list[dict] | None = None


class PolicyResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    scope: str
    rules: list
    is_default: bool
    created_at: str
    updated_at: str
