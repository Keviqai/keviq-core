"""FastAPI middleware for request ID injection and access logging."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .context import get_request_id, new_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"

log = structlog.get_logger("http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-ID into context; logs request/response.

    - Reuses incoming X-Request-ID if present, otherwise generates new UUID.
    - Adds X-Request-ID to response headers.
    - Logs structured access line per request (method, path, status, duration).
    - Fail-safe: exceptions in middleware do not suppress the original response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        set_request_id(request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            log.error(
                "request failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        status = response.status_code

        if not request.url.path.startswith("/healthz"):
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status_code=status,
                duration_ms=duration_ms,
            )

        response.headers[REQUEST_ID_HEADER] = get_request_id()
        return response
