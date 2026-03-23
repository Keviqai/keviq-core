"""JWT token verification for api-gateway."""

from __future__ import annotations

import os

import jwt

SECRET_KEY = os.environ.get('AUTH_JWT_SECRET')
if not SECRET_KEY:
    raise RuntimeError(
        "AUTH_JWT_SECRET environment variable is required. "
        "Service cannot start without JWT signing secret."
    )
ALGORITHM = 'HS256'


def verify_token(token: str) -> dict:
    """Verify and decode an access token. Returns the payload dict.
    Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get('type') != 'access':
        raise jwt.InvalidTokenError('Not an access token')
    return payload


from src.application.ports import JwtVerifier as JwtVerifierPort


class JwtVerifierAdapter(JwtVerifierPort):
    """Infrastructure adapter implementing JwtVerifier port."""

    def verify_token(self, token: str) -> dict:
        return verify_token(token)
