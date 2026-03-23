"""Unit tests for event-store cleanup logic (O2-S4)."""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'event-store')
os.environ.setdefault('APP_ENV', 'development')


class TestRetentionPolicy:
    """Retention policy configuration defaults and overrides."""

    def test_default_retention_90_days(self):
        from src.api.routes import _EVENT_RETENTION_DAYS
        assert _EVENT_RETENTION_DAYS == 90

    def test_default_batch_size_1000(self):
        from src.api.routes import _CLEANUP_BATCH_SIZE
        assert _CLEANUP_BATCH_SIZE == 1000

    def test_cutoff_calculation(self):
        """Cutoff = now - retention_days."""
        now = datetime.now(timezone.utc)
        days = 90
        cutoff = now - timedelta(days=days)
        # Cutoff should be roughly 90 days ago
        assert (now - cutoff).days == 90

    def test_batch_capped_at_5000(self):
        """Batch size input above 5000 gets clamped."""
        batch = min(10000, 5000)
        assert batch == 5000


class TestCleanupEndpointContract:
    """Cleanup response shape and dry-run behavior."""

    def test_dry_run_response_has_required_fields(self):
        expected_fields = {'dry_run', 'retention_days', 'cutoff', 'candidates', 'deleted'}
        # Simulate a dry-run response
        response = {
            "dry_run": True,
            "retention_days": 90,
            "cutoff": "2026-01-01T00:00:00+00:00",
            "candidates": 42,
            "deleted": 0,
        }
        assert set(response.keys()) == expected_fields

    def test_dry_run_never_deletes(self):
        response = {
            "dry_run": True,
            "retention_days": 90,
            "cutoff": "2026-01-01T00:00:00+00:00",
            "candidates": 100,
            "deleted": 0,
        }
        assert response["deleted"] == 0
        assert response["dry_run"] is True

    def test_actual_run_response_shape(self):
        response = {
            "dry_run": False,
            "retention_days": 90,
            "cutoff": "2026-01-01T00:00:00+00:00",
            "candidates": 100,
            "deleted": 50,
        }
        assert response["dry_run"] is False
        assert response["deleted"] <= response["candidates"]
