"""Model gateway API routes.

Internal service API — not exposed through api-gateway to external clients.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.internal_auth import require_service

from src.application.model_service import ModelExecutionService
from src.domain.contracts import (
    ExecuteModelError,
    ExecuteModelRequest,
    ExecuteModelResult,
    ModelProfile,
)

router = APIRouter()


# ── Health checks ────────────────────────────────────────────────

@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    info: dict = {"service": "model-gateway"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Model execution ─────────────────────────────────────────────

class InvokeModelBody(BaseModel):
    request_id: UUID
    agent_invocation_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    model_alias: str = Field(..., min_length=1)
    messages: list[dict[str, Any]] = Field(..., min_length=1)
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_ms: int = Field(default=30_000, ge=1000, le=300_000)
    tools: list[dict[str, Any]] | None = None


class InvokeModelResponse(BaseModel):
    request_id: UUID
    provider_name: str
    model_concrete: str
    output_text: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tool_calls: list[dict[str, Any]] | None = None


class InvokeModelErrorResponse(BaseModel):
    request_id: UUID
    error_code: str
    error_message: str
    provider_name: str
    retryable: bool


_service: ModelExecutionService | None = None


def configure_service(service: ModelExecutionService) -> None:
    """Set the service singleton. Called once at startup by main.py."""
    global _service
    _service = service


def _get_service() -> ModelExecutionService:
    """Get the configured service instance."""
    if _service is None:
        raise RuntimeError("ModelExecutionService not configured — call configure_service() at startup")
    return _service


@router.post(
    "/v1/models/invoke",
    status_code=status.HTTP_200_OK,
)
def invoke_model(body: InvokeModelBody, _claims=Depends(require_service("agent-runtime"))):
    """Execute a model call via the configured provider.

    Internal API for agent-runtime consumption.
    """
    service = _get_service()

    request = ExecuteModelRequest(
        request_id=body.request_id,
        agent_invocation_id=body.agent_invocation_id,
        workspace_id=body.workspace_id,
        correlation_id=body.correlation_id,
        model_profile=ModelProfile(
            model_alias=body.model_alias,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        ),
        messages=body.messages,
        timeout_ms=body.timeout_ms,
        tools=body.tools,
    )

    result = service.execute(request)

    if isinstance(result, ExecuteModelError):
        raise HTTPException(
            status_code=_error_status_code(result.error_code),
            detail=InvokeModelErrorResponse(
                request_id=result.request_id,
                error_code=result.error_code,
                error_message=result.error_message,
                provider_name=result.provider_name,
                retryable=result.retryable,
            ).model_dump(mode="json"),
        )

    return InvokeModelResponse(
        request_id=result.request_id,
        provider_name=result.provider_name,
        model_concrete=result.model_concrete,
        output_text=result.output_text,
        finish_reason=result.finish_reason,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_tokens=result.usage.total_tokens,
        tool_calls=result.tool_calls,
    )


def _error_status_code(error_code: str) -> int:
    """Map domain error codes to HTTP status codes."""
    if error_code in ("PROVIDER_NOT_FOUND", "CONFIG_ERROR"):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if error_code == "PROVIDER_DISABLED":
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if error_code == "TIMEOUT":
        return status.HTTP_504_GATEWAY_TIMEOUT
    return status.HTTP_502_BAD_GATEWAY
