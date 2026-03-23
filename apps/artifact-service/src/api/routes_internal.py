"""Artifact-service internal routes: outbox relay.

Internal infrastructure endpoints not part of the public API contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.application.bootstrap import get_session_factory
from src.internal_auth import require_service

internal_router = APIRouter()


# ── Internal: Outbox Relay Trigger ────────────────────────────

@internal_router.post("/internal/v1/outbox/relay")
def trigger_outbox_relay(_claims=Depends(require_service("api-gateway", "artifact-service"))):
    """Trigger outbox relay to forward events to event-store.

    Phase B: manual/cron trigger. Phase C: background worker.
    """
    from src.infrastructure.outbox.relay import relay_pending_events

    factory = get_session_factory()
    session = factory()
    try:
        relayed = relay_pending_events(session)
    finally:
        session.close()

    return {"relayed": relayed}
