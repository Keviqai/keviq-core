"""Resume handler — resumes a WAITING_HUMAN invocation after tool approval decision.

O5-S2: When a tool approval is decided (approved/rejected/override/cancel),
this handler loads the invocation, validates state, and routes to the
appropriate sub-handler:
  - Approved: resume_approved.py — dispatches the gated tool, continues model loop
  - Rejected: marks invocation FAILED with TOOL_REJECTED code
  - Override: resume_override.py — injects synthetic result, continues model loop
  - Cancel: marks invocation CANCELLED

This is a separate handler from ExecuteInvocationHandler to keep concerns clean.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.application.ports import (
    ExecutionServicePort,
    InvocationUnitOfWork,
    ModelGatewayPort,
)
from src.application.resume_approved import handle_approved
from src.application.resume_override import handle_override
from src.application.shared_execution import save_with_event
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation, InvocationStatus

logger = logging.getLogger(__name__)


class ResumeInvocationHandler:
    """Resumes a WAITING_HUMAN invocation after approval decision."""

    def __init__(
        self,
        *,
        unit_of_work: InvocationUnitOfWork,
        gateway: ModelGatewayPort,
        execution_service: ExecutionServicePort | None = None,
    ):
        self._uow = unit_of_work
        self._gateway = gateway
        self._execution_service = execution_service

    def resume(
        self,
        *,
        invocation_id: UUID,
        workspace_id: UUID,
        decision: str,
        comment: str | None = None,
        override_output: str | None = None,
    ) -> dict[str, Any]:
        """Resume, reject, override, or cancel an invocation.

        Args:
            invocation_id: The invocation to resume.
            workspace_id: Workspace for authorization.
            decision: "approved", "rejected", "override", or "cancel".
            comment: Optional reviewer comment.
            override_output: Required when decision="override".

        Returns:
            Dict with invocation_id, status, and outcome details.
        """
        # 1. Load invocation
        invocation = self._uow.invocations.get_by_id(invocation_id, workspace_id)
        if invocation is None:
            return {"error": "INVOCATION_NOT_FOUND", "invocation_id": str(invocation_id)}

        # 2. Validate state
        if invocation.invocation_status != InvocationStatus.WAITING_HUMAN:
            return {
                "error": "INVALID_STATE",
                "invocation_id": str(invocation_id),
                "current_status": invocation.invocation_status.value,
                "message": f"Cannot resume: invocation is {invocation.invocation_status.value}, not waiting_human",
            }

        # 3. Validate pending context
        ctx = invocation.pending_tool_context
        if not ctx or "tool_calls" not in ctx:
            logger.error(
                "Invocation %s in WAITING_HUMAN but missing pending_tool_context",
                invocation_id,
            )
            invocation.mark_failed(error_detail={
                "error_code": "MISSING_PENDING_CONTEXT",
                "error_message": "Cannot resume: pending_tool_context is missing or invalid",
            })
            save_with_event(self._uow, invocation, "agent_invocation.failed")
            return {
                "error": "MISSING_PENDING_CONTEXT",
                "invocation_id": str(invocation_id),
                "status": "failed",
            }

        # 4. Route by decision
        if decision == "approved":
            return handle_approved(
                invocation, ctx, comment,
                uow=self._uow,
                gateway=self._gateway,
                execution_service=self._execution_service,
            )
        elif decision == "rejected":
            return self._handle_rejected(invocation, ctx, comment)
        elif decision == "override":
            if not override_output:
                return {
                    "error": "MISSING_OVERRIDE_OUTPUT",
                    "message": "override_output is required for override decision",
                }
            return handle_override(
                invocation, ctx, comment, override_output,
                uow=self._uow,
                gateway=self._gateway,
                execution_service=self._execution_service,
            )
        elif decision == "cancel":
            return self._handle_cancel(invocation, ctx, comment)
        else:
            return {"error": "INVALID_DECISION", "message": f"Unknown decision: {decision}"}

    def _handle_rejected(
        self,
        invocation: AgentInvocation,
        ctx: dict[str, Any],
        comment: str | None,
    ) -> dict[str, Any]:
        """Rejected tool -> mark invocation FAILED with TOOL_REJECTED."""
        gated_tool = ctx.get("gated_tool_name", "unknown")
        reason = comment or ctx.get("gate_reason", "Tool approval rejected")

        invocation.mark_failed(error_detail={
            "error_code": "TOOL_REJECTED",
            "error_message": f"Tool '{gated_tool}' rejected by reviewer: {reason}",
            "gated_tool": gated_tool,
            "reviewer_comment": comment,
        })
        invocation.pending_tool_context = None  # consumed
        save_with_event(self._uow, invocation, "agent_invocation.failed")
        runtime_metrics.inc_human_gate("rejected")
        runtime_metrics.inc_invocation("failed")

        logger.info(
            "Invocation %s: tool '%s' rejected — marked FAILED (TOOL_REJECTED)",
            invocation.id, gated_tool,
        )

        return {
            "invocation_id": str(invocation.id),
            "status": "failed",
            "error_code": "TOOL_REJECTED",
            "gated_tool": gated_tool,
        }

    def _handle_cancel(
        self,
        invocation: AgentInvocation,
        ctx: dict[str, Any],
        comment: str | None,
    ) -> dict[str, Any]:
        """Cancel: terminate invocation cleanly from WAITING_HUMAN."""
        gated_tool = ctx.get("gated_tool_name", "unknown")
        reason = comment or "Cancelled by operator during tool approval"

        invocation.mark_cancelled()
        invocation.pending_tool_context = None  # consumed
        invocation.error_detail = {
            "error_code": "TOOL_CANCELLED",
            "error_message": f"Tool '{gated_tool}' cancelled by operator: {reason}",
            "gated_tool": gated_tool,
            "reviewer_comment": comment,
        }
        save_with_event(self._uow, invocation, "agent_invocation.cancelled")
        runtime_metrics.inc_human_gate("cancel")
        runtime_metrics.inc_invocation("cancelled")

        logger.info(
            "Invocation %s: tool '%s' cancelled by operator — marked CANCELLED",
            invocation.id, gated_tool,
        )

        return {
            "invocation_id": str(invocation.id),
            "status": "cancelled",
            "error_code": "TOOL_CANCELLED",
            "gated_tool": gated_tool,
        }
