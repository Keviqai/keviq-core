"""Usage record writer — persists model call records to DB."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.domain.ports import UsageRecordWriter

# SCHEMA is a compile-time constant — must never be user-derived (SQL injection risk).
SCHEMA = "model_gateway_core"

_INSERT_USAGE = text(f"""
    INSERT INTO {SCHEMA}.model_usage_records (
        agent_invocation_id, workspace_id, correlation_id,
        model_alias, model_concrete, provider,
        prompt_tokens, completion_tokens, total_cost_usd,
        latency_ms, status, error_code
    ) VALUES (
        :agent_invocation_id, :workspace_id, :correlation_id,
        :model_alias, :model_concrete, :provider,
        :prompt_tokens, :completion_tokens, :total_cost_usd,
        :latency_ms, :status, :error_code
    )
""")


class DbUsageRecordWriter(UsageRecordWriter):
    """Write usage records to model_gateway_core.model_usage_records."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def write(
        self,
        *,
        agent_invocation_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
        model_alias: str,
        model_concrete: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: Decimal,
        latency_ms: int | None,
        status: str,
        error_code: str | None = None,
    ) -> None:
        with self._engine.connect() as conn:
            conn.execute(_INSERT_USAGE, {
                "agent_invocation_id": str(agent_invocation_id),
                "workspace_id": str(workspace_id),
                "correlation_id": str(correlation_id),
                "model_alias": model_alias,
                "model_concrete": model_concrete,
                "provider": provider,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_cost_usd": total_cost_usd,
                "latency_ms": latency_ms,
                "status": status,
                "error_code": error_code,
            })
            conn.commit()
