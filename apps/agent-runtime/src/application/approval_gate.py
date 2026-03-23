"""Approval gate — checks tool calls against the approval policy.

When a tool is gated, the invocation is paused at WAITING_HUMAN and an
approval request is sent to the orchestrator. The handler returns an
ExecutionResult with WAITING_HUMAN status.

Extracted from tool_loop.py to keep file sizes under 300 lines.
"""

from __future__ import annotations

import json
import logging

from src.application.ports import (
    InvocationUnitOfWork,
    ToolApprovalServicePort,
)
from src.application.shared_execution import save_with_event
from src.domain.agent_invocation import AgentInvocation
from src.domain.execution_contracts import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from src.domain.tool_approval_policy import (
    ApprovalDecision as ToolPolicyDecision,
    evaluate_tool_approval,
)

logger = logging.getLogger(__name__)


def check_tool_approval_gate(
    *,
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    request: ExecutionRequest,
    tool_calls: list[dict],
    messages: list[dict],
    gw_response: dict,
    tool_approval_service: ToolApprovalServicePort | None,
) -> ExecutionResult | None:
    """Check if any tool call requires human approval.

    If a gated tool is found:
    1. Transition invocation to WAITING_HUMAN
    2. Persist pending_tool_context for S2 resume
    3. Request approval from orchestrator
    4. Return ExecutionResult with WAITING_HUMAN status

    Returns None if all tools are allowed (normal flow continues).
    """
    for tc in tool_calls:
        func = tc.get("function", {})
        tool_name = func.get("name", "unknown")
        try:
            tool_input = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            tool_input = {}

        policy_result = evaluate_tool_approval(tool_name, tool_input)

        if policy_result.decision == ToolPolicyDecision.WARN:
            logger.warning(
                "Tool '%s' flagged by approval policy (warn): %s",
                tool_name, policy_result.reason,
            )
            continue

        if policy_result.decision == ToolPolicyDecision.GATE:
            logger.info(
                "Tool '%s' gated by approval policy: %s — pausing invocation %s",
                tool_name, policy_result.reason, invocation.id,
            )

            sandbox_id_str = (request.input_payload or {}).get("sandbox_id")
            pending_context = {
                "tool_calls": tool_calls,
                "messages": messages,
                "gw_response": {
                    "output_text": gw_response.get("output_text"),
                    "prompt_tokens": gw_response.get("prompt_tokens", 0),
                    "completion_tokens": gw_response.get("completion_tokens", 0),
                },
                "sandbox_id": sandbox_id_str,
                "gated_tool_name": tool_name,
                "gated_tool_input_preview": json.dumps(tool_input)[:500],
                "gate_reason": policy_result.reason,
            }

            invocation.mark_waiting_human(pending_tool_context=pending_context)
            save_with_event(uow, invocation, "agent_invocation.waiting_human")

            approval_id = _request_tool_approval(
                tool_approval_service=tool_approval_service,
                invocation=invocation,
                request=request,
                tool_name=tool_name,
                tool_input=tool_input,
                risk_reason=policy_result.reason,
            )

            return ExecutionResult(
                agent_invocation_id=invocation.id,
                status=ExecutionStatus.WAITING_HUMAN,
                output_payload={
                    "waiting_reason": "tool_approval_required",
                    "gated_tool": tool_name,
                    "gate_reason": policy_result.reason,
                    "approval_id": approval_id,
                },
                started_at=invocation.started_at,
            )

    # All tools allowed
    return None


def _request_tool_approval(
    *,
    tool_approval_service: ToolApprovalServicePort | None,
    invocation: AgentInvocation,
    request: ExecutionRequest,
    tool_name: str,
    tool_input: dict,
    risk_reason: str,
) -> str | None:
    """Request tool approval from orchestrator. Best-effort."""
    if tool_approval_service is None:
        logger.warning("No tool approval service configured — approval not created")
        return None

    try:
        result = tool_approval_service.request_tool_approval(
            workspace_id=request.workspace_id,
            invocation_id=invocation.id,
            run_id=request.run_id,
            task_id=request.task_id,
            tool_name=tool_name,
            arguments_preview=json.dumps(tool_input)[:2000],
            risk_reason=risk_reason,
        )
        return result.get("id")
    except Exception:
        logger.warning(
            "Failed to create tool approval for invocation %s — "
            "invocation is WAITING_HUMAN but approval record may not exist",
            invocation.id,
            exc_info=True,
        )
        return None
