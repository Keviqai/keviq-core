"""Application bootstrap — dependency provider for workspace-service.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .ports import MemberEnricher, OutboxWriter, WorkspaceRepository

_workspace_repo: WorkspaceRepository | None = None
_outbox_writer: OutboxWriter | None = None
_member_enricher: MemberEnricher | None = None
_session_factory: Any = None
_configured = False


def configure_workspace_deps(
    *,
    workspace_repo: WorkspaceRepository,
    outbox_writer: OutboxWriter,
    member_enricher: MemberEnricher | None = None,
    session_factory: Any = None,
) -> None:
    """Set all workspace dependencies. Called once at startup by infrastructure."""
    global _workspace_repo, _outbox_writer, _member_enricher, _session_factory, _configured
    if _configured:
        raise RuntimeError("Workspace dependencies already configured")
    _workspace_repo = workspace_repo
    _outbox_writer = outbox_writer
    _member_enricher = member_enricher
    _session_factory = session_factory
    _configured = True


def get_workspace_repo() -> WorkspaceRepository:
    if _workspace_repo is None:
        raise RuntimeError("Workspace repository not configured — call configure_workspace_deps() at startup")
    return _workspace_repo


def get_member_enricher() -> MemberEnricher | None:
    return _member_enricher


def get_outbox_writer() -> OutboxWriter:
    if _outbox_writer is None:
        raise RuntimeError("Outbox writer not configured — call configure_workspace_deps() at startup")
    return _outbox_writer


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
