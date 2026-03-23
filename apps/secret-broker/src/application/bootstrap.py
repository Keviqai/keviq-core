"""Application bootstrap — dependency provider for secret-broker.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .ports import SecretRepository

_secret_repo: SecretRepository | None = None
_session_factory: Any = None
_configured = False


def configure_secret_deps(
    *,
    secret_repo: SecretRepository,
    session_factory: Any = None,
) -> None:
    global _secret_repo, _session_factory, _configured
    if _configured:
        raise RuntimeError("Secret dependencies already configured")
    _secret_repo = secret_repo
    _session_factory = session_factory
    _configured = True


def get_secret_repo() -> SecretRepository:
    if _secret_repo is None:
        raise RuntimeError("Secret repository not configured — call configure_secret_deps() at startup")
    return _secret_repo


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
