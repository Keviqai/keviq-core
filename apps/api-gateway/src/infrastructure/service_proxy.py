"""Generic HTTP proxy to forward requests to backend services."""

from __future__ import annotations

import os
from typing import AsyncIterator

import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from src.internal_auth import get_auth_client

SERVICE_URLS = {
    'auth': os.getenv('AUTH_SERVICE_URL', 'http://auth-service:8000'),
    'workspace': os.getenv('WORKSPACE_SERVICE_URL', 'http://workspace-service:8000'),
    'policy': os.getenv('POLICY_SERVICE_URL', 'http://policy-service:8000'),
    'orchestrator': os.getenv('ORCHESTRATOR_URL', 'http://orchestrator:8000'),
    'event-store': os.getenv('EVENT_STORE_URL', 'http://event-store:8000'),
    'artifact': os.getenv('ARTIFACT_SERVICE_URL', 'http://artifact-service:8000'),
    'execution': os.getenv('EXECUTION_SERVICE_URL', 'http://execution-service:8000'),
    'secret': os.getenv('SECRET_BROKER_URL', 'http://secret-broker:8000'),
    'notification': os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000'),
    'model-gateway': os.getenv('MODEL_GATEWAY_URL', 'http://model-gateway:8000'),
    'audit': os.getenv('AUDIT_SERVICE_URL', 'http://audit-service:8000'),
    'telemetry': os.getenv('TELEMETRY_SERVICE_URL', 'http://telemetry-service:8000'),
}

TIMEOUT = float(os.getenv('PROXY_TIMEOUT', '30.0'))
# SSE connections are long-lived — use a much longer timeout
SSE_TIMEOUT = float(os.getenv('PROXY_SSE_TIMEOUT', '3600.0'))

# Shared client for connection pooling across normal requests
_http_client = httpx.AsyncClient(
    timeout=TIMEOUT,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
)
# Separate client for SSE streams — long timeout, capped connections
_sse_client = httpx.AsyncClient(
    timeout=httpx.Timeout(SSE_TIMEOUT, connect=10.0),
    limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
)

# Hop-by-hop headers that must not be forwarded
_STRIP_HEADERS = frozenset({
    'transfer-encoding', 'connection', 'keep-alive',
    'upgrade', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
    'content-type',  # set explicitly via media_type to avoid duplication
})


def _is_sse_path(path: str) -> bool:
    """Check if the path is an SSE streaming endpoint."""
    return path.rstrip('/').endswith('/events/stream')


def _build_proxy_headers(
    request: Request,
    service: str,
    extra_headers: dict | None = None,
) -> dict:
    """Build headers for proxying to a backend service."""
    headers = dict(request.headers)
    headers.pop('host', None)
    headers.pop('x-user-id', None)
    headers.pop('authorization', None)
    if extra_headers:
        headers.update(extra_headers)

    _SERVICE_AUDIENCE_MAP = {
        'orchestrator': 'orchestrator',
        'artifact': 'artifact-service',
        'event-store': 'event-store',
        'auth': 'auth-service',
        'workspace': 'workspace-service',
        'policy': 'policy-service',
        'execution': 'execution-service',
        'secret': 'secret-broker',
        'notification': 'notification-service',
        'model-gateway': 'model-gateway',
        'audit': 'audit-service',
        'telemetry': 'telemetry-service',
    }
    audience = _SERVICE_AUDIENCE_MAP.get(service)
    if audience:
        headers.update(get_auth_client().auth_headers(audience))

    return headers


async def proxy_request(
    service: str,
    path: str,
    request: Request,
    extra_headers: dict | None = None,
    extra_params: dict | None = None,
) -> Response:
    """Forward request to a backend service and return the response."""
    base_url = SERVICE_URLS.get(service)
    if not base_url:
        return Response(content='{"detail":"Unknown service"}', status_code=502, media_type='application/json')

    headers = _build_proxy_headers(request, service, extra_headers)

    params = {k: v for k, v in request.query_params.items() if k != 'token'}
    if extra_params:
        params.update(extra_params)

    # SSE streams need special handling — stream chunks through without buffering
    if _is_sse_path(path):
        return await _proxy_sse_stream(base_url, path, headers, params, request)

    body = await request.body()

    resp = await _http_client.request(
        method=request.method,
        url=f'{base_url}{path}',
        headers=headers,
        content=body,
        params=params,
    )

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in _STRIP_HEADERS
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get('content-type'),
    )


async def _proxy_sse_stream(
    base_url: str,
    path: str,
    headers: dict,
    params: dict,
    request: Request,
) -> StreamingResponse:
    """Proxy an SSE stream — true streaming without buffering."""

    async def _stream_chunks() -> AsyncIterator[bytes]:
        async with _sse_client.stream(
            'GET',
            f'{base_url}{path}',
            headers=headers,
            params=params,
        ) as resp:
            async for chunk in resp.aiter_bytes():
                yield chunk

    return StreamingResponse(
        _stream_chunks(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


from src.application.ports import ServiceProxy as ServiceProxyPort


class ServiceProxyAdapter(ServiceProxyPort):
    """Infrastructure adapter implementing ServiceProxy port."""

    async def proxy_request(self, service, path, request, extra_headers=None, extra_params=None):
        return await proxy_request(service, path, request, extra_headers=extra_headers, extra_params=extra_params)
