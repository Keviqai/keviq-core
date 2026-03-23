"""Event ingest service — converts raw event envelopes to stored events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.domain.event import StoredEvent

from .ports import EventRepository

logger = logging.getLogger(__name__)


def ingest_event(envelope: dict[str, Any], repo: EventRepository) -> bool:
    """Ingest a raw event envelope into the store.

    Returns True if event was new, False if duplicate.
    Raises ValueError for invalid envelopes.
    """
    try:
        event = _parse_envelope(envelope)
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"Invalid event envelope: {e}") from e

    is_new = repo.ingest(event)
    if is_new:
        logger.info("Ingested event %s (%s)", event.id, event.event_type)
    else:
        logger.debug("Duplicate event %s skipped", event.id)
    return is_new


def ingest_event_batch(
    envelopes: list[dict[str, Any]], repo: EventRepository,
) -> list[dict[str, Any]]:
    """Ingest multiple event envelopes in a single transaction.

    Returns per-event results with status and event_id.
    """
    # Parse all envelopes, preserving input order in results
    parsed_events: list[StoredEvent | None] = []
    results: list[dict[str, Any]] = [None] * len(envelopes)  # type: ignore[list-item]

    valid_indices: list[int] = []
    for i, envelope in enumerate(envelopes):
        event_id = envelope.get("event_id", "unknown")
        try:
            event = _parse_envelope(envelope)
            parsed_events.append(event)
            valid_indices.append(i)
        except (KeyError, ValueError, TypeError) as e:
            parsed_events.append(None)
            results[i] = {"event_id": event_id, "status": "error", "detail": str(e)}

    if valid_indices:
        valid_events = [parsed_events[i] for i in valid_indices]
        is_new_flags = repo.ingest_batch(valid_events)  # type: ignore[arg-type]
        for idx, is_new in zip(valid_indices, is_new_flags):
            ev = parsed_events[idx]
            results[idx] = {
                "event_id": str(ev.id),  # type: ignore[union-attr]
                "status": "created" if is_new else "duplicate",
            }

    return results


def _parse_envelope(envelope: dict[str, Any]) -> StoredEvent:
    """Parse a raw event envelope dict into a StoredEvent domain object."""
    occurred_at = envelope["occurred_at"]
    if isinstance(occurred_at, str):
        occurred_at = datetime.fromisoformat(occurred_at)

    return StoredEvent(
        id=UUID(envelope["event_id"]),
        event_type=envelope["event_type"],
        schema_version=envelope.get("schema_version", "1.0"),
        workspace_id=UUID(envelope["workspace_id"]),
        task_id=UUID(envelope["task_id"]) if envelope.get("task_id") else None,
        run_id=UUID(envelope["run_id"]) if envelope.get("run_id") else None,
        step_id=UUID(envelope["step_id"]) if envelope.get("step_id") else None,
        correlation_id=UUID(envelope["correlation_id"]),
        causation_id=UUID(envelope["causation_id"]) if envelope.get("causation_id") else None,
        occurred_at=occurred_at,
        emitted_by=envelope.get("emitted_by", {"service": "unknown", "instance_id": "unknown"}),
        actor=envelope.get("actor", {"type": "system", "id": "unknown"}),
        payload=envelope.get("payload", {}),
        received_at=datetime.now(timezone.utc),
    )
