"""Tool approval API routes for orchestrator.

Internal routes called by agent-runtime when a tool call requires human approval.
Creates an approval request with target_type=tool_call and emits tool_approval.requested.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.application.approval_commands import CreateApprovalRequest
from src.application.approval_events import tool_approval_requested_event
from src.application.approval_handlers import handle_create_approval
from src.application.approval_queries import approval_to_dict
from src.application.bootstrap import get_uow
from src.infrastructure.notification_clients import notify_approval_requested
from src.internal_auth import require_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/internal/v1/tool-approvals",
    status_code=status.HTTP_201_CREATED,
)
async def create_tool_approval_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    _claims=Depends(require_service("agent-runtime")),
):
    """Create a tool approval request from agent-runtime.

    Called when the tool approval policy gates a tool call.
    Creates approval with target_type=tool_call and emits tool_approval.requested event.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # Required fields
    workspace_id_str = body.get("workspace_id")
    invocation_id_str = body.get("invocation_id")
    run_id_str = body.get("run_id")
    task_id_str = body.get("task_id")
    tool_name = body.get("tool_name", "")
    risk_reason = body.get("risk_reason", "")
    arguments_preview = body.get("arguments_preview", "")

    if not all([workspace_id_str, invocation_id_str, run_id_str, task_id_str, tool_name]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace_id, invocation_id, run_id, task_id, tool_name are required",
        )

    try:
        wid = UUID(str(workspace_id_str))
        invocation_id = UUID(str(invocation_id_str))
        run_id = UUID(str(run_id_str))
        task_id = UUID(str(task_id_str))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format",
        )

    # Truncate arguments preview for safety
    if len(arguments_preview) > 2000:
        arguments_preview = arguments_preview[:2000] + "..."

    # Build prompt from tool context
    prompt = (
        f"Tool '{tool_name}' requires approval.\n"
        f"Reason: {risk_reason}\n"
        f"Arguments: {arguments_preview}"
    )

    correlation_id = uuid4()

    cmd = CreateApprovalRequest(
        workspace_id=wid,
        target_type="tool_call",
        target_id=invocation_id,  # target_id = invocation that needs approval
        requested_by="system",  # system-initiated, not user-initiated
        prompt=prompt,
        correlation_id=correlation_id,
    )

    uow = get_uow()
    try:
        approval = handle_create_approval(cmd, uow)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Write tool_approval.requested event (separate from generic approval.requested)
    uow_event = get_uow()
    with uow_event:
        uow_event.outbox.write(tool_approval_requested_event(
            approval_id=approval.id,
            workspace_id=wid,
            invocation_id=invocation_id,
            run_id=run_id,
            task_id=task_id,
            tool_name=tool_name,
            risk_reason=risk_reason,
            correlation_id=correlation_id,
        ))
        uow_event.commit()

    # Notify workspace managers of pending tool approval
    background_tasks.add_task(
        notify_approval_requested,
        approval.id, wid, "system", None,
    )

    result = approval_to_dict(approval)
    result["tool_context"] = {
        "invocation_id": str(invocation_id),
        "run_id": str(run_id),
        "task_id": str(task_id),
        "tool_name": tool_name,
        "risk_reason": risk_reason,
        "arguments_preview": arguments_preview,
    }

    logger.info(
        "Tool approval created: approval_id=%s tool=%s invocation=%s",
        approval.id, tool_name, invocation_id,
    )

    return result
