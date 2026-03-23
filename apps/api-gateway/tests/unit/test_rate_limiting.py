"""Unit tests for rate limiting core — counter, config, IP extraction.

Tests cover:
- SlidingWindowCounter correctness (allow, block, expiry, prune)
- RateLimitConfig loading from env vars
- Client IP extraction from ASGI scope
"""

from __future__ import annotations

import pytest

from src.api.rate_limit import (
    RateLimitConfig,
    RateLimitTier,
    get_client_ip,
    load_rate_limit_config,
)
from src.api.rate_limit_middleware import SlidingWindowCounter


# ── SlidingWindowCounter tests ──────────────────────────────────


class TestSlidingWindowCounter:
    """Tests for the sliding window counter algorithm."""

    def test_allows_within_limit(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=3, window_seconds=60)
        now = 1000.0

        allowed1, rem1, _ = counter.is_allowed("k1", tier, now=now)
        allowed2, rem2, _ = counter.is_allowed("k1", tier, now=now + 1)
        allowed3, rem3, _ = counter.is_allowed("k1", tier, now=now + 2)

        assert allowed1 is True
        assert rem1 == 2
        assert allowed2 is True
        assert rem2 == 1
        assert allowed3 is True
        assert rem3 == 0

    def test_blocks_over_limit(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=2, window_seconds=60)
        now = 1000.0

        counter.is_allowed("k1", tier, now=now)
        counter.is_allowed("k1", tier, now=now + 1)
        allowed, remaining, reset = counter.is_allowed("k1", tier, now=now + 2)

        assert allowed is False
        assert remaining == 0
        assert reset >= 1

    def test_window_expires_allows_again(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=1, window_seconds=10)
        now = 1000.0

        counter.is_allowed("k1", tier, now=now)
        blocked, _, _ = counter.is_allowed("k1", tier, now=now + 5)
        assert blocked is False

        # After window expires
        allowed, remaining, _ = counter.is_allowed("k1", tier, now=now + 11)
        assert allowed is True
        assert remaining == 0

    def test_separate_keys_independent(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=1, window_seconds=60)
        now = 1000.0

        a1, _, _ = counter.is_allowed("user:alice", tier, now=now)
        b1, _, _ = counter.is_allowed("user:bob", tier, now=now)

        assert a1 is True
        assert b1 is True

        a2, _, _ = counter.is_allowed("user:alice", tier, now=now + 1)
        assert a2 is False

    def test_reset_after_value(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=1, window_seconds=30)
        now = 1000.0

        counter.is_allowed("k1", tier, now=now)
        _, _, reset = counter.is_allowed("k1", tier, now=now + 10)

        # Oldest entry at 1000.0, window=30, now=1010 -> reset = 1000+30-1010+1 = 21
        assert reset == 21

    def test_prune_stale_removes_old_keys(self) -> None:
        counter = SlidingWindowCounter()
        tier = RateLimitTier(max_requests=10, window_seconds=60)
        now = 1000.0

        counter.is_allowed("old_key", tier, now=now)
        counter.is_allowed("recent_key", tier, now=now + 200)

        counter.prune_stale(max_age=120.0, now=now + 250)
        assert "old_key" not in counter._windows
        assert "recent_key" in counter._windows


# ── RateLimitConfig tests ───────────────────────────────────────


class TestRateLimitConfig:
    """Tests for config loading and parsing."""

    def test_default_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in [
            "RATE_LIMIT_AUTH_LOGIN", "RATE_LIMIT_AUTH_REGISTER",
            "RATE_LIMIT_WRITE", "RATE_LIMIT_READ", "RATE_LIMIT_GLOBAL_IP",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = load_rate_limit_config()

        assert config.auth_login == RateLimitTier(10, 60)
        assert config.auth_register == RateLimitTier(5, 60)
        assert config.write == RateLimitTier(60, 60)
        assert config.read == RateLimitTier(300, 60)
        assert config.global_per_ip == RateLimitTier(600, 60)

    def test_custom_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RATE_LIMIT_WRITE", "30/120")
        monkeypatch.setenv("RATE_LIMIT_READ", "100/120")

        config = load_rate_limit_config()

        assert config.write == RateLimitTier(30, 120)
        assert config.read == RateLimitTier(100, 120)


# ── Client IP tests ─────────────────────────────────────────────


class TestGetClientIp:
    """Tests for IP extraction from ASGI scope."""

    def test_extracts_ip(self) -> None:
        scope = {"client": ("192.168.1.1", 54321)}
        assert get_client_ip(scope) == "192.168.1.1"

    def test_missing_client(self) -> None:
        assert get_client_ip({}) == "127.0.0.1"

    def test_none_client(self) -> None:
        assert get_client_ip({"client": None}) == "127.0.0.1"
