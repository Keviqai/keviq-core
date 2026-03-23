"""Orchestrator outbox cleanup endpoint (O2-S4)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import text

from src.application.bootstrap import get_session_factory

router = APIRouter()
logger = logging.getLogger(__name__)

_OUTBOX_RETENTION_DAYS = int(os.getenv('OUTBOX_RETENTION_DAYS', '7'))
_CLEANUP_BATCH_SIZE = int(os.getenv('CLEANUP_BATCH_SIZE', '1000'))


@router.post("/internal/v1/outbox/cleanup")
def cleanup_published_outbox(
    dry_run: bool = False,
    retention_days: int | None = None,
    batch_size: int | None = None,
):
    """Delete published outbox rows older than retention period."""
    days = retention_days or _OUTBOX_RETENTION_DAYS
    batch = min(batch_size or _CLEANUP_BATCH_SIZE, 5000)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    factory = get_session_factory()
    session = factory()
    try:
        count_result = session.execute(
            text("""
                SELECT COUNT(*) FROM orchestrator_core.outbox
                WHERE published_at IS NOT NULL AND created_at < :cutoff
            """),
            {'cutoff': cutoff},
        ).scalar() or 0

        if dry_run or count_result == 0:
            return {
                "dry_run": dry_run,
                "retention_days": days,
                "cutoff": cutoff.isoformat(),
                "candidates": count_result,
                "deleted": 0,
            }

        result = session.execute(
            text("""
                DELETE FROM orchestrator_core.outbox
                WHERE id IN (
                    SELECT id FROM orchestrator_core.outbox
                    WHERE published_at IS NOT NULL AND created_at < :cutoff
                    ORDER BY created_at ASC
                    LIMIT :batch
                )
            """),
            {'cutoff': cutoff, 'batch': batch},
        )
        deleted = result.rowcount
        session.commit()

        logger.info("outbox cleanup: deleted %d published rows older than %s", deleted, cutoff.isoformat())
        return {
            "dry_run": False,
            "retention_days": days,
            "cutoff": cutoff.isoformat(),
            "candidates": count_result,
            "deleted": deleted,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
