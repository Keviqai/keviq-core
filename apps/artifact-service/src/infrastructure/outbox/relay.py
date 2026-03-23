"""Outbox relay — polls artifact-service outbox and forwards events to event-store.

Phase C: HTTP-based relay with connection reuse and retry.
"""

from __future__ import annotations

import logging
import os
import threading

import httpx
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from resilience import RetryPolicy, retry_with_backoff
from src.infrastructure.db.models import OutboxRow
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

EVENT_STORE_URL = os.getenv("EVENT_STORE_URL", "http://event-store:8000")
RELAY_BATCH_SIZE = int(os.getenv("RELAY_BATCH_SIZE", "50"))
RELAY_TIMEOUT = float(os.getenv("RELAY_TIMEOUT", "5.0"))
MAX_RELAY_ATTEMPTS = int(os.getenv("MAX_RELAY_ATTEMPTS", "10"))

_RELAY_RETRY = RetryPolicy(max_attempts=2, base_delay_s=0.5, max_delay_s=3.0)

# Module-level shared client — initialised lazily.
_relay_client: httpx.Client | None = None
_relay_lock = threading.Lock()


def get_relay_client() -> httpx.Client:
    """Return a shared httpx client for outbox relay (thread-safe)."""
    global _relay_client  # noqa: PLW0603
    if _relay_client is not None:
        return _relay_client
    with _relay_lock:
        if _relay_client is None:
            _relay_client = httpx.Client(
                base_url=EVENT_STORE_URL,
                timeout=RELAY_TIMEOUT,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return _relay_client


def close_relay_client() -> None:
    """Close the shared relay client (called on shutdown)."""
    global _relay_client  # noqa: PLW0603
    with _relay_lock:
        if _relay_client is not None:
            _relay_client.close()
            _relay_client = None


def relay_pending_events(session: Session) -> int:
    """Poll outbox for unpublished events and forward to event-store.

    Uses batch ingest endpoint for efficiency.
    Skips events that have exceeded MAX_RELAY_ATTEMPTS to avoid poison pills.
    Returns the number of events successfully relayed.
    """
    rows = (
        session.query(OutboxRow)
        .filter(
            OutboxRow.published_at.is_(None),
            OutboxRow.attempts < MAX_RELAY_ATTEMPTS,
        )
        .order_by(OutboxRow.created_at)
        .limit(RELAY_BATCH_SIZE)
        .all()
    )

    if not rows:
        return 0

    payloads = [row.payload for row in rows]
    row_map = {i: row for i, row in enumerate(rows)}

    client = get_relay_client()

    def _send_batch() -> httpx.Response:
        try:
            return client.post(
                "/internal/v1/events/ingest/batch",
                json={"events": payloads},
                headers=get_auth_client().auth_headers("event-store"),
            )
        except httpx.HTTPError as e:
            raise _RelayTransientError(str(e)) from e

    try:
        resp = retry_with_backoff(
            _send_batch,
            _RELAY_RETRY,
            is_retryable=lambda exc: isinstance(exc, _RelayTransientError),
            operation_name="outbox_relay_batch",
        )
    except _RelayTransientError as e:
        logger.error("Batch relay failed after retries: %s", e)
        _increment_attempts(session, rows)
        return 0

    if resp.status_code not in (200, 201):
        logger.warning("Batch ingest rejected: %s %s", resp.status_code, resp.text)
        _increment_attempts(session, rows)
        return 0

    results = resp.json().get("results", [])
    relayed = 0
    failed_ids = []

    for i, result in enumerate(results):
        row = row_map.get(i)
        if not row:
            continue
        if result.get("status") in ("created", "duplicate"):
            session.execute(
                update(OutboxRow)
                .where(OutboxRow.id == row.id)
                .values(published_at=text("NOW()"))
            )
            relayed += 1
        else:
            failed_ids.append(row.id)
            session.execute(
                update(OutboxRow)
                .where(OutboxRow.id == row.id)
                .values(attempts=OutboxRow.attempts + 1)
            )

    session.commit()

    if failed_ids:
        logger.warning("Failed to relay %d events: %s", len(failed_ids), failed_ids)
    if relayed:
        logger.info("Relayed %d/%d events to event-store", relayed, len(rows))
    return relayed


def _increment_attempts(session: Session, rows: list) -> None:
    """Increment attempt counter for all rows and commit."""
    for row in rows:
        session.execute(
            update(OutboxRow)
            .where(OutboxRow.id == row.id)
            .values(attempts=OutboxRow.attempts + 1)
        )
    session.commit()


class _RelayTransientError(Exception):
    """Internal marker for transient relay errors."""
