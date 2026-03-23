"""Rate limiting configuration for api-gateway.

Provides:
- slowapi Limiter for auth-specific route decorators (login, register)
- RateLimitConfig with per-tier limits configurable via env vars
- Helper to extract client identity (user ID or IP fallback)

Uses in-memory storage (single-instance). Switch to Redis backend
when scaling to multiple gateway instances.

NOTE: get_remote_address uses request.client.host (TCP peer). When
deployed behind a reverse proxy, update key_func to read from a
trusted X-Forwarded-For header with proxy allowlist.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from slowapi import Limiter
from slowapi.util import get_remote_address

# ── slowapi limiter (used by auth route decorators) ──────────────
limiter = Limiter(key_func=get_remote_address)


@dataclass(frozen=True)
class RateLimitTier:
    """Rate limit for a single tier: max requests per window."""

    max_requests: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitConfig:
    """Tiered rate-limit configuration loaded from env vars."""

    auth_login: RateLimitTier
    auth_register: RateLimitTier
    write: RateLimitTier
    read: RateLimitTier
    global_per_ip: RateLimitTier


def load_rate_limit_config() -> RateLimitConfig:
    """Load rate limit configuration from environment variables.

    Env vars (all optional, sensible defaults provided):
      RATE_LIMIT_AUTH_LOGIN      — e.g. "10/60" (requests/seconds)
      RATE_LIMIT_AUTH_REGISTER   — e.g. "5/60"
      RATE_LIMIT_WRITE           — e.g. "60/60"
      RATE_LIMIT_READ            — e.g. "300/60"
      RATE_LIMIT_GLOBAL_IP       — e.g. "600/60"
    """
    return RateLimitConfig(
        auth_login=_parse_tier(os.getenv("RATE_LIMIT_AUTH_LOGIN", "10/60")),
        auth_register=_parse_tier(os.getenv("RATE_LIMIT_AUTH_REGISTER", "5/60")),
        write=_parse_tier(os.getenv("RATE_LIMIT_WRITE", "60/60")),
        read=_parse_tier(os.getenv("RATE_LIMIT_READ", "300/60")),
        global_per_ip=_parse_tier(os.getenv("RATE_LIMIT_GLOBAL_IP", "600/60")),
    )


def _parse_tier(value: str) -> RateLimitTier:
    """Parse 'max_requests/window_seconds' string into RateLimitTier."""
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid rate limit format: {value!r} (expected 'N/S')")
    return RateLimitTier(
        max_requests=int(parts[0]),
        window_seconds=int(parts[1]),
    )


def get_client_ip(scope: dict) -> str:
    """Extract client IP from ASGI scope.

    Returns '127.0.0.1' if client info is unavailable.
    """
    client = scope.get("client")
    if client and len(client) >= 1:
        return str(client[0])
    return "127.0.0.1"
