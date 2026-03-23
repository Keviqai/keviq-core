"""Outbox writer for agent-runtime events.

Writes events to agent_runtime.outbox in the same transaction as state mutations.
Events are picked up by a separate publisher (out of scope for PR16).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

SCHEMA = "agent_runtime"

_INSERT_OUTBOX = text(f"""
    INSERT INTO {SCHEMA}.outbox (event_type, payload, correlation_id)
    VALUES (:event_type, :payload, :correlation_id)
""")


class OutboxWriter:
    """Write outbox events within an existing DB connection/transaction."""

    @staticmethod
    def write_event(
        conn: Connection,
        *,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: UUID,
    ) -> None:
        """Insert an outbox event using the given connection (same transaction)."""
        conn.execute(_INSERT_OUTBOX, {
            "event_type": event_type,
            "payload": json.dumps(payload, default=str),
            "correlation_id": str(correlation_id),
        })
