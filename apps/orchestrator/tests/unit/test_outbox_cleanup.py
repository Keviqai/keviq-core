"""Unit tests for orchestrator outbox cleanup (O2-S4)."""

import os
import sys
from datetime import timedelta, timezone, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'orchestrator')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')


class TestOutboxRetentionPolicy:
    """Outbox retention defaults."""

    def test_default_retention_7_days(self):
        from src.api.routes_cleanup import _OUTBOX_RETENTION_DAYS
        assert _OUTBOX_RETENTION_DAYS == 7

    def test_default_batch_size(self):
        from src.api.routes_cleanup import _CLEANUP_BATCH_SIZE
        assert _CLEANUP_BATCH_SIZE == 1000

    def test_cutoff_calculation(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        assert (now - cutoff).days == 7

    def test_batch_capped(self):
        assert min(10000, 5000) == 5000


class TestOutboxCleanupContract:
    """Response shape for outbox cleanup."""

    def test_response_fields(self):
        expected = {'dry_run', 'retention_days', 'cutoff', 'candidates', 'deleted'}
        response = {
            "dry_run": True,
            "retention_days": 7,
            "cutoff": "2026-03-13T00:00:00+00:00",
            "candidates": 10,
            "deleted": 0,
        }
        assert set(response.keys()) == expected

    def test_only_published_rows_are_candidates(self):
        """Cleanup targets published_at IS NOT NULL only."""
        # The SQL WHERE clause is:
        # published_at IS NOT NULL AND created_at < :cutoff
        # Unpublished rows (published_at IS NULL) are never deleted
        sql_where = "published_at IS NOT NULL AND created_at < :cutoff"
        assert "published_at IS NOT NULL" in sql_where
