"""Application-layer proxy facade — keeps api/ from importing infrastructure/."""

from __future__ import annotations

from fastapi import Request, Response

from .bootstrap import get_service_proxy


async def forward_to_service(
    service: str,
    path: str,
    request: Request,
    extra_headers: dict | None = None,
    extra_params: dict | None = None,
) -> Response:
    """Forward request to a backend service."""
    return await get_service_proxy().proxy_request(
        service, path, request,
        extra_headers=extra_headers,
        extra_params=extra_params,
    )
