"""Outbox event factories for approval operations.

Maps approval transitions to event types per doc 06.
"""

from __future__ import annotations

from uuid import UUID

from .events import OutboxEvent


def approval_requested_event(
    *,
    approval_id: UUID,
    workspace_id: UUID,
    target_type: str,
    target_id: UUID,
    requested_by: str,
    prompt: str | None = None,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="approval.requested",
        workspace_id=workspace_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "approval_id": str(approval_id),
            "target_type": target_type,
            "target_id": str(target_id),
            "requested_by": requested_by,
            "prompt": prompt,
        },
    )


def tool_approval_requested_event(
    *,
    approval_id: UUID,
    workspace_id: UUID,
    invocation_id: UUID,
    run_id: UUID,
    task_id: UUID,
    tool_name: str,
    risk_reason: str,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="tool_approval.requested",
        workspace_id=workspace_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "approval_id": str(approval_id),
            "target_type": "tool_call",
            "invocation_id": str(invocation_id),
            "run_id": str(run_id),
            "task_id": str(task_id),
            "tool_name": tool_name,
            "risk_reason": risk_reason,
        },
    )


def approval_decided_event(
    *,
    approval_id: UUID,
    workspace_id: UUID,
    decision: str,
    decided_by_id: UUID,
    target_type: str,
    target_id: UUID,
    comment: str | None = None,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="approval.decided",
        workspace_id=workspace_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "approval_id": str(approval_id),
            "decision": decision,
            "decided_by_id": str(decided_by_id),
            "target_type": target_type,
            "target_id": str(target_id),
            "comment": comment,
        },
    )


def tool_approval_decided_event(
    *,
    approval_id: UUID,
    workspace_id: UUID,
    invocation_id: UUID,
    decision: str,
    decided_by_id: UUID,
    tool_name: str | None = None,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="tool_approval.decided",
        workspace_id=workspace_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "approval_id": str(approval_id),
            "invocation_id": str(invocation_id),
            "decision": decision,
            "decided_by_id": str(decided_by_id),
            "tool_name": tool_name,
        },
    )
