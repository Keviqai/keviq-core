"""Resume handler — approved path.

Handles the case where a gated tool is approved: dispatches the tool(s),
then continues the model loop until stop or budget exhaustion.

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


def handle_approved(
    invocation: AgentInvocation,
    ctx: dict[str, Any],
    comment: str | None,
    *,
    uow: InvocationUnitOfWork,
    gateway: ModelGatewayPort,
    execution_service: ExecutionServicePort | None,
) -> dict[str, Any]:
    """Approved tool -> resume execution from where it paused.

    Restores context from pending_tool_context, dispatches the gated
    tool(s), then continues the model loop until stop or budget exhaustion.
    """
    tool_calls = ctx.get("tool_calls", [])
    messages = ctx.get("messages", [])
    gw_ctx = ctx.get("gw_response", {})
    gated_tool = ctx.get("gated_tool_name", "unknown")

    # Resume: WAITING_HUMAN -> RUNNING
    invocation.resume_from_wait()
    invocation.pending_tool_context = None  # consumed
    save_with_event(uow, invocation, "agent_invocation.resumed")
    runtime_metrics.inc_human_gate("approved")

    logger.info(
        "Invocation %s: tool '%s' approved — resuming execution",
        invocation.id, gated_tool,
    )

    # Start budget clock from NOW (pause time does not count)
    budget_start = time.monotonic()
    budget_ms = INVOCATION_BUDGET_MS

    # Accumulate tokens from pre-pause
    total_prompt_tokens = gw_ctx.get("prompt_tokens", 0)
    total_completion_tokens = gw_ctx.get("completion_tokens", 0)
    all_tool_calls: list[dict] = list(tool_calls)

    # Mark waiting_tool for the dispatch phase
    invocation.mark_waiting_tool()
    save_with_event(uow, invocation, "agent_invocation.waiting_tool")

    # Add the assistant message that triggered tool calls
    messages.append({
        "role": "assistant",
        "content": gw_ctx.get("output_text") or None,
        "tool_calls": tool_calls,
    })

    # Dispatch each tool from the gated turn
    sandbox_id_str = ctx.get("sandbox_id")
    sandbox_id = UUID(sandbox_id_str) if sandbox_id_str else None

    turn_failure_count = 0
    turn_tool_count = len(tool_calls)

    for tc in tool_calls:
        elapsed_ms = int((time.monotonic() - budget_start) * 1000)
        if budget_ms - elapsed_ms <= 0:
            logger.warning("Budget exhausted during resumed tool dispatch")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": "Budget exhausted — tool execution skipped",
            })
            turn_failure_count += 1
            continue

        tool_result = execute_tool(
            tc,
            execution_service=execution_service,
            sandbox_id=sandbox_id,
        )

        tool_status = tool_result.get("status", "failed")
        if tool_status != "completed":
            turn_failure_count += 1

        content = (
            tool_result.get("stdout", "")
            or tool_result.get("error_message", "Tool execution failed")
        )
        if tool_result.get("truncated"):
            content += "\n[output truncated by execution-service]"
        content = truncate_tool_result(content)

        messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": content,
        })

    # If all tools failed
    if turn_failure_count == turn_tool_count:
        invocation.mark_failed(error_detail={
            "error_code": "ALL_TOOLS_FAILED",
            "error_message": f"All {turn_tool_count} tool(s) failed after approval resume",
        })
        save_with_event(uow, invocation, "agent_invocation.failed")
        return {
            "invocation_id": str(invocation.id),
            "status": "failed",
            "error_code": "ALL_TOOLS_FAILED",
        }

    # Resume from tool wait -> continue model loop
    invocation.resume_from_wait()

    return _continue_model_loop(
        invocation=invocation,
        messages=messages,
        all_tool_calls=all_tool_calls,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        budget_start=budget_start,
        budget_ms=budget_ms,
        sandbox_id=sandbox_id,
        uow=uow,
        gateway=gateway,
        execution_service=execution_service,
    )


def _continue_model_loop(
    *,
    invocation: AgentInvocation,
    messages: list[dict],
    all_tool_calls: list[dict],
    total_prompt_tokens: int,
    total_completion_tokens: int,
    budget_start: float,
    budget_ms: int,
    sandbox_id: UUID | None,
    uow: InvocationUnitOfWork,
    gateway: ModelGatewayPort,
    execution_service: ExecutionServicePort | None,
) -> dict[str, Any]:
    """Continue the model loop after tool dispatch on resume path."""
    tools = None  # Tools param from original request not stored
    last_gw_response: dict = {}
    remaining_turns = MAX_TOOL_TURNS - 1

    for turn in range(remaining_turns):
        elapsed_ms = int((time.monotonic() - budget_start) * 1000)
        remaining_ms = budget_ms - elapsed_ms
        if remaining_ms <= 0:
            invocation.mark_timed_out(error_detail={
                "error_code": "BUDGET_EXHAUSTED",
                "error_message": f"Budget exhausted after resume ({elapsed_ms}ms)",
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
                tools=tools,
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
        new_tool_calls = gw_response.get("tool_calls")

        if finish_reason != "tool_calls" or not new_tool_calls or not execution_service:
            break

        valid = validate_tool_calls(new_tool_calls)
        if not valid:
            invocation.mark_failed(error_detail={
                "error_code": "MALFORMED_TOOL_CALLS",
                "error_message": "Model returned malformed tool_calls after resume",
            })
            save_with_event(uow, invocation, "agent_invocation.failed")
            return {
                "invocation_id": str(invocation.id),
                "status": "failed",
                "error_code": "MALFORMED_TOOL_CALLS",
            }

        all_tool_calls.extend(valid)
        invocation.mark_waiting_tool()
        save_with_event(uow, invocation, "agent_invocation.waiting_tool")

        messages.append({
            "role": "assistant",
            "content": gw_response.get("output_text") or None,
            "tool_calls": valid,
        })

        for tc in valid:
            elapsed_ms = int((time.monotonic() - budget_start) * 1000)
            if budget_ms - elapsed_ms <= 0:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": "Budget exhausted",
                })
                continue
            result = execute_tool(
                tc,
                execution_service=execution_service,
                sandbox_id=sandbox_id,
            )
            content = (
                result.get("stdout", "")
                or result.get("error_message", "Tool execution failed")
            )
            content = truncate_tool_result(content)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": content,
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
        "Invocation %s completed after resume (tokens: %d+%d)",
        invocation.id, total_prompt_tokens, total_completion_tokens,
    )

    return {
        "invocation_id": str(invocation.id),
        "status": "completed",
        "output_text": output_text,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
    }
