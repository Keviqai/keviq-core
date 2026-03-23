"""Shared outbox event envelope builder.

Provides a standard envelope structure for all services that emit events
via the outbox pattern. Each service's writer uses this to build the
payload before inserting into their outbox table.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any


def build_envelope(
    *,
    event_type: str,
    service_name: str,
    payload: dict[str, Any],
    workspace_id: uuid.UUID | str | None = None,
    task_id: uuid.UUID | str | None = None,
    run_id: uuid.UUID | str | None = None,
    step_id: uuid.UUID | str | None = None,
    agent_invocation_id: uuid.UUID | str | None = None,
    sandbox_id: uuid.UUID | str | None = None,
    artifact_id: uuid.UUID | str | None = None,
    correlation_id: uuid.UUID | str | None = None,
    causation_id: uuid.UUID | str | None = None,
    actor_type: str = "service",
    actor_id: str | None = None,
    event_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Build a standard outbox event envelope.

    Returns a dict ready to be JSON-serialized into the outbox payload column.
    """
    eid = event_id or uuid.uuid4()
    now = datetime.now(timezone.utc)
    instance_id = os.getenv("HOSTNAME", f"{service_name}-local")

    return {
        "event_id": str(eid),
        "event_type": event_type,
        "schema_version": "1.0",
        "workspace_id": str(workspace_id) if workspace_id else None,
        "task_id": str(task_id) if task_id else None,
        "run_id": str(run_id) if run_id else None,
        "step_id": str(step_id) if step_id else None,
        "agent_invocation_id": str(agent_invocation_id) if agent_invocation_id else None,
        "sandbox_id": str(sandbox_id) if sandbox_id else None,
        "artifact_id": str(artifact_id) if artifact_id else None,
        "correlation_id": str(correlation_id) if correlation_id else None,
        "causation_id": str(causation_id) if causation_id else None,
        "occurred_at": now.isoformat(),
        "emitted_by": {
            "service": service_name,
            "instance_id": instance_id,
        },
        "actor": {
            "type": actor_type,
            "id": actor_id or service_name,
        },
        "payload": payload,
    }
