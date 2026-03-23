"""Tool loop — the core model-call -> tool-dispatch -> repeat cycle.

Extracted from execution_handler.py to keep file sizes under 300 lines.
Contains the main loop that calls model gateway, validates tool calls,
dispatches tools, and handles the approval gate.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from uuid import UUID

from src.application.approval_gate import check_tool_approval_gate
from src.application.loop_errors import (
    handle_all_tools_failed,
    handle_budget_exhausted,
    handle_malformed_tools,
)
from src.application.ports import (
    ExecutionServicePort,
    InvocationUnitOfWork,
    ModelGatewayPort,
    ToolApprovalServicePort,
)
from src.application.shared_execution import execute_tool, save_with_event
from src.application.tool_helpers import (
    INVOCATION_BUDGET_MS,
    MAX_TOOL_TURNS,
    build_turn_event_payload,
    truncate_tool_result as _truncate_tool_result,
    validate_tool_calls as _validate_tool_calls,
)
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation
from src.domain.execution_contracts import (
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolLoopResult:
    """Outcome of the tool loop."""

    output_text: str = ""
    last_gw_response: dict = field(default_factory=dict)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    all_tool_calls: list[dict] = field(default_factory=list)
    completed_turns: int = 0
    total_tools_called: int = 0
    total_tool_failures: int = 0
    total_model_latency_ms: int = 0
    total_tool_latency_ms: int = 0
    # Non-None means the loop exited early with a terminal result
    early_exit: ExecutionResult | ExecutionFailure | None = None


def run_tool_loop(
    *,
    invocation: AgentInvocation,
    request: ExecutionRequest,
    uow: InvocationUnitOfWork,
    gateway: ModelGatewayPort,
    execution_service: ExecutionServicePort | None,
    tool_approval_service: ToolApprovalServicePort | None,
) -> ToolLoopResult:
    """Run the model-call -> tool-dispatch loop.

    Returns ToolLoopResult. If early_exit is set, the caller should return it.
    """
    budget_start = time.monotonic()
    budget_ms = request.timeout_ms if request.timeout_ms > 0 else INVOCATION_BUDGET_MS
    messages = list(invocation.input_messages or [])
    tools = request.input_payload.get("tools") if request.input_payload else None

    result = ToolLoopResult()

    for turn in range(MAX_TOOL_TURNS):
        turn_start = time.monotonic()
        elapsed_ms = int((time.monotonic() - budget_start) * 1000)
        remaining_ms = budget_ms - elapsed_ms
        if remaining_ms <= 0:
            result.early_exit = handle_budget_exhausted(
                uow, invocation, elapsed_ms, budget_ms, turn, result,
            )
            return result

        # Call model gateway
        model_timeout_ms = min(remaining_ms, 60_000)
        model_call_start = time.monotonic()
        try:
            gw_response = gateway.invoke_model(
                agent_invocation_id=request.agent_invocation_id,
                model_alias=request.model_profile.model_alias,
                messages=messages,
                workspace_id=request.workspace_id,
                correlation_id=request.correlation_id,
                max_tokens=request.model_profile.max_tokens,
                temperature=request.model_profile.temperature,
                tools=tools,
                timeout_ms=model_timeout_ms,
            )
        except Exception as exc:
            from src.application.gateway_errors import handle_gateway_error
            result.early_exit = handle_gateway_error(uow, invocation, exc)
            return result

        model_latency_ms = int((time.monotonic() - model_call_start) * 1000)
        result.last_gw_response = gw_response
        result.last_gw_response["model_latency_ms"] = model_latency_ms
        result.total_model_latency_ms += model_latency_ms
        result.total_prompt_tokens += gw_response.get("prompt_tokens", 0)
        result.total_completion_tokens += gw_response.get("completion_tokens", 0)

        finish_reason = gw_response.get("finish_reason", "stop")
        tool_calls = gw_response.get("tool_calls")

        if finish_reason != "tool_calls" or not tool_calls or not execution_service:
            break

        valid_tool_calls = _validate_tool_calls(tool_calls)
        if not valid_tool_calls:
            result.early_exit = handle_malformed_tools(uow, invocation, tool_calls)
            return result

        result.all_tool_calls.extend(valid_tool_calls)

        # Approval gate check (O5-S1)
        gate_result = check_tool_approval_gate(
            uow=uow, invocation=invocation, request=request,
            tool_calls=valid_tool_calls, messages=messages,
            gw_response=gw_response, tool_approval_service=tool_approval_service,
        )
        if gate_result is not None:
            runtime_metrics.inc_human_gate("gate_entered")
            result.early_exit = gate_result
            return result

        invocation.mark_waiting_tool()
        save_with_event(uow, invocation, "agent_invocation.waiting_tool")
        messages.append({
            "role": "assistant",
            "content": gw_response.get("output_text") or None,
            "tool_calls": valid_tool_calls,
        })

        # Execute each tool
        turn_res = _dispatch_tools(
            valid_tool_calls, request, budget_start, budget_ms,
            execution_service, turn, result, messages,
        )

        if turn_res.all_failed:
            result.early_exit = handle_all_tools_failed(
                uow, invocation, turn, turn_res.count, result,
            )
            return result

        invocation.resume_from_wait()
        result.completed_turns = turn + 1
        turn_duration_ms = int((time.monotonic() - turn_start) * 1000)
        budget_remaining = max(
            0, budget_ms - int((time.monotonic() - budget_start) * 1000),
        )

        uow.save_with_event(
            invocation=invocation,
            event_type="agent_invocation.turn_completed",
            event_payload=build_turn_event_payload(
                invocation, turn_index=turn, tool_count=turn_res.count,
                failure_count=turn_res.failures, model_latency_ms=model_latency_ms,
                turn_duration_ms=turn_duration_ms, budget_remaining_ms=budget_remaining,
                tools=turn_res.details,
            ),
        )
        logger.info(
            "Tool turn %d completed (%d/%d succeeded), resuming model call",
            turn + 1, turn_res.count - turn_res.failures, turn_res.count,
        )

    result.output_text = result.last_gw_response.get("output_text", "")
    return result


# ── Tool dispatch helper ─────────────────────────────────────────


@dataclass
class _TurnResult:
    count: int = 0
    failures: int = 0
    details: list[dict] = field(default_factory=list)

    @property
    def all_failed(self) -> bool:
        return self.failures == self.count and self.count > 0


def _dispatch_tools(
    tool_calls: list[dict],
    request: ExecutionRequest,
    budget_start: float,
    budget_ms: int,
    execution_service: ExecutionServicePort | None,
    turn: int,
    result: ToolLoopResult,
    messages: list[dict],
) -> _TurnResult:
    """Dispatch tool calls for one turn. Updates result and messages in-place."""
    sandbox_id_str = (request.input_payload or {}).get("sandbox_id")
    sandbox_id = UUID(sandbox_id_str) if sandbox_id_str else None
    turn_result = _TurnResult(count=len(tool_calls))

    for tc in tool_calls:
        elapsed_ms = int((time.monotonic() - budget_start) * 1000)
        if budget_ms - elapsed_ms <= 0:
            messages.append({
                "role": "tool", "tool_call_id": tc.get("id", ""),
                "content": "Budget exhausted — tool execution skipped",
            })
            turn_result.failures += 1
            turn_result.details.append({
                "name": tc.get("function", {}).get("name", "unknown"),
                "status": "skipped", "duration_ms": 0,
            })
            continue

        tool_call_start = time.monotonic()
        tool_result = execute_tool(
            tc, execution_service=execution_service,
            sandbox_id=sandbox_id, attempt_index=turn,
        )
        tool_duration_ms = int((time.monotonic() - tool_call_start) * 1000)
        tool_result["tool_duration_ms"] = tool_duration_ms
        result.total_tool_latency_ms += tool_duration_ms

        tool_status = tool_result.get("status", "failed")
        runtime_metrics.inc_tool_call(tool_status)
        if tool_status != "completed":
            turn_result.failures += 1
            runtime_metrics.inc_tool_failure(tool_result.get("error_code", "UNKNOWN"))

        turn_result.details.append({
            "name": tc.get("function", {}).get("name", "unknown"),
            "status": tool_status, "duration_ms": tool_duration_ms,
        })

        content = (
            tool_result.get("stdout", "")
            or tool_result.get("error_message", "Tool execution failed")
        )
        if tool_result.get("truncated"):
            content += "\n[output truncated by execution-service]"
        content = _truncate_tool_result(content)
        messages.append({
            "role": "tool", "tool_call_id": tc.get("id", ""), "content": content,
        })

    result.total_tools_called += turn_result.count
    result.total_tool_failures += turn_result.failures
    return turn_result
