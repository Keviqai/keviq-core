"""Client-side helpers for attaching internal auth tokens to HTTP requests."""

from __future__ import annotations

from internal_auth.config import InternalAuthConfig
from internal_auth.token import InternalTokenIssuer


class InternalAuthClient:
    """Client-side helper for issuing internal auth tokens.

    Each service that calls other services creates one of these at startup.
    """

    def __init__(self, *, config: InternalAuthConfig):
        self._issuer = InternalTokenIssuer(
            secret=config.secret,
            service_name=config.service_name,
            issuer=config.issuer,
            ttl_seconds=config.token_ttl_seconds,
        )

    def auth_headers(self, audience: str) -> dict[str, str]:
        """Return Authorization headers for calling the target service."""
        token = self._issuer.issue(audience=audience)
        return {"Authorization": f"Bearer {token}"}
