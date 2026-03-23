"""Service bootstrap helpers for internal auth."""

from __future__ import annotations

from internal_auth.client import InternalAuthClient
from internal_auth.config import load_internal_auth_config
from internal_auth.fastapi_dep import configure_verifier
from internal_auth.token import InternalTokenVerifier

_auth_client: InternalAuthClient | None = None


def bootstrap_internal_auth(
    *,
    service_name: str,
) -> InternalAuthClient:
    """Configure internal auth for this service.

    Sets up:
    1. Token verifier for incoming internal requests
    2. Token issuer client for outgoing service calls

    Returns:
        InternalAuthClient for attaching tokens to outgoing requests.

    Raises:
        RuntimeError if INTERNAL_AUTH_SECRET is not set.
    """
    global _auth_client

    config = load_internal_auth_config(service_name=service_name)

    verifier = InternalTokenVerifier(
        secret=config.secret,
        expected_audience=config.service_name,
        issuer=config.issuer,
    )
    configure_verifier(verifier)

    _auth_client = InternalAuthClient(config=config)
    return _auth_client


def get_auth_client() -> InternalAuthClient:
    """Get the configured auth client. Fails if not bootstrapped."""
    if _auth_client is None:
        raise RuntimeError(
            "Internal auth not bootstrapped. "
            "Call bootstrap_internal_auth() during service startup."
        )
    return _auth_client
