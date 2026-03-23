"""FastAPI dependencies for auth-service."""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, status

from src.application.token_service import verify_access_token


def get_current_user_id(
    x_user_id: str | None = Header(None),
    authorization: str | None = Header(None),
) -> uuid.UUID:
    """Extract user_id from X-User-Id (gateway-injected) or Authorization header.

    Gateway strips Authorization before forwarding and injects X-User-Id instead.
    Accept both to support direct calls (tests, CLI) and proxied calls (browser).
    """
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid X-User-Id header',
            )
    if authorization and authorization.startswith('Bearer '):
        token = authorization[len('Bearer '):]
        try:
            return verify_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Missing Authorization or X-User-Id header',
    )
