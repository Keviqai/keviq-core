"""JWT token handling — issue and verify."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

SECRET_KEY = os.environ.get('AUTH_JWT_SECRET')
if not SECRET_KEY:
    raise RuntimeError(
        "AUTH_JWT_SECRET environment variable is required. "
        "Service cannot start without JWT signing secret."
    )
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('AUTH_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('AUTH_REFRESH_TOKEN_EXPIRE_DAYS', '7'))


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'email': email,
        'iat': now,
        'exp': now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        'type': 'access',
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        'type': 'refresh',
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


from src.application.ports import JwtHandler as JwtHandlerPort


class JwtHandlerAdapter(JwtHandlerPort):
    """Infrastructure adapter implementing JwtHandler port."""

    def create_access_token(self, user_id: uuid.UUID, email: str) -> str:
        return create_access_token(user_id, email)

    def create_refresh_token(self, user_id: uuid.UUID) -> str:
        return create_refresh_token(user_id)

    def decode_token(self, token: str) -> dict:
        return decode_token(token)
