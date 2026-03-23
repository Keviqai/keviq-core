"""Shared SQL and parameter helpers for AgentInvocation persistence.

Used by both DbAgentInvocationRepository and DbInvocationUnitOfWork
to prevent duplication of the UPSERT statement and param-building logic.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from src.domain.agent_invocation import AgentInvocation

# SCHEMA is a compile-time constant — must never be user-derived.
SCHEMA = "agent_runtime"

UPSERT_INVOCATION = text(f"""
    INSERT INTO {SCHEMA}.agent_invocations (
        id, step_id, run_id, task_id, workspace_id, correlation_id,
        agent_id, model_id, invocation_status,
        prompt_tokens, completion_tokens, total_cost_usd,
        input_messages, output_messages, tool_calls, error_detail,
        pending_tool_context,
        started_at, completed_at
    ) VALUES (
        :id, :step_id, :run_id, :task_id, :workspace_id, :correlation_id,
        :agent_id, :model_id, :invocation_status,
        :prompt_tokens, :completion_tokens, :total_cost_usd,
        :input_messages, :output_messages, :tool_calls, :error_detail,
        :pending_tool_context,
        :started_at, :completed_at
    )
    ON CONFLICT (id) DO UPDATE SET
        invocation_status = EXCLUDED.invocation_status,
        prompt_tokens = EXCLUDED.prompt_tokens,
        completion_tokens = EXCLUDED.completion_tokens,
        total_cost_usd = EXCLUDED.total_cost_usd,
        input_messages = EXCLUDED.input_messages,
        output_messages = EXCLUDED.output_messages,
        tool_calls = EXCLUDED.tool_calls,
        error_detail = EXCLUDED.error_detail,
        pending_tool_context = EXCLUDED.pending_tool_context,
        started_at = EXCLUDED.started_at,
        completed_at = EXCLUDED.completed_at
""")


def _to_json(value: Any) -> str | None:
    """Convert dict/list to JSON string for JSONB column, or None."""
    if value is None:
        return None
    return json.dumps(value)


def invocation_params(inv: AgentInvocation) -> dict[str, Any]:
    """Convert AgentInvocation entity to DB parameter dict."""
    return {
        "id": str(inv.id),
        "step_id": str(inv.step_id),
        "run_id": str(inv.run_id),
        "task_id": str(inv.task_id),
        "workspace_id": str(inv.workspace_id),
        "correlation_id": str(inv.correlation_id),
        "agent_id": inv.agent_id,
        "model_id": inv.model_id,
        "invocation_status": inv.invocation_status.value,
        "prompt_tokens": inv.prompt_tokens,
        "completion_tokens": inv.completion_tokens,
        "total_cost_usd": inv.total_cost_usd,
        "input_messages": _to_json(inv.input_messages),
        "output_messages": _to_json(inv.output_messages),
        "tool_calls": _to_json(inv.tool_calls),
        "error_detail": _to_json(inv.error_detail),
        "pending_tool_context": _to_json(inv.pending_tool_context),
        "started_at": inv.started_at,
        "completed_at": inv.completed_at,
    }
