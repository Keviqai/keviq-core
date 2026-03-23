"""Pydantic request/response schemas for integration management API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateIntegrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    integration_type: str = Field(..., pattern=r'^(llm_provider)$')
    provider_kind: str = Field(..., pattern=r'^(openai|anthropic|azure_openai|custom)$')
    endpoint_url: str | None = Field(default=None, max_length=500)
    default_model: str | None = Field(default=None, max_length=100)
    api_key_secret_ref: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_enabled: bool = True


class UpdateIntegrationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    integration_type: str | None = Field(default=None, pattern=r'^(llm_provider)$')
    provider_kind: str | None = Field(default=None, pattern=r'^(openai|anthropic|azure_openai|custom)$')
    endpoint_url: str | None = Field(default=None, max_length=500)
    default_model: str | None = Field(default=None, max_length=100)
    api_key_secret_ref: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_enabled: bool | None = None


class IntegrationResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    integration_type: str
    provider_kind: str
    endpoint_url: str
    default_model: str
    api_key_secret_ref: str
    description: str
    is_enabled: bool
    config: dict | None
    created_by_id: str
    created_at: str
    updated_at: str
