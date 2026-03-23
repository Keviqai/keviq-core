"""Resume handler — override path.

Handles the case where an operator provides a synthetic tool result
to replace the gated tool execution. The override output is injected
as if the tool had produced it, then the model loop continues.

Extracted from resume_handler.py to keep file sizes under 300 lines.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from src.application.ports import (
    ExecutionServicePort,
    InvocationUnitOfWork,
    ModelGatewayPort,
)
from src.application.shared_execution import execute_tool, save_with_event
from src.application.tool_helpers import (
    INVOCATION_BUDGET_MS,
    MAX_TOOL_TURNS,
    truncate_tool_result,
    validate_tool_calls,
)
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation

logger = logging.getLogger(__name__)


def handle_override(
    invocation: AgentInvocation,
    ctx: dict[str, Any],
    comment: str | None,
    override_output: str,
    *,
    uow: InvocationUnitOfWork,
    gateway: ModelGatewayPort,
    execution_service: ExecutionServicePort | None,
) -> dict[str, Any]:
    """Override: inject synthetic tool result, then continue model loop.

    The override_output is treated as a valid tool result — the model
    receives it exactly as if the tool had produced it.
    """
    tool_calls = ctx.get("tool_calls", [])
    messages = ctx.get("messages", [])
    gw_ctx = ctx.get("gw_response", {})
    gated_tool = ctx.get("gated_tool_name", "unknown")

    # Resume: WAITING_HUMAN -> RUNNING
    invocation.resume_from_wait()
    invocation.pending_tool_context = None  # consumed
    save_with_event(uow, invocation, "agent_invocation.overridden")
    runtime_metrics.inc_human_gate("override")

    logger.info(
        "Invocation %s: tool '%s' overridden by operator — injecting synthetic result (%d chars)",
        invocation.id, gated_tool, len(override_output),
    )

    # Build messages as if tool executed: assistant message + synthetic tool results
    messages.append({
        "role": "assistant",
        "content": gw_ctx.get("output_text") or None,
        "tool_calls": tool_calls,
    })

    # Inject override as tool result for each tool call in the gated turn
    for tc in tool_calls:
        messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": truncate_tool_result(override_output),
        })

    # Continue model loop with override result
    budget_start = time.monotonic()
    budget_ms = INVOCATION_BUDGET_MS
    total_prompt_tokens = gw_ctx.get("prompt_tokens", 0)
    total_completion_tokens = gw_ctx.get("completion_tokens", 0)
    all_tool_calls: list[dict] = list(tool_calls)
    last_gw_response: dict = {}

    sandbox_id_str = ctx.get("sandbox_id")
    sandbox_id = UUID(sandbox_id_str) if sandbox_id_str else None

    remaining_turns = MAX_TOOL_TURNS - 1
    for turn in range(remaining_turns):
        elapsed_ms = int((time.monotonic() - budget_start) * 1000)
        remaining_ms = budget_ms - elapsed_ms
        if remaining_ms <= 0:
            invocation.mark_timed_out(error_detail={
                "error_code": "BUDGET_EXHAUSTED",
                "error_message": f"Budget exhausted after override resume ({elapsed_ms}ms)",
            })
            save_with_event(uow, invocation, "agent_invocation.timed_out")
            return {
                "invocation_id": str(invocation.id),
                "status": "timed_out",
                "error_code": "BUDGET_EXHAUSTED",
            }

        model_timeout_ms = min(remaining_ms, 60_000)
        try:
            gw_response = gateway.invoke_model(
                agent_invocation_id=invocation.id,
                model_alias=invocation.model_id,
                messages=messages,
                workspace_id=invocation.workspace_id,
                correlation_id=invocation.correlation_id,
                tools=None,
                timeout_ms=model_timeout_ms,
            )
        except Exception as exc:
            invocation.mark_failed(error_detail={
                "error_code": "GATEWAY_ERROR",
                "error_message": str(exc),
            })
            save_with_event(uow, invocation, "agent_invocation.failed")
            return {
                "invocation_id": str(invocation.id),
                "status": "failed",
                "error_code": "GATEWAY_ERROR",
            }

        last_gw_response = gw_response
        total_prompt_tokens += gw_response.get("prompt_tokens", 0)
        total_completion_tokens += gw_response.get("completion_tokens", 0)

        finish_reason = gw_response.get("finish_reason", "stop")
        if finish_reason != "tool_calls" or not gw_response.get("tool_calls"):
            break

        # Further tool calls after override — dispatch normally (no gate on resume)
        valid = validate_tool_calls(gw_response.get("tool_calls", []))
        if not valid:
            break
        all_tool_calls.extend(valid)
        invocation.mark_waiting_tool()
        save_with_event(uow, invocation, "agent_invocation.waiting_tool")
        messages.append({
            "role": "assistant",
            "content": gw_response.get("output_text") or None,
            "tool_calls": valid,
        })
        for tc in valid:
            result = execute_tool(
                tc,
                execution_service=execution_service,
                sandbox_id=sandbox_id,
            )
            content = (
                result.get("stdout", "")
                or result.get("error_message", "Tool execution failed")
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": truncate_tool_result(content),
            })
        invocation.resume_from_wait()

    # Complete
    output_text = last_gw_response.get("output_text", "")
    invocation.mark_completed(
        output_messages=[{"role": "assistant", "content": output_text}],
        tool_calls=all_tool_calls or None,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
    )
    save_with_event(uow, invocation, "agent_invocation.completed")
    runtime_metrics.inc_invocation("completed")

    logger.info(
        "Invocation %s completed after override (tokens: %d+%d)",
        invocation.id, total_prompt_tokens, total_completion_tokens,
    )

    return {
        "invocation_id": str(invocation.id),
        "status": "completed",
        "output_text": output_text,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "resolution": "overridden",
    }
