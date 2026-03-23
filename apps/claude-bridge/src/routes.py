"""HTTP routes for the Claude Code CLI bridge service.

LOCAL-ONLY: This bridge is designed for single-user local development.
It must not be deployed as a shared or production service.

Endpoints:
  GET  /internal/v1/health  — liveness probe
  GET  /internal/v1/status  — bridge readiness (binary, auth, warnings)
  POST /internal/v1/query   — send a prompt through Claude Code CLI
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.cli_runner import check_status, invoke_cli

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ────────────────────────────────────────────


@router.get("/internal/v1/health")
def health():
    """Liveness probe — always returns ok."""
    return {"status": "ok", "service": "claude-bridge"}


@router.get("/healthz/live")
def liveness():
    """Standard Keviq Core liveness probe."""
    return {"status": "live"}


# ── Status ────────────────────────────────────────────


@router.get("/internal/v1/status")
def bridge_status():
    """Report bridge readiness: binary, auth state, warnings."""
    return check_status()


# ── Query ─────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Request body for /internal/v1/query."""

    prompt: str = Field(..., min_length=1, max_length=100_000)
    model: str = Field(default="sonnet")
    max_turns: int = Field(default=1, ge=1, le=10)
    timeout_s: int = Field(default=120, ge=10, le=600)


class QueryResponse(BaseModel):
    """Normalized response from Claude Code CLI."""

    output_text: str
    model_name: str
    is_error: bool = False
    error_message: str = ""
    cost_usd: float | None = None
    duration_ms: int = 0
    session_id: str = ""
    provider: str = "claude_code_cli"


@router.post("/internal/v1/query", response_model=QueryResponse)
def query(body: QueryRequest):
    """Send a prompt to Claude Code CLI and return the response.

    This calls `claude -p <prompt> --output-format json --model <model>`.
    The host machine must have Claude Code installed and logged in.
    """
    start = time.monotonic()

    result = invoke_cli(
        body.prompt,
        model=body.model,
        max_turns=body.max_turns,
        timeout_s=body.timeout_s,
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if result.is_error:
        logger.warning(
            "claude-bridge query failed: model=%s error=%s",
            body.model, result.error_message,
        )

    return QueryResponse(
        output_text=result.output_text,
        model_name=result.model_name,
        is_error=result.is_error,
        error_message=result.error_message,
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms or elapsed_ms,
        session_id=result.session_id,
    )
