"""Orchestrator internal API routes.

These routes are called by api-gateway (not directly by clients).
Command routes return 202 Accepted. Query routes return 200 with current state.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.application.bootstrap import get_dispatcher, get_execution_service, get_uow
from src.infrastructure.audit_clients import record_audit
from src.internal_auth import require_service
from src.application.commands import CancelTask, RetryTask, SubmitTask
from src.application.execution_loop import run_real_execution
from src.application.handlers import handle_cancel_task, handle_retry_task, handle_submit_task
from src.application.queries import (
    get_run,
    get_run_steps,
    get_task_with_latest_run,
    list_tasks_by_workspace,
    run_to_dict,
    step_to_dict,
    task_to_dict,
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
    info: dict = {"service": "orchestrator"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Command: Submit Task ───────────────────────────────────────

@router.post(
    "/internal/v1/tasks",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_task_endpoint(request: Request, background_tasks: BackgroundTasks, _claims=Depends(require_service("api-gateway"))):
    """Create and submit a new task. Returns 202 Accepted."""
    body = await request.json()

    # Gateway injects authenticated user via X-User-Id header — always override
    header_user_id = request.headers.get("x-user-id")
    if header_user_id:
        body["created_by_id"] = header_user_id

    required = ["workspace_id", "title", "task_type", "created_by_id"]
    for field in required:
        if field not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}",
            )

    try:
        cmd = SubmitTask(
            workspace_id=UUID(body["workspace_id"]),
            title=body["title"],
            task_type=body["task_type"],
            created_by_id=UUID(body["created_by_id"]),
            description=body.get("description"),
            input_config=body.get("input_config"),
            repo_snapshot_id=UUID(body["repo_snapshot_id"]) if body.get("repo_snapshot_id") else None,
            policy_id=UUID(body["policy_id"]) if body.get("policy_id") else None,
            parent_task_id=UUID(body["parent_task_id"]) if body.get("parent_task_id") else None,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    try:
        result = handle_submit_task(cmd, uow)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    task = result.task

    # Trigger real execution via agent-runtime + execution-service
    try:
        exec_uow = get_uow()
        dispatcher = get_dispatcher()
        try:
            execution_service = get_execution_service()
        except RuntimeError:
            execution_service = None  # Optional — not configured yet
        run_real_execution(task.id, exec_uow, dispatcher, execution_service)
    except Exception:
        logger.exception("Execution failed for task %s", task.id)

    background_tasks.add_task(
        record_audit,
        actor_id=str(task.created_by_id),
        action="task.created",
        workspace_id=task.workspace_id,
        target_id=str(task.id),
        target_type="task",
        metadata={"title": task.title[:200] if task.title else ""},
    )

    return {
        "task_id": str(task.id),
        "status": "accepted",
        "links": {"task": f"/v1/tasks/{task.id}"},
    }


# ── Command: Cancel Task ──────────────────────────────────────

@router.post(
    "/internal/v1/tasks/{task_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_task_endpoint(task_id: str, request: Request, background_tasks: BackgroundTasks, _claims=Depends(require_service("api-gateway"))):
    """Cancel a task and cascade to runs/steps. Returns 202 Accepted."""
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-User-Id header",
        )

    try:
        cmd = CancelTask(
            task_id=UUID(task_id),
            cancelled_by_id=UUID(user_id),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id or user_id format",
        )

    uow = get_uow()
    try:
        result = handle_cancel_task(cmd, uow)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    background_tasks.add_task(
        record_audit,
        actor_id=user_id,
        action="task.cancelled",
        workspace_id=result.task.workspace_id,
        target_id=str(result.task.id),
        target_type="task",
    )

    return {
        "task_id": str(result.task.id),
        "status": "accepted",
        "cancelled_runs": len(result.cancelled_runs),
        "cancelled_steps": len(result.cancelled_steps),
    }


# ── Command: Retry Task ───────────────────────────────────────

@router.post(
    "/internal/v1/tasks/{task_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_task_endpoint(task_id: str, request: Request, background_tasks: BackgroundTasks, _claims=Depends(require_service("api-gateway"))):
    """Retry a failed task (failed → pending, new Run queued). Returns 202 Accepted."""
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-User-Id header",
        )

    try:
        cmd = RetryTask(
            task_id=UUID(task_id),
            retried_by_id=UUID(user_id),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id or user_id format",
        )

    uow = get_uow()
    try:
        result = handle_retry_task(cmd, uow)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    background_tasks.add_task(
        record_audit,
        actor_id=user_id,
        action="task.retried",
        workspace_id=result.task.workspace_id,
        target_id=str(result.task.id),
        target_type="task",
    )

    return {
        "task_id": str(result.task.id),
        "status": "accepted",
    }


# ── Query: List Tasks ─────────────────────────────────────────

@router.get("/internal/v1/tasks")
def list_tasks_endpoint(
    workspace_id: str,
    _claims=Depends(require_service("api-gateway")),
    limit: int = 50,
    offset: int = 0,
):
    """List tasks for a workspace, ordered by most recently updated."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    uow = get_uow()
    tasks_with_runs = list_tasks_by_workspace(wid, uow, limit=limit, offset=offset)
    items = [task_to_dict(t, r) for t, r in tasks_with_runs]
    return {
        "items": items,
        "count": len(items),
    }


# ── Query: Get Task ───────────────────────────────────────────

@router.get("/internal/v1/tasks/{task_id}")
def get_task_endpoint(task_id: str, _claims=Depends(require_service("api-gateway"))):
    """Get task by ID with latest run info."""
    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format",
        )

    uow = get_uow()
    try:
        task, latest_run = get_task_with_latest_run(tid, uow)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return task_to_dict(task, latest_run)


# ── Query: List Runs by Task ──────────────────────────────────

@router.get("/internal/v1/workspaces/{workspace_id}/tasks/{task_id}/runs")
def list_runs_by_task_endpoint(
    workspace_id: str, task_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """List all runs for a task, newest first."""
    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task_id")

    uow = get_uow()
    with uow:
        runs = uow.runs.list_by_task(tid)
    return {"items": [run_to_dict(r) for r in runs], "count": len(runs)}


# ── Query: Get Run ─────────────────────────────────────────────

@router.get("/internal/v1/runs/{run_id}")
def get_run_endpoint(run_id: str, _claims=Depends(require_service("api-gateway"))):
    """Get run by ID."""
    try:
        rid = UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format",
        )

    uow = get_uow()
    try:
        run = get_run(rid, uow)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return run_to_dict(run)


# ── Query: Get Run Steps ──────────────────────────────────────

@router.get("/internal/v1/runs/{run_id}/steps")
def get_run_steps_endpoint(run_id: str, _claims=Depends(require_service("api-gateway"))):
    """Get all steps for a run, ordered by sequence."""
    try:
        rid = UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format",
        )

    uow = get_uow()
    try:
        run, steps = get_run_steps(rid, uow)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {
        "run_id": str(run.id),
        "workspace_id": str(run.workspace_id),
        "steps": [step_to_dict(s) for s in steps],
    }


# ── Internal: Outbox Relay Trigger ────────────────────────────

@router.post("/internal/v1/outbox/relay")
def trigger_outbox_relay(_claims=Depends(require_service("api-gateway", "orchestrator"))):
    """Trigger outbox relay to forward events to event-store.

    Phase B: manual/cron trigger. Phase C: background worker.
    """
    from src.application.bootstrap import get_session_factory
    from src.infrastructure.outbox.relay import relay_pending_events

    factory = get_session_factory()
    session = factory()
    try:
        relayed = relay_pending_events(session)
    finally:
        session.close()

    return {"relayed": relayed}
