"""Execution-service internal API routes.

These routes are called by other services (not directly by clients).
Command routes return 202 Accepted. Query routes return 200 with current state.
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.internal_auth import require_service

from src.application.bootstrap import get_execution_backend, get_sandbox_backend, get_uow
from src.application.sandbox_service import (
    get_sandbox,
    list_active_sandboxes,
    provision_sandbox,
    terminate_sandbox,
)
from src.application.tool_execution_service import execute_tool, get_execution
from src.domain.contracts import (
    SandboxProvisionRequest,
    SandboxTerminationRequest,
    ToolExecutionRequest,
)
from src.domain.errors import DomainError, InvalidTransitionError

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Health ─────────────────────────────────────────────────────

@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "execution-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
        info["execution_backend"] = os.getenv("EXECUTION_BACKEND", "docker-local")
    return info


# ── Command: Provision Sandbox ────────────────────────────────

@router.post(
    "/internal/v1/sandboxes/provision",
    status_code=status.HTTP_202_ACCEPTED,
)
async def provision_sandbox_endpoint(request: Request, _claims=Depends(require_service("orchestrator"))):
    """Provision a new sandbox. Returns 202 Accepted."""
    body = await request.json()

    required = [
        "workspace_id", "task_id", "run_id", "step_id",
        "agent_invocation_id", "sandbox_type",
    ]
    for field in required:
        if field not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}",
            )

    try:
        req = SandboxProvisionRequest.from_dict(body)
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    backend = get_sandbox_backend()

    try:
        result = provision_sandbox(req, uow, backend)
    except (ValueError, DomainError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return result.to_dict()


# ── Command: Terminate Sandbox ────────────────────────────────

@router.post(
    "/internal/v1/sandboxes/{sandbox_id}/terminate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def terminate_sandbox_endpoint(sandbox_id: str, request: Request, _claims=Depends(require_service("orchestrator"))):
    """Terminate a sandbox. Returns 202 Accepted."""
    try:
        sid = UUID(sandbox_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sandbox_id format",
        )

    # Parse optional JSON body safely
    raw = await request.body()
    body: dict = {}
    if raw:
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body",
            )

    reason = body.get("reason", "completed")
    req = SandboxTerminationRequest(sandbox_id=sid, reason=reason)

    uow = get_uow()
    backend = get_sandbox_backend()

    try:
        result = terminate_sandbox(req, uow, backend)
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return result.to_dict()


# ── Query: Get Sandbox ────────────────────────────────────────

@router.get("/internal/v1/sandboxes/{sandbox_id}")
def get_sandbox_endpoint(
    sandbox_id: str,
    workspace_id: str | None = None,
    _claims=Depends(require_service("orchestrator", "api-gateway")),
):
    """Get sandbox by ID."""
    try:
        sid = UUID(sandbox_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sandbox_id format",
        )

    uow = get_uow()
    try:
        sandbox = get_sandbox(sid, uow)
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Workspace isolation when called via api-gateway
    if workspace_id and str(sandbox.workspace_id) != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found in this workspace",
        )

    return {
        "sandbox_id": str(sandbox.id),
        "workspace_id": str(sandbox.workspace_id),
        "task_id": str(sandbox.task_id),
        "run_id": str(sandbox.run_id),
        "step_id": str(sandbox.step_id),
        "agent_invocation_id": str(sandbox.agent_invocation_id),
        "sandbox_type": sandbox.sandbox_type.value,
        "sandbox_status": sandbox.sandbox_status.value,
        "started_at": sandbox.started_at.isoformat() if sandbox.started_at else None,
        "terminated_at": sandbox.terminated_at.isoformat() if sandbox.terminated_at else None,
        "termination_reason": (
            sandbox.termination_reason.value if sandbox.termination_reason else None
        ),
        "created_at": sandbox.created_at.isoformat(),
        "updated_at": sandbox.updated_at.isoformat(),
    }


# ── Query: List Active Sandboxes ──────────────────────────────

@router.get("/internal/v1/sandboxes")
def list_sandboxes_endpoint(_claims=Depends(require_service("orchestrator"))):
    """List active sandboxes."""
    uow = get_uow()
    sandboxes = list_active_sandboxes(uow)
    return {
        "sandboxes": [
            {
                "sandbox_id": str(s.id),
                "sandbox_type": s.sandbox_type.value,
                "sandbox_status": s.sandbox_status.value,
                "created_at": s.created_at.isoformat(),
            }
            for s in sandboxes
        ],
    }


# ── Command: Execute Tool ────────────────────────────────────

@router.post(
    "/internal/v1/tool-executions",
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_tool_endpoint(request: Request, _claims=Depends(require_service("orchestrator", "agent-runtime"))):
    """Execute a registered tool inside a sandbox. Returns 202 Accepted."""
    body = await request.json()

    required = ["sandbox_id", "attempt_index", "tool_name"]
    for field in required:
        if field not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}",
            )

    try:
        req = ToolExecutionRequest.from_dict(body)
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    execution_backend = get_execution_backend()

    try:
        # Run in threadpool — execute_tool blocks on Docker exec.
        result = await asyncio.to_thread(execute_tool, req, uow, execution_backend)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return result.to_dict()


# ── Query: Get Execution ─────────────────────────────────────

@router.get("/internal/v1/tool-executions/{execution_id}")
def get_execution_endpoint(
    execution_id: str,
    workspace_id: str | None = None,
    _claims=Depends(require_service("orchestrator", "api-gateway")),
):
    """Get tool execution by ID.

    When called via api-gateway, workspace_id is required for workspace isolation.
    The execution's sandbox must belong to the requested workspace.
    """
    try:
        eid = UUID(execution_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid execution_id format",
        )

    uow = get_uow()
    try:
        attempt = get_execution(eid, uow)
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Workspace isolation: validate sandbox belongs to requested workspace
    if workspace_id:
        sandbox_id = attempt.get("sandbox_id")
        if sandbox_id:
            with uow:
                sandbox = uow.sandboxes.get_by_id(UUID(str(sandbox_id)))
                if sandbox is None or str(sandbox.workspace_id) != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Execution not found in this workspace",
                    )

    return {
        "execution_id": attempt["id"],
        "sandbox_id": attempt["sandbox_id"],
        "attempt_index": attempt["attempt_index"],
        "tool_name": attempt["tool_name"],
        "tool_input": attempt.get("tool_input"),
        "status": attempt["status"],
        "stdout": attempt.get("stdout"),
        "stderr": attempt.get("stderr"),
        "exit_code": attempt.get("exit_code"),
        "truncated": attempt.get("truncated", False),
        "error_detail": attempt.get("error_detail"),
        "started_at": (
            attempt["started_at"].isoformat()
            if attempt.get("started_at") else None
        ),
        "completed_at": (
            attempt["completed_at"].isoformat()
            if attempt.get("completed_at") else None
        ),
    }
