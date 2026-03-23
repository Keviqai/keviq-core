"""Pydantic request/response schemas for secret-broker API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSecretRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    secret_type: str = Field(..., pattern=r'^(api_key|token|password|custom)$')
    value: str = Field(..., min_length=1, max_length=10000)


class UpdateSecretMetadataRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class SecretResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    secret_type: str
    masked_display: str
    created_by_id: str
    created_at: str
    updated_at: str
