"""Tool loop error handlers — budget exhaustion, malformed tools, all-tools-failed.

Extracted from tool_loop.py to keep file sizes under 300 lines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.application.ports import InvocationUnitOfWork
from src.application.shared_execution import save_with_event
from src.application.tool_helpers import build_invocation_summary
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation
from src.domain.execution_contracts import ExecutionFailure, ExecutionStatus

if TYPE_CHECKING:
    from src.application.tool_loop import ToolLoopResult

logger = logging.getLogger(__name__)


def handle_budget_exhausted(
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    elapsed_ms: int,
    budget_ms: int,
    turn: int,
    result: ToolLoopResult,
) -> ExecutionFailure:
    """Mark invocation timed out due to budget exhaustion."""
    logger.warning(
        "Invocation budget exhausted (%dms used of %dms)", elapsed_ms, budget_ms,
    )
    invocation.mark_timed_out(error_detail={
        "error_code": "BUDGET_EXHAUSTED",
        "error_message": (
            f"Invocation wall-clock budget exhausted after {elapsed_ms}ms "
            f"(budget: {budget_ms}ms)"
        ),
        "turns_completed": turn,
        "invocation_summary": build_invocation_summary(
            total_turns=turn,
            total_tools_called=result.total_tools_called,
            total_tool_failures=result.total_tool_failures,
            total_model_latency_ms=result.total_model_latency_ms,
            total_tool_latency_ms=result.total_tool_latency_ms,
            terminal_reason="BUDGET_EXHAUSTED",
        ),
    })
    save_with_event(uow, invocation, "agent_invocation.timed_out")
    runtime_metrics.inc_invocation("timed_out")
    runtime_metrics.inc_budget_exhaustion()
    return ExecutionFailure(
        agent_invocation_id=invocation.id,
        status=ExecutionStatus.FAILED,
        error_code="BUDGET_EXHAUSTED",
        error_message=f"Invocation budget exhausted after {elapsed_ms}ms",
        failed_at=invocation.completed_at,
    )


def handle_malformed_tools(
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    tool_calls: list[dict],
) -> ExecutionFailure:
    """Mark invocation failed due to malformed tool calls."""
    logger.error("All tool_calls malformed — marking invocation failed")
    invocation.mark_failed(error_detail={
        "error_code": "MALFORMED_TOOL_CALLS",
        "error_message": "Model returned tool_calls with no valid entries",
        "raw_tool_calls": tool_calls[:3],
    })
    save_with_event(uow, invocation, "agent_invocation.failed")
    runtime_metrics.inc_invocation("failed")
    return ExecutionFailure(
        agent_invocation_id=invocation.id,
        status=ExecutionStatus.FAILED,
        error_code="MALFORMED_TOOL_CALLS",
        error_message="Model returned tool_calls with no valid entries",
        failed_at=invocation.completed_at,
    )


def handle_all_tools_failed(
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    turn: int,
    turn_tool_count: int,
    result: ToolLoopResult,
) -> ExecutionFailure:
    """Mark invocation failed because all tools in a turn failed."""
    logger.error(
        "All %d tools failed in turn %d — marking invocation failed",
        turn_tool_count, turn,
    )
    invocation.mark_failed(error_detail={
        "error_code": "ALL_TOOLS_FAILED",
        "error_message": f"All {turn_tool_count} tool(s) failed in turn {turn}",
        "turn": turn,
        "invocation_summary": build_invocation_summary(
            total_turns=turn + 1,
            total_tools_called=result.total_tools_called,
            total_tool_failures=result.total_tool_failures,
            total_model_latency_ms=result.total_model_latency_ms,
            total_tool_latency_ms=result.total_tool_latency_ms,
            terminal_reason="ALL_TOOLS_FAILED",
        ),
    })
    save_with_event(uow, invocation, "agent_invocation.failed")
    runtime_metrics.inc_invocation("failed")
    return ExecutionFailure(
        agent_invocation_id=invocation.id,
        status=ExecutionStatus.FAILED,
        error_code="ALL_TOOLS_FAILED",
        error_message=f"All {turn_tool_count} tool(s) failed in turn {turn}",
        failed_at=invocation.completed_at,
    )
