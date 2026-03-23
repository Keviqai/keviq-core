"""Unit tests for rate limit ASGI middleware.

Tests cover:
- Exempt paths (health, metrics, internal) bypass limiting
- Auth paths delegated to slowapi (not middleware)
- Per-user read/write limiting with separate counters
- Per-IP fallback when no X-User-Id header
- 429 with Retry-After and X-RateLimit-* headers
- Global per-IP catch-all limit
- Internal service-to-service bypass
- Different tiers enforce different limits
- Non-HTTP scopes pass through
- Successful responses include rate limit headers
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.api.rate_limit import RateLimitConfig, RateLimitTier
from src.api.rate_limit_middleware import RateLimitMiddleware


def _make_scope(
    path: str = "/v1/tasks",
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] = ("10.0.0.1", 12345),
) -> dict:
    """Build a minimal ASGI HTTP scope for testing."""
    return {
        "type": "http",
        "path": path,
        "method": method,
        "headers": headers or [],
        "client": client,
        "query_string": b"",
    }


def _make_config(
    write_max: int = 60,
    read_max: int = 300,
    global_max: int = 600,
) -> RateLimitConfig:
    """Build a test config with customisable tier limits."""
    return RateLimitConfig(
        auth_login=RateLimitTier(10, 60),
        auth_register=RateLimitTier(5, 60),
        write=RateLimitTier(write_max, 60),
        read=RateLimitTier(read_max, 60),
        global_per_ip=RateLimitTier(global_max, 60),
    )


# ── Exempt path tests ───────────────────────────────────────────


class TestExemptPaths:
    """Paths that should never be rate-limited."""

    @pytest.mark.asyncio
    async def test_health_path_exempt(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1))
        scope = _make_scope(path="/healthz/live", method="GET")

        for _ in range(10):
            await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 10

    @pytest.mark.asyncio
    async def test_metrics_path_exempt(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1))
        scope = _make_scope(path="/metrics", method="GET")

        for _ in range(5):
            await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 5

    @pytest.mark.asyncio
    async def test_internal_path_exempt(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1))
        scope = _make_scope(path="/internal/v1/something", method="GET")

        for _ in range(5):
            await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 5

    @pytest.mark.asyncio
    async def test_auth_paths_skip_middleware(self) -> None:
        """Auth paths are handled by slowapi decorators, not middleware."""
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(write_max=1))
        scope = _make_scope(path="/v1/auth/login", method="POST")

        for _ in range(5):
            await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 5

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1))
        scope = {"type": "websocket", "path": "/ws"}

        await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 1


# ── Tier enforcement tests ──────────────────────────────────────


class TestTierEnforcement:
    """Read/write/global tiers enforce correct limits."""

    @pytest.mark.asyncio
    async def test_read_limit_enforced(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=2, global_max=100))
        scope = _make_scope(path="/v1/tasks", method="GET")
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 2

        responses.clear()
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 2
        assert any(r.get("status") == 429 for r in responses)

    @pytest.mark.asyncio
    async def test_write_limit_enforced(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(write_max=1, global_max=100))
        scope = _make_scope(path="/v1/tasks", method="POST")
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 1

        responses.clear()
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 1
        assert any(r.get("status") == 429 for r in responses)

    @pytest.mark.asyncio
    async def test_global_ip_limit(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=100, global_max=2))
        scope = _make_scope(path="/v1/tasks", method="GET")
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 2

        responses.clear()
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 2
        assert any(r.get("status") == 429 for r in responses)

    @pytest.mark.asyncio
    async def test_different_tiers_different_limits(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(
            app, config=_make_config(write_max=1, read_max=3, global_max=100),
        )
        write_scope = _make_scope(path="/v1/tasks", method="POST")
        read_scope = _make_scope(path="/v1/tasks", method="GET")

        await mw(write_scope, AsyncMock(), AsyncMock())
        assert app.call_count == 1

        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(write_scope, AsyncMock(), capture_send)
        assert app.call_count == 1  # blocked

        for _ in range(3):
            await mw(read_scope, AsyncMock(), AsyncMock())
        assert app.call_count == 4  # 1 write + 3 reads


# ── Identity tracking tests ─────────────────────────────────────


class TestIdentityTracking:
    """Per-user and per-IP tracking."""

    @pytest.mark.asyncio
    async def test_per_user_tracking(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1, global_max=100))

        scope_alice = _make_scope(
            path="/v1/tasks", method="GET",
            headers=[(b"x-user-id", b"alice")],
        )
        scope_bob = _make_scope(
            path="/v1/tasks", method="GET",
            headers=[(b"x-user-id", b"bob")],
        )

        await mw(scope_alice, AsyncMock(), AsyncMock())
        await mw(scope_bob, AsyncMock(), AsyncMock())
        assert app.call_count == 2

    @pytest.mark.asyncio
    async def test_ip_fallback_when_no_user(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1, global_max=100))
        scope = _make_scope(
            path="/v1/tasks", method="GET", client=("1.2.3.4", 9999),
        )
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 1

        responses.clear()
        await mw(scope, AsyncMock(), capture_send)
        assert app.call_count == 1
        assert any(r.get("status") == 429 for r in responses)

    @pytest.mark.asyncio
    async def test_internal_service_bypass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "test-secret-123")
        import importlib
        import src.api.rate_limit_middleware as rlm
        importlib.reload(rlm)

        app = AsyncMock()
        mw = rlm.RateLimitMiddleware(app, config=_make_config(read_max=1, global_max=1))
        scope = _make_scope(
            path="/v1/tasks", method="GET",
            headers=[
                (b"authorization", b"Bearer internal-jwt-token"),
                (b"x-internal-service", b"test-secret-123"),
            ],
        )

        for _ in range(5):
            await mw(scope, AsyncMock(), AsyncMock())
        assert app.call_count == 5


# ── Response header tests ───────────────────────────────────────


class TestResponseHeaders:
    """Rate limit headers in responses."""

    @pytest.mark.asyncio
    async def test_429_includes_retry_after(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1, global_max=100))
        scope = _make_scope(path="/v1/tasks", method="GET")
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        responses.clear()
        await mw(scope, AsyncMock(), capture_send)

        start_msg = next(r for r in responses if r.get("type") == "http.response.start")
        headers_dict = {k: v for k, v in start_msg["headers"]}
        assert b"retry-after" in headers_dict
        assert int(headers_dict[b"retry-after"]) >= 1

    @pytest.mark.asyncio
    async def test_429_includes_rate_limit_headers(self) -> None:
        app = AsyncMock()
        mw = RateLimitMiddleware(app, config=_make_config(read_max=1, global_max=100))
        scope = _make_scope(path="/v1/tasks", method="GET")
        responses: list[dict] = []

        async def capture_send(msg: dict) -> None:
            responses.append(msg)

        await mw(scope, AsyncMock(), capture_send)
        responses.clear()
        await mw(scope, AsyncMock(), capture_send)

        start_msg = next(r for r in responses if r.get("type") == "http.response.start")
        headers_dict = {k: v for k, v in start_msg["headers"]}
        assert b"x-ratelimit-limit" in headers_dict
        assert b"x-ratelimit-remaining" in headers_dict
        assert headers_dict[b"x-ratelimit-remaining"] == b"0"
        assert b"x-ratelimit-reset" in headers_dict

    @pytest.mark.asyncio
    async def test_success_response_has_headers(self) -> None:
        captured: list[dict] = []

        async def fake_app(scope: dict, receive: object, send: object) -> None:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": b"{}"})

        mw = RateLimitMiddleware(fake_app, config=_make_config(read_max=10, global_max=100))
        scope = _make_scope(path="/v1/tasks", method="GET")

        async def capture_send(msg: dict) -> None:
            captured.append(msg)

        await mw(scope, AsyncMock(), capture_send)

        start_msg = next(m for m in captured if m["type"] == "http.response.start")
        headers_dict = {k: v for k, v in start_msg["headers"]}
        assert b"x-ratelimit-limit" in headers_dict
        assert b"x-ratelimit-remaining" in headers_dict
        assert b"x-ratelimit-reset" in headers_dict
