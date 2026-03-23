"""SQLAlchemy-based AgentInvocation repository.

Maps between domain entity and agent_runtime.agent_invocations table.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.application.ports import AgentInvocationRepository
from src.domain.agent_invocation import AgentInvocation, InvocationStatus
from src.infrastructure.db._invocation_sql import (
    SCHEMA,
    UPSERT_INVOCATION,
    invocation_params,
)

_SELECT_BY_ID = text(f"""
    SELECT id, step_id, run_id, task_id, workspace_id, correlation_id,
           agent_id, model_id, invocation_status,
           prompt_tokens, completion_tokens, total_cost_usd,
           input_messages, output_messages, tool_calls, error_detail,
           pending_tool_context,
           started_at, completed_at, created_at
    FROM {SCHEMA}.agent_invocations
    WHERE id = :id AND workspace_id = :workspace_id
""")

_SELECT_ACTIVE = text(f"""
    SELECT id, step_id, run_id, task_id, workspace_id, correlation_id,
           agent_id, model_id, invocation_status,
           prompt_tokens, completion_tokens, total_cost_usd,
           input_messages, output_messages, tool_calls, error_detail,
           pending_tool_context,
           started_at, completed_at, created_at
    FROM {SCHEMA}.agent_invocations
    WHERE invocation_status IN ('initializing', 'starting', 'running', 'waiting_human', 'waiting_tool')
      AND workspace_id = :workspace_id
    ORDER BY created_at
    LIMIT :limit
""")

_SELECT_BY_STEP = text(f"""
    SELECT id, step_id, run_id, task_id, workspace_id, correlation_id,
           agent_id, model_id, invocation_status,
           prompt_tokens, completion_tokens, total_cost_usd,
           input_messages, output_messages, tool_calls, error_detail,
           pending_tool_context,
           started_at, completed_at, created_at
    FROM {SCHEMA}.agent_invocations
    WHERE step_id = :step_id AND workspace_id = :workspace_id
    ORDER BY created_at
""")

_MAX_LIST_LIMIT = 200


def _row_to_entity(row: Any) -> AgentInvocation:
    """Map a DB row to AgentInvocation domain entity."""
    return AgentInvocation(
        id=row.id,
        step_id=row.step_id,
        run_id=row.run_id,
        task_id=row.task_id,
        workspace_id=row.workspace_id,
        correlation_id=row.correlation_id,
        agent_id=row.agent_id,
        model_id=row.model_id,
        invocation_status=InvocationStatus(row.invocation_status),
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_cost_usd=row.total_cost_usd,
        input_messages=row.input_messages,
        output_messages=row.output_messages,
        tool_calls=row.tool_calls,
        error_detail=row.error_detail,
        pending_tool_context=row.pending_tool_context,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


class DbAgentInvocationRepository(AgentInvocationRepository):
    """Persist AgentInvocation entities to agent_runtime.agent_invocations."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def save(self, invocation: AgentInvocation) -> None:
        with self._engine.connect() as conn:
            conn.execute(UPSERT_INVOCATION, invocation_params(invocation))
            conn.commit()

    def get_by_id(self, invocation_id: UUID, workspace_id: UUID) -> AgentInvocation | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                _SELECT_BY_ID,
                {"id": str(invocation_id), "workspace_id": str(workspace_id)},
            ).first()
            if row is None:
                return None
            return _row_to_entity(row)

    def list_active(self, workspace_id: UUID, limit: int = 50) -> list[AgentInvocation]:
        safe_limit = min(max(1, limit), _MAX_LIST_LIMIT)
        with self._engine.connect() as conn:
            rows = conn.execute(
                _SELECT_ACTIVE,
                {"limit": safe_limit, "workspace_id": str(workspace_id)},
            ).fetchall()
            return [_row_to_entity(r) for r in rows]

    def list_by_step(self, step_id: UUID, workspace_id: UUID) -> list[AgentInvocation]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                _SELECT_BY_STEP,
                {"step_id": str(step_id), "workspace_id": str(workspace_id)},
            ).fetchall()
            return [_row_to_entity(r) for r in rows]
