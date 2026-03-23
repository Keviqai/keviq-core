"""Unit tests for resilience.timeout_budget module."""

from __future__ import annotations

import time

import pytest

from resilience.timeout_budget import TimeoutBudget


class TestTimeoutBudget:
    def test_initial_remaining(self):
        b = TimeoutBudget(10_000)
        assert b.remaining_ms > 9_900  # allow small elapsed time
        assert b.remaining_ms <= 10_000

    def test_remaining_decreases(self):
        b = TimeoutBudget(10_000)
        time.sleep(0.05)
        assert b.remaining_ms < 10_000

    def test_remaining_floors_at_zero(self):
        b = TimeoutBudget(1)
        time.sleep(0.01)
        assert b.remaining_ms == 0

    def test_is_exhausted_below_threshold(self):
        b = TimeoutBudget(1)
        time.sleep(0.01)
        assert b.is_exhausted is True

    def test_is_not_exhausted_with_time(self):
        b = TimeoutBudget(60_000)
        assert b.is_exhausted is False

    def test_remaining_for_downstream_deducts_overhead(self):
        b = TimeoutBudget(10_000)
        downstream = b.remaining_for_downstream(overhead_ms=2_000)
        assert downstream <= 8_000
        assert downstream > 7_900

    def test_remaining_for_downstream_floors_at_zero(self):
        b = TimeoutBudget(1_000)
        time.sleep(0.01)
        assert b.remaining_for_downstream(overhead_ms=999_999) == 0

    def test_remaining_seconds(self):
        b = TimeoutBudget(10_000)
        assert 9.0 < b.remaining_seconds() <= 10.0

    def test_from_remaining_ms(self):
        b = TimeoutBudget.from_remaining_ms(5_000)
        assert b.remaining_ms > 4_900
        assert b.remaining_ms <= 5_000

    def test_invalid_total_ms(self):
        with pytest.raises(ValueError, match="positive"):
            TimeoutBudget(0)

        with pytest.raises(ValueError, match="positive"):
            TimeoutBudget(-100)

    def test_elapsed_ms(self):
        b = TimeoutBudget(10_000)
        time.sleep(0.05)
        assert b.elapsed_ms >= 40  # at least ~50ms, allow some variance
