"""Task brief routes — draft creation and brief updates.

Q1 Delegation Clarity: structured task brief CRUD.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.application.bootstrap import get_uow
from src.infrastructure.audit_clients import record_audit
from src.application.commands import CreateTaskDraft, LaunchTask, UpdateTaskBrief
from src.application.handlers import handle_create_draft, handle_launch_task, handle_update_brief
from src.application.queries import task_to_dict
from src.domain.errors import DomainError
from src.internal_auth import require_service

router = APIRouter()


# ── Command: Create Task Draft ────────────────────────────────

@router.post(
    "/internal/v1/tasks/draft",
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_endpoint(
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Create a new task in DRAFT status. Returns 201 Created."""
    body = await request.json()

    header_user_id = request.headers.get("x-user-id")
    if header_user_id:
        body["created_by_id"] = header_user_id

    if "title" not in body or not body["title"].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="title is required",
        )
    if "workspace_id" not in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace_id is required",
        )

    user_id = body.get("created_by_id") or header_user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="created_by_id is required (or X-User-Id header)",
        )

    try:
        cmd = CreateTaskDraft(
            workspace_id=UUID(body["workspace_id"]),
            title=body["title"],
            task_type=body.get("task_type", "custom"),
            created_by_id=UUID(user_id),
            description=body.get("description"),
            goal=body.get("goal"),
            context=body.get("context"),
            constraints=body.get("constraints"),
            desired_output=body.get("desired_output"),
            template_id=UUID(body["template_id"]) if body.get("template_id") else None,
            agent_template_id=UUID(body["agent_template_id"]) if body.get("agent_template_id") else None,
            risk_level=body.get("risk_level"),
            input_config=body.get("input_config"),
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    try:
        result = handle_create_draft(cmd, uow)
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return task_to_dict(result.task)


# ── Command: Update Task Brief ───────────────────────────────

@router.patch(
    "/internal/v1/tasks/{task_id}",
    status_code=status.HTTP_200_OK,
)
async def update_task_endpoint(
    task_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Update brief fields on a draft task. Returns updated task."""
    body = await request.json()

    try:
        tid = UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id",
        )

    updates = dict(body)
    for uuid_field in ('template_id', 'agent_template_id'):
        if uuid_field in updates and updates[uuid_field]:
            try:
                updates[uuid_field] = UUID(updates[uuid_field])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid {uuid_field}",
                )

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    cmd = UpdateTaskBrief(task_id=tid, updates=updates)
    uow = get_uow()
    try:
        result = handle_update_brief(cmd, uow)
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

    return task_to_dict(result.task)


# ── Command: Launch Task ─────────────────────────────────────


@router.post(
    "/internal/v1/tasks/{task_id}/launch",
    status_code=status.HTTP_202_ACCEPTED,
)
async def launch_task_endpoint(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _claims=Depends(require_service("api-gateway")),
):
    """Validate and launch a draft task. Returns 202 Accepted."""
    import logging
    logger = logging.getLogger(__name__)

    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-User-Id header",
        )

    try:
        tid = UUID(task_id)
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id or user_id format",
        )

    cmd = LaunchTask(task_id=tid, launched_by_id=uid)
    uow = get_uow()
    try:
        result = handle_launch_task(cmd, uow)
    except DomainError as e:
        err_msg = str(e).lower()
        if "not found" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    task = result.task

    background_tasks.add_task(
        record_audit,
        actor_id=str(user_id),
        action="task.created",
        workspace_id=task.workspace_id,
        target_id=str(task.id),
        target_type="task",
        metadata={"title": task.title[:200] if task.title else ""},
    )

    # Trigger execution (same pattern as submit_task_endpoint)
    try:
        from src.application.bootstrap import get_dispatcher, get_execution_service
        from src.application.execution_loop import run_real_execution
        exec_uow = get_uow()
        dispatcher = get_dispatcher()
        try:
            execution_service = get_execution_service()
        except RuntimeError:
            execution_service = None
        run_real_execution(task.id, exec_uow, dispatcher, execution_service)
    except Exception:
        logger.exception("Execution failed for task %s", task.id)

    return {
        "task_id": str(task.id),
        "status": "accepted",
        "links": {"task": f"/v1/tasks/{task.id}"},
    }
