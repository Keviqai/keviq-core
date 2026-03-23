"""Token operations exposed to the API layer."""

from __future__ import annotations

import uuid

from .bootstrap import get_jwt_handler


def verify_access_token(token: str) -> uuid.UUID:
    """Verify an access token and return the user_id. Raises ValueError on failure."""
    jwt_handler = get_jwt_handler()
    try:
        payload = jwt_handler.decode_token(token)
    except Exception as exc:
        raise ValueError('Invalid or expired token') from exc
    if payload.get('type') != 'access':
        raise ValueError('Invalid token type')
    return uuid.UUID(payload['sub'])
