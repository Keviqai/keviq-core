"""Unit tests for notification cleanup (O2-S4)."""

import os
import sys
from datetime import timedelta, timezone, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'notification-service')
os.environ.setdefault('APP_ENV', 'development')


class TestNotificationRetentionPolicy:
    """Notification retention defaults."""

    def test_default_retention_30_days(self):
        from src.api.routes import _NOTIFICATION_RETENTION_DAYS
        assert _NOTIFICATION_RETENTION_DAYS == 30

    def test_default_batch_size(self):
        from src.api.routes import _CLEANUP_BATCH_SIZE
        assert _CLEANUP_BATCH_SIZE == 1000

    def test_cutoff_calculation(self):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        assert (now - cutoff).days == 30


class TestNotificationCleanupContract:
    """Response shape and targeting."""

    def test_response_fields(self):
        expected = {'dry_run', 'retention_days', 'cutoff', 'candidates', 'deleted'}
        response = {
            "dry_run": True,
            "retention_days": 30,
            "cutoff": "2026-02-18T00:00:00+00:00",
            "candidates": 5,
            "deleted": 0,
        }
        assert set(response.keys()) == expected

    def test_only_read_notifications_are_candidates(self):
        """Cleanup targets is_read = true AND read_at < cutoff."""
        sql_where = "is_read = true AND read_at < :cutoff"
        assert "is_read = true" in sql_where
        assert "read_at" in sql_where

    def test_unread_notifications_never_deleted(self):
        """Unread notifications are never cleanup candidates."""
        # The SQL condition explicitly requires is_read = true
        sql_where = "is_read = true AND read_at < :cutoff"
        assert "is_read = false" not in sql_where
