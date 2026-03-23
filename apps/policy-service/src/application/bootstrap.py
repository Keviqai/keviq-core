"""Application bootstrap — dependency provider for policy-service.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .ports import PolicyRepository

_policy_repo: PolicyRepository | None = None
_session_factory: Any = None
_configured = False


def configure_policy_deps(
    *,
    policy_repo: PolicyRepository,
    session_factory: Any = None,
) -> None:
    global _policy_repo, _session_factory, _configured
    if _configured:
        raise RuntimeError("Policy dependencies already configured")
    _policy_repo = policy_repo
    _session_factory = session_factory
    _configured = True


def get_policy_repo() -> PolicyRepository:
    if _policy_repo is None:
        raise RuntimeError("Policy repository not configured — call configure_policy_deps() at startup")
    return _policy_repo


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
