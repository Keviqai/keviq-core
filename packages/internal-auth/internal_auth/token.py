"""Internal JWT token issuing and verification.

These tokens are for service-to-service auth only.
They are NOT user/session tokens and must never be mixed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"


# ── Exception hierarchy ──────────────────────────────────────────


class InternalAuthError(Exception):
    """Base class for internal auth errors."""


class InvalidTokenError(InternalAuthError):
    """Token is malformed, has wrong signature, or fails validation."""


class ExpiredTokenError(InternalAuthError):
    """Token has expired."""


class WrongAudienceError(InternalAuthError):
    """Token audience does not match expected service."""


class UnauthorizedServiceError(InternalAuthError):
    """Caller service is not in the allowed service list."""


# ── Claims model ─────────────────────────────────────────────────


@dataclass(frozen=True)
class InternalTokenClaims:
    """Validated claims from an internal service token."""

    sub: str  # service_name of the caller
    aud: str  # intended recipient service
    iss: str  # issuer (monaos-internal)
    jti: str  # unique token ID
    iat: datetime
    exp: datetime
    service_name: str  # explicit service identity claim


# ── Issuer ───────────────────────────────────────────────────────


class InternalTokenIssuer:
    """Issues signed internal JWTs for service-to-service calls."""

    def __init__(
        self,
        *,
        secret: str,
        service_name: str,
        issuer: str = "monaos-internal",
        ttl_seconds: int = 300,
    ):
        if not secret:
            raise ValueError("Internal auth secret must not be empty")
        if not service_name:
            raise ValueError("Service name must not be empty")
        self._secret = secret
        self._service_name = service_name
        self._issuer = issuer
        self._ttl_seconds = ttl_seconds

    def issue(self, *, audience: str) -> str:
        """Issue a signed JWT for the given audience (target service)."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": self._service_name,
            "aud": audience,
            "iss": self._issuer,
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(seconds=self._ttl_seconds),
            "service_name": self._service_name,
        }
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM)


# ── Verifier ─────────────────────────────────────────────────────


class InternalTokenVerifier:
    """Verifies incoming internal service tokens."""

    def __init__(
        self,
        *,
        secret: str,
        expected_audience: str,
        issuer: str = "monaos-internal",
    ):
        if not secret:
            raise ValueError("Internal auth secret must not be empty")
        if not expected_audience:
            raise ValueError("Expected audience must not be empty")
        self._secret = secret
        self._expected_audience = expected_audience
        self._issuer = issuer

    def verify(
        self,
        token: str,
        *,
        allowed_services: list[str] | None = None,
    ) -> InternalTokenClaims:
        """Verify token and return validated claims.

        Raises:
            InvalidTokenError: Token is malformed or has wrong signature.
            ExpiredTokenError: Token has expired.
            WrongAudienceError: Token audience doesn't match this service.
            UnauthorizedServiceError: Caller service not in allowed list.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                audience=self._expected_audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError("Internal token has expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise WrongAudienceError(
                f"Token audience does not match expected service "
                f"'{self._expected_audience}'"
            ) from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidTokenError(
                f"Token issuer does not match expected '{self._issuer}'"
            ) from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(f"Invalid internal token: {exc}") from exc

        service_name = payload.get("service_name", payload.get("sub", ""))

        if allowed_services is not None and service_name not in allowed_services:
            raise UnauthorizedServiceError(
                f"Service '{service_name}' is not authorized to call this endpoint. "
                f"Allowed: {allowed_services}"
            )

        return InternalTokenClaims(
            sub=payload["sub"],
            aud=payload["aud"],
            iss=payload["iss"],
            jti=payload.get("jti", ""),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            service_name=service_name,
        )
