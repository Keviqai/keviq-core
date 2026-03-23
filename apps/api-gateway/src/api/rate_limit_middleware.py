"""ASGI middleware for tiered rate limiting.

Applies rate limiting based on route category and client identity:
- Auth routes: strict per-IP limits (handled by slowapi decorators)
- Write routes (POST/PUT/PATCH/DELETE): moderate per-user limits
- Read routes (GET): relaxed per-user limits
- Global per-IP: catch-all for all routes
- Health/internal routes: exempt

Uses a sliding-window counter algorithm with in-memory storage.
Thread-safe via threading.Lock.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.api.rate_limit import RateLimitConfig, RateLimitTier, get_client_ip, load_rate_limit_config

logger = logging.getLogger(__name__)

# Header used to identify the user (set by auth middleware / gateway proxy)
_USER_ID_HEADER = b"x-user-id"

# Internal service auth secret — requests with matching header bypass limits
_INTERNAL_SECRET = os.getenv("INTERNAL_AUTH_SECRET", "")

# Paths exempt from rate limiting
_EXEMPT_PREFIXES = ("/healthz/", "/metrics", "/internal/")

# Auth paths handled by slowapi decorators — skip middleware limiting
_AUTH_PATHS = frozenset({"/v1/auth/login", "/v1/auth/register"})

# Write HTTP methods
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SlidingWindowCounter:
    """Thread-safe sliding window counter for rate limiting.

    Tracks request timestamps per key within a configurable window.
    Old entries are pruned on each check to bound memory usage.
    """

    _NUM_SHARDS = 64
    _PRUNE_INTERVAL = 60.0  # seconds between prune runs
    _PRUNE_EVERY_N = 1000  # check prune every N calls

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}
        self._locks = [threading.Lock() for _ in range(self._NUM_SHARDS)]
        self._call_count = 0
        self._call_count_lock = threading.Lock()
        self._last_prune: float = time.monotonic()

    def _shard_lock(self, key: str) -> threading.Lock:
        return self._locks[hash(key) % self._NUM_SHARDS]

    def is_allowed(self, key: str, tier: RateLimitTier, now: float | None = None) -> tuple[bool, int, int]:
        """Check if a request is allowed under the given tier.

        Returns:
            (allowed, remaining, reset_after_seconds)
        """
        if now is None:
            now = time.monotonic()
        window_start = now - tier.window_seconds

        self._maybe_prune(now)

        with self._shard_lock(key):
            timestamps = self._windows.get(key, [])
            # Prune expired entries
            timestamps = [t for t in timestamps if t > window_start]

            remaining = max(0, tier.max_requests - len(timestamps))
            reset_after = self._compute_reset(timestamps, tier, now)

            if len(timestamps) >= tier.max_requests:
                self._windows[key] = timestamps
                return False, 0, reset_after

            timestamps.append(now)
            self._windows[key] = timestamps
            return True, remaining - 1, reset_after

    def _compute_reset(
        self, timestamps: list[float], tier: RateLimitTier, now: float,
    ) -> int:
        """Compute seconds until the window resets (oldest entry expires)."""
        if not timestamps:
            return tier.window_seconds
        oldest = timestamps[0]
        reset = int(oldest + tier.window_seconds - now) + 1
        return max(1, reset)

    def _maybe_prune(self, now: float) -> None:
        """Periodically run prune_stale based on call count and elapsed time."""
        with self._call_count_lock:
            self._call_count += 1
            if self._call_count < self._PRUNE_EVERY_N:
                return
            if now - self._last_prune < self._PRUNE_INTERVAL:
                return
            self._call_count = 0
            self._last_prune = now
        # Run prune outside the count lock
        self.prune_stale(now=now)

    def prune_stale(self, max_age: float = 120.0, *, now: float | None = None) -> None:
        """Remove keys with no recent activity (housekeeping)."""
        now = now if now is not None else time.monotonic()
        cutoff = now - max_age
        # Snapshot keys to avoid holding locks during iteration
        keys = list(self._windows.keys())
        for k in keys:
            with self._shard_lock(k):
                ts = self._windows.get(k)
                if ts is not None and (not ts or ts[-1] < cutoff):
                    del self._windows[k]


class RateLimitMiddleware:
    """ASGI middleware applying tiered rate limiting.

    Checks requests in order:
    1. Skip exempt paths (health, metrics, internal)
    2. Skip internal service-to-service calls
    3. Skip auth paths (handled by slowapi decorators)
    4. Apply per-user write/read limits (user from X-User-Id header)
    5. Apply global per-IP limit
    """

    def __init__(self, app: ASGIApp, config: RateLimitConfig | None = None) -> None:
        self.app = app
        self.config = config or load_rate_limit_config()
        self._counter = SlidingWindowCounter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        # 1. Exempt paths
        if self._is_exempt(path):
            await self.app(scope, receive, send)
            return

        # 2. Internal service calls bypass
        if self._is_internal_call(scope):
            await self.app(scope, receive, send)
            return

        # 3. Auth paths — handled by slowapi decorators
        if path.rstrip("/") in _AUTH_PATHS:
            await self.app(scope, receive, send)
            return

        # 4. Determine identity and tier
        user_id = self._extract_user_id(scope)
        client_ip = get_client_ip(scope)

        # Per-user or per-IP tier check
        tier_result = self._check_tier(method, user_id, client_ip)
        if tier_result is not None:
            allowed, remaining, reset_after, limit = tier_result
            if not allowed:
                await self._send_429(scope, send, reset_after, limit)
                return
            # Store headers for response injection
            scope["_rate_limit_headers"] = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_after),
            }

        # 5. Global per-IP check (always applies)
        ip_key = f"global:ip:{client_ip}"
        g_allowed, g_remaining, g_reset = self._counter.is_allowed(
            ip_key, self.config.global_per_ip,
        )
        if not g_allowed:
            await self._send_429(
                scope, send, g_reset, self.config.global_per_ip.max_requests,
            )
            return

        # Wrap send to inject rate limit headers
        headers_to_inject = scope.get("_rate_limit_headers", {})
        wrapped_send = self._make_header_injector(send, headers_to_inject)
        await self.app(scope, receive, wrapped_send)

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    def _is_internal_call(self, scope: Scope) -> bool:
        """Check if request is an internal service-to-service call."""
        if not _INTERNAL_SECRET:
            return False
        headers = dict(scope.get("headers", []))
        internal_marker = headers.get(b"x-internal-service", b"").decode(
            "utf-8", errors="ignore",
        )
        # Validate the header value matches the configured secret
        if internal_marker and internal_marker == _INTERNAL_SECRET:
            return True
        return False

    def _extract_user_id(self, scope: Scope) -> str | None:
        """Extract user ID from request headers."""
        headers = scope.get("headers", [])
        for name, value in headers:
            if name == _USER_ID_HEADER:
                return value.decode("utf-8", errors="ignore")
        return None

    def _check_tier(
        self, method: str, user_id: str | None, client_ip: str,
    ) -> tuple[bool, int, int, int] | None:
        """Check the appropriate tier limit.

        Returns (allowed, remaining, reset_after, limit) or None.
        """
        if method in _WRITE_METHODS:
            tier = self.config.write
            identity = user_id or client_ip
            key = f"write:{'user' if user_id else 'ip'}:{identity}"
        elif method == "GET":
            tier = self.config.read
            identity = user_id or client_ip
            key = f"read:{'user' if user_id else 'ip'}:{identity}"
        else:
            return None

        allowed, remaining, reset_after = self._counter.is_allowed(key, tier)
        return allowed, remaining, reset_after, tier.max_requests

    async def _send_429(
        self, scope: Scope, send: Send, retry_after: int, limit: int,
    ) -> None:
        """Send a 429 Too Many Requests response."""
        body = b'{"detail":"Rate limit exceeded. Try again later."}'
        headers = [
            (b"content-type", b"application/json"),
            (b"retry-after", str(retry_after).encode()),
            (b"x-ratelimit-limit", str(limit).encode()),
            (b"x-ratelimit-remaining", b"0"),
            (b"x-ratelimit-reset", str(retry_after).encode()),
        ]
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })

    def _make_header_injector(
        self, send: Send, headers_to_inject: dict[str, str],
    ) -> Callable:
        """Wrap send to inject rate limit headers into the response."""
        if not headers_to_inject:
            return send

        async def injector(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = list(message.get("headers", []))
                for name, value in headers_to_inject.items():
                    existing.append((name.lower().encode(), value.encode()))
                message["headers"] = existing
            await send(message)

        return injector
