"""Application bootstrap — dependency provider for integration management.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .integration_ports import IntegrationRepository

_integration_repo: IntegrationRepository | None = None
_session_factory: Any = None
_configured = False


def configure_integration_deps(
    *,
    integration_repo: IntegrationRepository,
    session_factory: Any = None,
) -> None:
    global _integration_repo, _session_factory, _configured
    if _configured:
        raise RuntimeError("Integration dependencies already configured")
    _integration_repo = integration_repo
    _session_factory = session_factory
    _configured = True


def get_integration_repo() -> IntegrationRepository:
    if _integration_repo is None:
        raise RuntimeError("Integration repository not configured — call configure_integration_deps() at startup")
    return _integration_repo


def get_integration_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Integration session factory not configured")
    return _session_factory
