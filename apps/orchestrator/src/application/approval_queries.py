"""Query handlers for approval operations.

Read-only operations — never mutate state.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.domain.approval_request import ApprovalRequest
from src.domain.errors import DomainError

from .ports import UnitOfWork


def list_approvals_by_workspace(
    workspace_id: UUID,
    uow: UnitOfWork,
    *,
    decision: str | None = None,
    reviewer_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ApprovalRequest]:
    """List approval requests in a workspace, optionally filtered by decision or reviewer."""
    with uow:
        return uow.approvals.list_by_workspace(
            workspace_id, decision=decision, reviewer_id=reviewer_id,
            limit=limit, offset=offset,
        )


def get_approval(approval_id: UUID, uow: UnitOfWork) -> ApprovalRequest:
    """Get an approval request by ID. Raises DomainError if not found."""
    with uow:
        approval = uow.approvals.get_by_id(approval_id)
        if approval is None:
            raise DomainError(f"ApprovalRequest {approval_id} not found")
        return approval


def count_pending_approvals(workspace_id: UUID, uow: UnitOfWork) -> int:
    """Count pending approval requests in a workspace."""
    with uow:
        return uow.approvals.count_pending_by_workspace(workspace_id)


def approval_to_dict(approval: ApprovalRequest) -> dict[str, Any]:
    """Serialize an ApprovalRequest to a dict suitable for JSON response."""
    result: dict[str, Any] = {
        "approval_id": str(approval.id),
        "workspace_id": str(approval.workspace_id),
        "target_type": approval.target_type.value,
        "target_id": str(approval.target_id),
        "requested_by": approval.requested_by,
        "reviewer_id": str(approval.reviewer_id) if approval.reviewer_id else None,
        "prompt": approval.prompt,
        "decision": approval.decision.value,
        "created_at": approval.created_at.isoformat(),
        "updated_at": approval.updated_at.isoformat(),
    }
    if approval.timeout_at:
        result["timeout_at"] = approval.timeout_at.isoformat()
    if approval.decided_by_id:
        result["decided_by_id"] = str(approval.decided_by_id)
    if approval.decided_at:
        result["decided_at"] = approval.decided_at.isoformat()
    if approval.decision_comment:
        result["decision_comment"] = approval.decision_comment
    return result
