"""Transactional unit of work for AgentInvocation + outbox.

Saves invocation state and writes outbox event in the same DB transaction.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from src.application.ports import InvocationUnitOfWork
from src.domain.agent_invocation import AgentInvocation
from src.infrastructure.db._invocation_sql import UPSERT_INVOCATION, invocation_params
from src.infrastructure.outbox.outbox_writer import OutboxWriter


class DbInvocationUnitOfWork(InvocationUnitOfWork):
    """Save invocation + outbox event atomically via DB transaction."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def save_with_event(
        self,
        invocation: AgentInvocation,
        event_type: str,
        event_payload: dict,
    ) -> None:
        with self._engine.connect() as conn:
            conn.execute(UPSERT_INVOCATION, invocation_params(invocation))
            OutboxWriter.write_event(
                conn,
                event_type=event_type,
                payload=event_payload,
                correlation_id=invocation.correlation_id,
            )
            conn.commit()
