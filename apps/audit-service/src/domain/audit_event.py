"""Audit event domain entity."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import UUID, uuid4


VALID_ACTOR_TYPES = frozenset({'user', 'system', 'agent'})


@dataclasses.dataclass(frozen=True)
class AuditEvent:
    """Immutable record of an actor performing an action on a target."""

    event_id: UUID
    actor_id: str
    actor_type: str          # 'user' | 'system' | 'agent'
    action: str              # e.g. 'approval.requested', 'task.created'
    workspace_id: UUID
    target_id: str | None
    target_type: str | None
    metadata: dict
    occurred_at: datetime

    @classmethod
    def create(
        cls,
        *,
        actor_id: str,
        action: str,
        workspace_id: UUID,
        actor_type: str = 'user',
        target_id: str | None = None,
        target_type: str | None = None,
        metadata: dict | None = None,
        occurred_at: datetime | None = None,
    ) -> 'AuditEvent':
        if not actor_id:
            raise ValueError("actor_id is required")
        if not action:
            raise ValueError("action is required")
        if actor_type not in VALID_ACTOR_TYPES:
            raise ValueError(f"actor_type must be one of {VALID_ACTOR_TYPES}")

        return cls(
            event_id=uuid4(),
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            workspace_id=workspace_id,
            target_id=target_id,
            target_type=target_type,
            metadata=metadata or {},
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )
