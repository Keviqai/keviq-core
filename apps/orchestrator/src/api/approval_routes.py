"""Approval request API routes for orchestrator.

Internal routes called by api-gateway. Workspace-scoped.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from src.application.approval_commands import CreateApprovalRequest, DecideApproval
from src.application.approval_handlers import handle_create_approval, handle_decide_approval
from src.application.approval_queries import (
    approval_to_dict,
    count_pending_approvals,
    get_approval,
    list_approvals_by_workspace,
)
from src.application.bootstrap import get_uow
from src.domain.errors import DomainError, InvalidTransitionError
from src.infrastructure.audit_clients import record_audit
from src.infrastructure.notification_clients import (
    notify_approval_decided,
    notify_approval_requested,
)
from src.infrastructure.runtime_resume_client import resume_invocation
from src.infrastructure.service_clients import (
    enrich_approval_list_with_artifact_names,
    get_artifact_context,
    validate_artifact_in_workspace,
    validate_workspace_member,
)
from src.internal_auth import require_service

logger = logging.getLogger(__name__)

router = APIRouter()


_VALID_DECISIONS = {"pending", "approved", "rejected", "timed_out", "cancelled"}


@router.get("/internal/v1/workspaces/{workspace_id}/approvals")
def list_approvals_endpoint(
    workspace_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
    decision: str | None = None,
    reviewer_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List approval requests for a workspace.

    reviewer_id="me" resolves to the calling user's ID (from X-User-Id header).
    reviewer_id=<uuid> filters by that specific reviewer.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    if decision and decision not in _VALID_DECISIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid decision filter",
        )

    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    resolved_reviewer_id: UUID | None = None
    if reviewer_id == "me":
        user_id_header = request.headers.get("x-user-id")
        if not user_id_header:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")
        try:
            resolved_reviewer_id = UUID(user_id_header)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-User-Id header")
    elif reviewer_id:
        try:
            resolved_reviewer_id = UUID(reviewer_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reviewer_id format")

    uow = get_uow()
    approvals = list_approvals_by_workspace(
        wid, uow, decision=decision, reviewer_id=resolved_reviewer_id,
        limit=limit, offset=offset,
    )
    items = [approval_to_dict(a) for a in approvals]
    enrich_approval_list_with_artifact_names(items, approvals)
    return {"items": items, "count": len(items)}


@router.get("/internal/v1/workspaces/{workspace_id}/approvals/count")
def approval_count_endpoint(
    workspace_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """Count pending approval requests for a workspace."""
    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    uow = get_uow()
    count = count_pending_approvals(wid, uow)
    return {"pending_count": count}


@router.get("/internal/v1/workspaces/{workspace_id}/approvals/{approval_id}")
def get_approval_endpoint(
    workspace_id: str,
    approval_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """Get a single approval request with context."""
    try:
        wid = UUID(workspace_id)
        aid = UUID(approval_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id or approval_id format",
        )

    uow = get_uow()
    try:
        approval = get_approval(aid, uow)
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if approval.workspace_id != wid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found in this workspace",
        )

    result = approval_to_dict(approval)

    # Enrich with artifact context when target is an artifact
    if approval.target_type.value == "artifact":
        context = get_artifact_context(approval.target_id, approval.workspace_id)
        result["artifact_context"] = context

    return result


@router.post(
    "/internal/v1/workspaces/{workspace_id}/approvals",
    status_code=status.HTTP_201_CREATED,
)
async def create_approval_endpoint(
    workspace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _claims=Depends(require_service("api-gateway")),
):
    """Create a user-initiated approval request (artifact target only).

    requested_by is taken from the gateway-injected X-User-Id header (never from body).
    reviewer_id is optional; validated as workspace member if provided.
    target_id artifact is validated to belong to this workspace.
    """
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    target_id_str = body.get("target_id", "")
    prompt = str(body.get("prompt", "")).strip()
    reviewer_id_str = body.get("reviewer_id") or None

    if not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="prompt is required")
    if len(prompt) > 2000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="prompt too long (max 2000 characters)")
    if not target_id_str:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="target_id is required")

    try:
        wid = UUID(workspace_id)
        tid = UUID(str(target_id_str))
        uid = UUID(str(user_id))
        rid = UUID(str(reviewer_id_str)) if reviewer_id_str else None
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    # Cross-workspace artifact validation (Q4-S1 debt resolved here)
    if not validate_artifact_in_workspace(tid, wid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Artifact does not belong to this workspace",
        )

    # Reviewer must be a workspace member if provided
    if rid and not validate_workspace_member(wid, rid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reviewer is not a member of this workspace",
        )

    cmd = CreateApprovalRequest(
        workspace_id=wid,
        target_type="artifact",
        target_id=tid,
        requested_by=str(uid),
        prompt=prompt,
        correlation_id=uuid4(),
        reviewer_id=rid,
    )
    uow = get_uow()
    try:
        approval = handle_create_approval(cmd, uow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    background_tasks.add_task(notify_approval_requested, approval.id, wid, str(uid), rid)
    background_tasks.add_task(
        record_audit,
        actor_id=str(uid),
        action="approval.requested",
        workspace_id=wid,
        target_id=str(tid),
        target_type="artifact",
        metadata={"approval_id": str(approval.id), "prompt": prompt[:200]},
    )
    return approval_to_dict(approval)


@router.post(
    "/internal/v1/workspaces/{workspace_id}/approvals/{approval_id}/decide",
    status_code=status.HTTP_202_ACCEPTED,
)
async def decide_approval_endpoint(
    workspace_id: str,
    approval_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _claims=Depends(require_service("api-gateway")),
):
    """Approve or reject an approval request. Returns 202 Accepted."""
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-User-Id header")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    decision = body.get("decision")
    # O5-S3: "override" and "cancel" are valid for tool_call approvals
    valid_decisions = ("approve", "reject", "override", "cancel")
    if decision not in valid_decisions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"decision must be one of {valid_decisions}")

    comment = body.get("comment")
    if comment and len(comment) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment too long (max 2000 characters)")

    override_output = body.get("override_output")
    if decision == "override" and not override_output:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="override_output is required for override decision")
    if override_output and len(override_output) > 32768:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="override_output too large (max 32KB)")

    # O5-S3: Map override/cancel to domain-level approve/reject
    # Domain only knows approve/reject; override/cancel are agent-runtime semantics
    domain_decision = decision
    if decision == "override":
        domain_decision = "approve"  # approval is granted, output is overridden
    elif decision == "cancel":
        domain_decision = "reject"  # approval is denied, invocation cancelled

    # Annotate comment with original decision for audit trail
    domain_comment = comment
    if decision in ("override", "cancel"):
        prefix = f"[{decision}] "
        domain_comment = prefix + (comment or "")

    try:
        cmd = DecideApproval(
            approval_id=UUID(approval_id),
            workspace_id=UUID(workspace_id),
            decided_by_id=UUID(user_id),
            decision=domain_decision,
            comment=domain_comment,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    uow = get_uow()
    try:
        approval = handle_decide_approval(cmd, uow)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    background_tasks.add_task(
        notify_approval_decided,
        approval.id, approval.workspace_id, approval.requested_by,
        approval.decision.value, approval.target_id,
    )
    background_tasks.add_task(
        record_audit,
        actor_id=str(cmd.decided_by_id),
        action="approval.decided",
        workspace_id=approval.workspace_id,
        target_id=str(approval.target_id),
        target_type=approval.target_type.value,
        metadata={
            "approval_id": str(approval.id),
            "decision": decision,  # original decision (approve/reject/override/cancel)
        },
    )

    # O5-S2/S3: Resume agent-runtime invocation for tool_call approvals
    if approval.target_type.value == "tool_call":
        # Pass the original decision (not domain_decision) to agent-runtime
        # so it knows whether to dispatch tool, override, or cancel
        runtime_decision = decision if decision in ("override", "cancel") else approval.decision.value
        background_tasks.add_task(
            resume_invocation,
            approval.target_id,  # target_id = invocation_id
            approval.workspace_id,
            runtime_decision,
            cmd.comment,
            override_output if decision == "override" else None,
        )

    return {
        "approval_id": str(approval.id),
        "decision": approval.decision.value,
        "status": "accepted",
    }
