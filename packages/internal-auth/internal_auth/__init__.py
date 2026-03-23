"""Internal service-to-service authentication for Keviq Core.

This package provides JWT-based service identity for internal API calls.
It is separate from user/session auth (auth-service) and must never be
mixed with end-user tokens.
"""

from internal_auth.token import (
    InternalTokenIssuer,
    InternalTokenVerifier,
    InternalTokenClaims,
    InternalAuthError,
    InvalidTokenError,
    ExpiredTokenError,
    WrongAudienceError,
    UnauthorizedServiceError,
)
from internal_auth.config import InternalAuthConfig, load_internal_auth_config
from internal_auth.fastapi_dep import require_internal_auth, require_service, configure_verifier
from internal_auth.client import InternalAuthClient
from internal_auth.bootstrap import bootstrap_internal_auth, get_auth_client

__all__ = [
    "InternalTokenIssuer",
    "InternalTokenVerifier",
    "InternalTokenClaims",
    "InternalAuthError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "WrongAudienceError",
    "UnauthorizedServiceError",
    "InternalAuthConfig",
    "load_internal_auth_config",
    "require_internal_auth",
    "require_service",
    "configure_verifier",
    "InternalAuthClient",
    "bootstrap_internal_auth",
    "get_auth_client",
]
