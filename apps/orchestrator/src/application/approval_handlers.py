"""Command handlers for approval operations.

Decide (approve/reject) an approval request and transition the target entity.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from src.domain.approval_request import ApprovalRequest, ApprovalTargetType
from src.domain.errors import DomainError

logger = logging.getLogger(__name__)

from .approval_commands import CreateApprovalRequest, DecideApproval
from .approval_events import approval_decided_event, approval_requested_event
from .ports import UnitOfWork


def handle_create_approval(
    cmd: CreateApprovalRequest, uow: UnitOfWork,
) -> ApprovalRequest:
    """Create a user-initiated approval request (Q4-S1).

    requested_by must come from the gateway-injected X-User-Id header —
    never trust client-supplied identity for audit fields.
    """
    target_type = ApprovalTargetType(cmd.target_type)

    with uow:
        approval = ApprovalRequest(
            workspace_id=cmd.workspace_id,
            target_type=target_type,
            target_id=cmd.target_id,
            requested_by=cmd.requested_by,
            reviewer_id=cmd.reviewer_id,
            prompt=cmd.prompt,
        )
        uow.approvals.save(approval)

        uow.outbox.write(approval_requested_event(
            approval_id=approval.id,
            workspace_id=approval.workspace_id,
            target_type=approval.target_type.value,
            target_id=approval.target_id,
            requested_by=approval.requested_by,
            prompt=approval.prompt,
            correlation_id=cmd.correlation_id,
        ))

        uow.commit()

    return approval


def handle_decide_approval(
    cmd: DecideApproval, uow: UnitOfWork,
) -> ApprovalRequest:
    """Approve or reject a pending approval request.

    Uses FOR UPDATE lock to prevent concurrent decisions.
    On approve, also transitions the target entity back to running.
    """
    with uow:
        approval = uow.approvals.get_by_id_for_update(cmd.approval_id)
        if approval is None:
            raise DomainError(f"ApprovalRequest {cmd.approval_id} not found")

        if str(approval.workspace_id) != str(cmd.workspace_id):
            raise DomainError("Approval does not belong to this workspace")

        # Domain transition — will raise if already decided
        if cmd.decision == "approve":
            approval.approve(cmd.decided_by_id, cmd.comment)
            _transition_target_on_approve(approval, uow)
        elif cmd.decision == "reject":
            approval.reject(cmd.decided_by_id, cmd.comment)
        else:
            raise DomainError(f"Invalid decision: {cmd.decision!r}")

        uow.approvals.save(approval)

        uow.outbox.write(approval_decided_event(
            approval_id=approval.id,
            workspace_id=approval.workspace_id,
            decision=approval.decision.value,
            decided_by_id=cmd.decided_by_id,
            target_type=approval.target_type.value,
            target_id=approval.target_id,
            comment=cmd.comment,
            correlation_id=uuid4(),
        ))

        uow.commit()

    return approval


def _transition_target_on_approve(
    approval: ApprovalRequest, uow: UnitOfWork,
) -> None:
    """When approved, transition target entity: waiting_approval → running."""
    target_type = approval.target_type.value

    if target_type == "task":
        entity = uow.tasks.get_by_id(approval.target_id)
        if entity:
            entity.approve()
            uow.tasks.save(entity)
        else:
            logger.warning("Approval %s: target task %s not found", approval.id, approval.target_id)
    elif target_type == "run":
        entity = uow.runs.get_by_id(approval.target_id)
        if entity:
            entity.approve()
            uow.runs.save(entity)
        else:
            logger.warning("Approval %s: target run %s not found", approval.id, approval.target_id)
    elif target_type == "step":
        entity = uow.steps.get_by_id(approval.target_id)
        if entity:
            entity.approve()
            uow.steps.save(entity)
        else:
            logger.warning("Approval %s: target step %s not found", approval.id, approval.target_id)
    elif target_type == "artifact":
        # Artifact approvals are user-initiated review gates (Q4-S1).
        # No entity state transition required — approval decision is the outcome itself.
        logger.info("Approval %s: artifact target %s approved (no entity transition needed)", approval.id, approval.target_id)
    elif target_type == "tool_call":
        # Tool call approvals are system-initiated gates (O5-S1).
        # target_id = invocation_id. Resume handled by agent-runtime in O5-S2.
        # No orchestrator entity transition — agent-runtime owns invocation lifecycle.
        logger.info(
            "Approval %s: tool_call target (invocation %s) approved — "
            "agent-runtime resume pending (O5-S2)",
            approval.id, approval.target_id,
        )
