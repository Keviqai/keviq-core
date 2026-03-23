"""Configuration loading for internal service auth.

Fails fast if required environment variables are missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class InternalAuthConfig:
    """Configuration for internal service auth."""

    secret: str
    service_name: str
    issuer: str = "monaos-internal"
    token_ttl_seconds: int = 300  # 5 minutes


def load_internal_auth_config(
    *,
    service_name: str | None = None,
) -> InternalAuthConfig:
    """Load internal auth config from environment variables.

    Required env vars:
        INTERNAL_AUTH_SECRET — shared signing secret
        SERVICE_NAME — identity of this service (or pass service_name param)

    Optional env vars:
        INTERNAL_AUTH_ISSUER — token issuer (default: monaos-internal)
        INTERNAL_AUTH_TTL_SECONDS — token TTL in seconds (default: 300)

    Raises RuntimeError if required vars are missing.
    """
    secret = os.environ.get("INTERNAL_AUTH_SECRET")
    if not secret:
        raise RuntimeError(
            "INTERNAL_AUTH_SECRET environment variable is required. "
            "Service cannot start without internal auth configuration."
        )

    svc_name = service_name or os.environ.get("SERVICE_NAME")
    if not svc_name:
        raise RuntimeError(
            "SERVICE_NAME environment variable is required. "
            "Each service must have a unique identity."
        )

    issuer = os.environ.get("INTERNAL_AUTH_ISSUER", "monaos-internal")
    ttl = int(os.environ.get("INTERNAL_AUTH_TTL_SECONDS", "300"))

    return InternalAuthConfig(
        secret=secret,
        service_name=svc_name,
        issuer=issuer,
        token_ttl_seconds=ttl,
    )
