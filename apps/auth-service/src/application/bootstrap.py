"""Application bootstrap — dependency provider for auth-service.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .ports import JwtHandler, PasswordHasher, UserRepository

_user_repo: UserRepository | None = None
_password_hasher: PasswordHasher | None = None
_jwt_handler: JwtHandler | None = None
_session_factory: Any = None
_configured = False


def configure_auth_deps(
    *,
    user_repo: UserRepository,
    password_hasher: PasswordHasher,
    jwt_handler: JwtHandler,
    session_factory: Any = None,
) -> None:
    """Set all auth dependencies. Called once at startup by infrastructure."""
    global _user_repo, _password_hasher, _jwt_handler, _session_factory, _configured
    if _configured:
        raise RuntimeError("Auth dependencies already configured")
    _user_repo = user_repo
    _password_hasher = password_hasher
    _jwt_handler = jwt_handler
    _session_factory = session_factory
    _configured = True


def get_user_repo() -> UserRepository:
    if _user_repo is None:
        raise RuntimeError("User repository not configured — call configure_auth_deps() at startup")
    return _user_repo


def get_password_hasher() -> PasswordHasher:
    if _password_hasher is None:
        raise RuntimeError("Password hasher not configured — call configure_auth_deps() at startup")
    return _password_hasher


def get_jwt_handler() -> JwtHandler:
    if _jwt_handler is None:
        raise RuntimeError("JWT handler not configured — call configure_auth_deps() at startup")
    return _jwt_handler


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
