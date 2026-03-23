"""Lightweight in-memory metrics registry with Prometheus text exposition.

Provides counters for HTTP request metrics and a /metrics endpoint response.
No external dependencies — all state is in-process, reset on restart.

Usage:
    from mona_os_logger.metrics import MetricsRegistry, MetricsMiddleware

    metrics = MetricsRegistry(service="api-gateway")
    app.add_middleware(MetricsMiddleware, registry=metrics)

    @app.get("/metrics")
    def metrics_endpoint():
        return metrics.prometheus_response()
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

# Route normalization: replace UUID-like segments with {id}
_UUID_PATTERN = re.compile(
    r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE,
)


def _normalize_route(path: str) -> str:
    """Normalize request path to prevent high-cardinality labels.

    Replaces UUID segments with {id}. Strips trailing slashes.
    """
    normalized = _UUID_PATTERN.sub('/{id}', path.rstrip('/'))
    return normalized or '/'


class MetricsRegistry:
    """Thread-safe in-memory metrics registry.

    Tracks:
    - mona_http_requests_total{service, method, route, status_class}
    - mona_http_request_duration_ms_sum{service, method, route}
    - mona_http_request_duration_ms_count{service, method, route}
    - mona_http_request_errors_total{service, method, route, status_code}
    """

    def __init__(self, service: str):
        self.service = service
        self._lock = threading.Lock()
        self._request_total: dict[tuple[str, str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._error_total: dict[tuple[str, str, int], int] = defaultdict(int)
        self._custom_counters: dict[str, dict[tuple, int]] = {}
        self._custom_counter_labels: dict[str, tuple[str, ...]] = {}

    def record_request(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record an HTTP request metric."""
        status_class = f"{status_code // 100}xx"
        with self._lock:
            self._request_total[(method, route, status_class)] += 1
            self._duration_sum[(method, route)] += duration_ms
            self._duration_count[(method, route)] += 1
            if status_code >= 400:
                self._error_total[(method, route, status_code)] += 1

    def register_counter(self, name: str, labels: tuple[str, ...]) -> None:
        """Register a custom counter for domain metrics (O8-S2)."""
        with self._lock:
            if name not in self._custom_counters:
                self._custom_counters[name] = defaultdict(int)
                self._custom_counter_labels[name] = labels

    def inc_counter(self, name: str, label_values: tuple, delta: int = 1) -> None:
        """Increment a custom counter."""
        with self._lock:
            if name in self._custom_counters:
                self._custom_counters[name][label_values] += delta

    def prometheus_text(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        lines: list[str] = []

        with self._lock:
            # Request total
            lines.append('# HELP mona_http_requests_total Total HTTP requests')
            lines.append('# TYPE mona_http_requests_total counter')
            for (method, route, status_class), count in sorted(self._request_total.items()):
                lines.append(
                    f'mona_http_requests_total{{service="{self.service}",method="{method}",'
                    f'route="{route}",status_class="{status_class}"}} {count}'
                )

            # Duration sum (for computing averages)
            lines.append('# HELP mona_http_request_duration_ms_sum Total request duration in ms')
            lines.append('# TYPE mona_http_request_duration_ms_sum counter')
            for (method, route), total in sorted(self._duration_sum.items()):
                lines.append(
                    f'mona_http_request_duration_ms_sum{{service="{self.service}",method="{method}",'
                    f'route="{route}"}} {total:.1f}'
                )

            # Duration count
            lines.append('# HELP mona_http_request_duration_ms_count Request count for duration average')
            lines.append('# TYPE mona_http_request_duration_ms_count counter')
            for (method, route), count in sorted(self._duration_count.items()):
                lines.append(
                    f'mona_http_request_duration_ms_count{{service="{self.service}",method="{method}",'
                    f'route="{route}"}} {count}'
                )

            # Error total
            lines.append('# HELP mona_http_request_errors_total Total HTTP errors (4xx+5xx)')
            lines.append('# TYPE mona_http_request_errors_total counter')
            for (method, route, status_code), count in sorted(self._error_total.items()):
                lines.append(
                    f'mona_http_request_errors_total{{service="{self.service}",method="{method}",'
                    f'route="{route}",status_code="{status_code}"}} {count}'
                )

            # Custom counters (for O8-S2)
            for name, data in sorted(self._custom_counters.items()):
                labels = self._custom_counter_labels[name]
                lines.append(f'# TYPE {name} counter')
                for label_values, count in sorted(data.items()):
                    if labels:
                        label_pairs = ','.join(
                            f'{k}="{v}"' for k, v in zip(labels, label_values)
                        )
                        lines.append(f'{name}{{{label_pairs}}} {count}')
                    else:
                        lines.append(f'{name} {count}')

        lines.append('')  # trailing newline
        return '\n'.join(lines)

    def prometheus_response(self) -> PlainTextResponse:
        """Return a Starlette response with Prometheus text format."""
        return PlainTextResponse(
            content=self.prometheus_text(),
            media_type='text/plain; version=0.0.4; charset=utf-8',
        )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request metrics.

    Add after RequestIdMiddleware. Skips /healthz and /metrics paths.
    """

    def __init__(self, app: Any, registry: MetricsRegistry):
        super().__init__(app)
        self._registry = registry

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        # Skip health checks and metrics endpoint itself
        if path.startswith('/healthz') or path == '/metrics':
            return await call_next(request)

        route = _normalize_route(path)
        method = request.method
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            self._registry.record_request(method, route, 500, duration_ms)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        self._registry.record_request(method, route, response.status_code, duration_ms)
        return response
