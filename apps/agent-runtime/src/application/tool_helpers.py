"""Tool execution helpers — guardrails, validation, truncation.

Extracted from execution_handler.py to keep it under 300 lines.
These are pure functions with no handler state dependency.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.domain.agent_invocation import AgentInvocation

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS = int(os.getenv('MAX_TOOL_TURNS', '5'))
INVOCATION_BUDGET_MS = int(os.getenv('INVOCATION_BUDGET_MS', '120000'))
MAX_TOOL_RESULT_BYTES = 32_768
MAX_TOOL_INPUT_BYTES = 65_536


def check_tool_guardrails(tool_name: str, tool_input: dict) -> str | None:
    """Check tool input against baseline guardrails. Returns rejection reason or None."""
    input_str = json.dumps(tool_input)
    if len(input_str.encode('utf-8')) > MAX_TOOL_INPUT_BYTES:
        return f"Tool input too large ({len(input_str)} chars, max {MAX_TOOL_INPUT_BYTES} bytes)"

    if tool_name == 'shell.exec':
        code = str(tool_input.get('code', '') or tool_input.get('command', '') or '')
        if not code.strip():
            return "shell.exec: empty command"

        _WARN_PATTERNS = ['curl ', 'wget ', 'nc ', 'chmod +x', 'rm -rf /', 'base64 -d']
        for pattern in _WARN_PATTERNS:
            if pattern in code.lower():
                logger.warning("shell.exec contains potentially risky pattern '%s'", pattern)
                break

    if tool_name == 'python.run_script':
        code = str(tool_input.get('code', ''))
        if not code.strip():
            return "python.run_script: empty code"

    return None


def truncate_tool_result(content: str) -> str:
    """Truncate tool result content to MAX_TOOL_RESULT_BYTES."""
    encoded = content.encode('utf-8')
    if len(encoded) <= MAX_TOOL_RESULT_BYTES:
        return content
    truncated = encoded[:MAX_TOOL_RESULT_BYTES].decode('utf-8', errors='ignore')
    return truncated + "\n[output truncated to 32KB]"


def validate_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Validate tool_call entries. Returns only valid ones, logs warnings for invalid."""
    valid = []
    for i, tc in enumerate(tool_calls):
        if not isinstance(tc, dict):
            logger.warning("tool_call[%d] is not a dict — skipping", i)
            continue
        tc_id = tc.get("id")
        func = tc.get("function")
        if not tc_id:
            logger.warning("tool_call[%d] missing 'id' — skipping", i)
            continue
        if not isinstance(func, dict) or not func.get("name"):
            logger.warning("tool_call[%d] missing function.name — skipping (id=%s)", i, tc_id)
            continue
        valid.append(tc)
    return valid


def build_event_payload(inv: AgentInvocation) -> dict[str, Any]:
    """Build outbox event payload."""
    payload: dict[str, Any] = {
        "agent_invocation_id": str(inv.id),
        "step_id": str(inv.step_id),
        "run_id": str(inv.run_id),
        "task_id": str(inv.task_id),
        "workspace_id": str(inv.workspace_id),
        "agent_id": inv.agent_id,
        "invocation_status": inv.invocation_status.value,
    }

    if inv.started_at:
        payload["started_at"] = inv.started_at.isoformat()
    if inv.completed_at:
        payload["completed_at"] = inv.completed_at.isoformat()
    if inv.error_detail:
        payload["error_detail"] = inv.error_detail
    if inv.prompt_tokens is not None:
        payload["prompt_tokens"] = inv.prompt_tokens
    if inv.completion_tokens is not None:
        payload["completion_tokens"] = inv.completion_tokens
    if inv.tool_calls:
        payload["tool_calls"] = inv.tool_calls

    return payload


def build_turn_event_payload(
    inv: AgentInvocation,
    *,
    turn_index: int,
    tool_count: int,
    failure_count: int,
    model_latency_ms: int,
    turn_duration_ms: int,
    budget_remaining_ms: int,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build payload for agent_invocation.turn_completed event."""
    payload: dict[str, Any] = {
        "agent_invocation_id": str(inv.id),
        "run_id": str(inv.run_id),
        "task_id": str(inv.task_id),
        "workspace_id": str(inv.workspace_id),
        "turn_index": turn_index,
        "tool_count": tool_count,
        "failure_count": failure_count,
        "model_latency_ms": model_latency_ms,
        "turn_duration_ms": turn_duration_ms,
        "budget_remaining_ms": budget_remaining_ms,
    }
    if tools:
        # Summary per tool: name, status, duration_ms
        payload["tools"] = [
            {k: t[k] for k in ("name", "status", "duration_ms") if k in t}
            for t in tools
        ]
    return payload


def build_invocation_summary(
    *,
    total_turns: int,
    total_tools_called: int,
    total_tool_failures: int,
    total_model_latency_ms: int,
    total_tool_latency_ms: int,
    terminal_reason: str | None = None,
) -> dict[str, Any]:
    """Build summary dict for terminal invocation events (completed/failed/timed_out)."""
    summary: dict[str, Any] = {
        "total_turns": total_turns,
        "total_tools_called": total_tools_called,
        "total_tool_failures": total_tool_failures,
        "total_model_latency_ms": total_model_latency_ms,
        "total_tool_latency_ms": total_tool_latency_ms,
    }
    if terminal_reason:
        summary["terminal_reason"] = terminal_reason
    return summary


# Backward-compat aliases for existing imports
_check_tool_guardrails = check_tool_guardrails
_truncate_tool_result = truncate_tool_result
_validate_tool_calls = validate_tool_calls
_event_payload = build_event_payload
