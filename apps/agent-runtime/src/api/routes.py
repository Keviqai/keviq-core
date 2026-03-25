"""Agent-runtime API routes.

Internal service API — health checks + execution endpoint + recovery.
Not exposed through api-gateway to external clients.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.internal_auth import require_service

logger = logging.getLogger(__name__)

_INVOCATION_STUCK_TIMEOUT_S = int(os.getenv('INVOCATION_STUCK_TIMEOUT_S', '300'))

router = APIRouter()


# ── Health checks ────────────────────────────────────────────────

@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info() -> dict[str, str]:
    import os
    info: dict = {"service": "agent-runtime"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Execution endpoint ──────────────────────────────────────────

class ExecuteInvocationBody(BaseModel):
    agent_invocation_id: UUID
    workspace_id: UUID
    task_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    agent_id: str = Field(..., min_length=1)
    model_alias: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    sandbox_id: UUID | None = None
    timeout_ms: int = Field(default=30_000, ge=1000, le=300_000)
    max_tokens: int | None = None
    temperature: float | None = None


_service = None
_service_lock = threading.Lock()


def _get_service():
    """Build execution handler with real dependencies. Thread-safe singleton."""
    global _service
    if _service is not None:
        return _service

    with _service_lock:
        if _service is not None:
            return _service

        from sqlalchemy import create_engine

        from src.application.execution_handler import ExecuteInvocationHandler
        from src.infrastructure.artifact_client import ArtifactServiceClient
        from src.infrastructure.db.unit_of_work import DbInvocationUnitOfWork
        from src.infrastructure.execution_service_client import HttpExecutionServiceClient
        from src.infrastructure.gateway_client import ModelGatewayClient
        from src.infrastructure.tool_approval_client import HttpToolApprovalClient

        db_url = os.environ.get("AGENT_RUNTIME_DB_URL")
        if not db_url:
            raise RuntimeError("AGENT_RUNTIME_DB_URL environment variable is required")

        gw_url = os.environ.get("MODEL_GATEWAY_URL")
        if not gw_url:
            raise RuntimeError("MODEL_GATEWAY_URL environment variable is required")

        engine = create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)

        # Artifact service is optional — runtime works without it
        artifact_service = None
        artifact_url = os.environ.get("ARTIFACT_SERVICE_URL")
        if artifact_url:
            artifact_service = ArtifactServiceClient(base_url=artifact_url)

        # Execution service is optional — tool loop requires it
        execution_service = None
        exec_url = os.environ.get("EXECUTION_SERVICE_URL")
        if exec_url:
            execution_service = HttpExecutionServiceClient(base_url=exec_url)

        # Tool approval service is optional — approval gate requires it
        tool_approval_service = None
        orchestrator_url = os.environ.get("ORCHESTRATOR_URL")
        if orchestrator_url:
            tool_approval_service = HttpToolApprovalClient()

        _service = ExecuteInvocationHandler(
            unit_of_work=DbInvocationUnitOfWork(engine),
            gateway=ModelGatewayClient(base_url=gw_url),
            artifact_service=artifact_service,
            execution_service=execution_service,
            tool_approval_service=tool_approval_service,
        )
        return _service


@router.post(
    "/internal/v1/invocations/execute",
    status_code=status.HTTP_200_OK,
)
def execute_invocation(body: ExecuteInvocationBody, _claims=Depends(require_service("orchestrator"))):
    """Execute an agent invocation synchronously.

    Internal API for orchestrator consumption.
    Returns execution result or failure details.
    """
    from src.domain.execution_contracts import (
        ExecutionFailure,
        ExecutionRequest,
        ModelProfile,
    )

    service = _get_service()

    request = ExecutionRequest(
        agent_invocation_id=body.agent_invocation_id,
        workspace_id=body.workspace_id,
        task_id=body.task_id,
        run_id=body.run_id,
        step_id=body.step_id,
        correlation_id=body.correlation_id,
        agent_id=body.agent_id,
        model_profile=ModelProfile(
            model_alias=body.model_alias,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        ),
        instruction=body.instruction,
        input_payload={
            **body.input_payload,
            **({"sandbox_id": str(body.sandbox_id)} if body.sandbox_id else {}),
        },
        timeout_ms=body.timeout_ms,
    )

    result = service.execute(request)

    if isinstance(result, ExecutionFailure):
        return {
            "agent_invocation_id": str(result.agent_invocation_id),
            "status": result.status.value,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "retryable": result.retryable,
        }

    return {
        "agent_invocation_id": str(result.agent_invocation_id),
        "status": result.status.value,
        "output_text": result.output_payload.get("output_text", ""),
        "prompt_tokens": result.usage.prompt_tokens,
        "completion_tokens": result.usage.completion_tokens,
        "model_concrete": result.usage.model_concrete,
        "artifact_id": str(result.artifact_id) if result.artifact_id else None,
    }


# ── Resume: tool approval resolution (O5-S2) ────────────────────

class ResumeInvocationBody(BaseModel):
    workspace_id: UUID
    decision: str = Field(..., pattern="^(approved|rejected|override|cancel)$")
    comment: str | None = None
    override_output: str | None = Field(default=None, max_length=32768)


_resume_service = None
_resume_lock = threading.Lock()


def _get_resume_service():
    """Build resume handler with real dependencies. Thread-safe singleton."""
    global _resume_service
    if _resume_service is not None:
        return _resume_service

    with _resume_lock:
        if _resume_service is not None:
            return _resume_service

        from sqlalchemy import create_engine

        from src.application.resume_handler import ResumeInvocationHandler
        from src.infrastructure.db.unit_of_work import DbInvocationUnitOfWork
        from src.infrastructure.execution_service_client import HttpExecutionServiceClient
        from src.infrastructure.gateway_client import ModelGatewayClient

        db_url = os.environ.get("AGENT_RUNTIME_DB_URL")
        if not db_url:
            raise RuntimeError("AGENT_RUNTIME_DB_URL not configured")

        gw_url = os.environ.get("MODEL_GATEWAY_URL")
        if not gw_url:
            raise RuntimeError("MODEL_GATEWAY_URL not configured")

        engine = create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=3, pool_recycle=3600)

        execution_service = None
        exec_url = os.environ.get("EXECUTION_SERVICE_URL")
        if exec_url:
            execution_service = HttpExecutionServiceClient(base_url=exec_url)

        _resume_service = ResumeInvocationHandler(
            unit_of_work=DbInvocationUnitOfWork(engine),
            gateway=ModelGatewayClient(base_url=gw_url),
            execution_service=execution_service,
        )
        return _resume_service


@router.post(
    "/internal/v1/invocations/{invocation_id}/resume",
    status_code=status.HTTP_200_OK,
)
def resume_invocation(
    invocation_id: str,
    body: ResumeInvocationBody,
    _claims=Depends(require_service("orchestrator")),
):
    """Resume a WAITING_HUMAN invocation after tool approval decision.

    Called by orchestrator when a TOOL_CALL approval is decided.
    decision must be "approved" or "rejected".
    """
    try:
        inv_id = UUID(invocation_id)
    except ValueError:
        return {"error": "INVALID_UUID", "message": "Invalid invocation_id format"}

    service = _get_resume_service()
    result = service.resume(
        invocation_id=inv_id,
        workspace_id=body.workspace_id,
        decision=body.decision,
        comment=body.comment,
        override_output=body.override_output,
    )
    return result


# ── Recovery: stuck invocation sweeper ──────────────────────────

_STUCK_STATES = ('initializing', 'starting', 'running', 'waiting_human', 'waiting_tool')

_STUCK_REASON_MAP = {
    'initializing': 'STUCK_INITIALIZING',
    'starting': 'STUCK_STARTING',
    'running': 'STUCK_RUNNING',
    'waiting_human': 'STUCK_WAITING_HUMAN',
    'waiting_tool': 'STUCK_WAITING_TOOL',
}


@router.post("/internal/v1/invocations/recover-stuck")
def recover_stuck_invocations(
    timeout_seconds: int | None = None,
    dry_run: bool = False,
    _claims=Depends(require_service("orchestrator")),
):
    """Recover invocations stuck in non-terminal states beyond timeout.

    Uses started_at for RUNNING/WAITING states, created_at for INITIALIZING/STARTING.
    Transitions each stuck invocation to FAILED with a per-state error code.
    """
    timeout_s = timeout_seconds or _INVOCATION_STUCK_TIMEOUT_S
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_s)
    now = datetime.now(timezone.utc)

    db_url = os.environ.get("AGENT_RUNTIME_DB_URL")
    if not db_url:
        return {"error": "AGENT_RUNTIME_DB_URL not configured", "recovered": 0}

    from sqlalchemy import create_engine
    engine = create_engine(db_url, pool_pre_ping=True)

    with engine.connect() as conn:
        # Find stuck invocations
        rows = conn.execute(
            text("""
                SELECT id, invocation_status, started_at, created_at
                FROM agent_runtime.agent_invocations
                WHERE invocation_status IN :states
                  AND completed_at IS NULL
                  AND COALESCE(started_at, created_at) < :cutoff
                ORDER BY created_at ASC
                LIMIT 100
            """),
            {"states": tuple(_STUCK_STATES), "cutoff": cutoff},
        ).fetchall()

        if dry_run or not rows:
            return {
                "dry_run": dry_run,
                "timeout_seconds": timeout_s,
                "cutoff": cutoff.isoformat(),
                "candidates": len(rows),
                "recovered": 0,
                "details": [
                    {"id": str(r.id), "status": r.invocation_status,
                     "age_seconds": int((now - (r.started_at or r.created_at)).total_seconds())}
                    for r in rows
                ],
            }

        # Recover each stuck invocation
        recovered = 0
        details = []
        for row in rows:
            error_code = _STUCK_REASON_MAP.get(row.invocation_status, 'STUCK_UNKNOWN')
            age_s = int((now - (row.started_at or row.created_at)).total_seconds())

            conn.execute(
                text("""
                    UPDATE agent_runtime.agent_invocations
                    SET invocation_status = 'failed',
                        completed_at = :now,
                        error_detail = CAST(:error_detail AS jsonb)
                    WHERE id = :id AND completed_at IS NULL
                """),
                {
                    "id": str(row.id),
                    "now": now,
                    "error_detail": __import__('json').dumps({
                        "error_code": error_code,
                        "error_message": f"Invocation stuck in {row.invocation_status} for {age_s}s (timeout: {timeout_s}s)",
                        "recovered_at": now.isoformat(),
                    }),
                },
            )
            recovered += 1
            details.append({"id": str(row.id), "status": row.invocation_status, "error_code": error_code, "age_seconds": age_s})
            logger.warning("Recovered stuck invocation %s: %s → failed (%s, age=%ds)",
                           row.id, row.invocation_status, error_code, age_s)

        conn.commit()

    return {
        "dry_run": False,
        "timeout_seconds": timeout_s,
        "cutoff": cutoff.isoformat(),
        "candidates": len(rows),
        "recovered": recovered,
        "details": details,
    }
