"""Application bootstrap — dependency provider for audit-service."""

from __future__ import annotations

from typing import Any

from src.application.ports import AuditRepository

_audit_repo: AuditRepository | None = None
_session_factory: Any = None
_configured = False


def configure_audit_deps(
    *,
    audit_repo: AuditRepository,
    session_factory: Any,
) -> None:
    global _audit_repo, _session_factory, _configured
    if _configured:
        raise RuntimeError("Audit dependencies already configured")
    _audit_repo = audit_repo
    _session_factory = session_factory
    _configured = True


def get_audit_repo() -> AuditRepository:
    if _audit_repo is None:
        raise RuntimeError("Audit repository not configured — call configure_audit_deps() at startup")
    return _audit_repo


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
