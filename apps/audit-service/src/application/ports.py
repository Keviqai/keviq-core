"""Application ports — abstract interfaces for audit-service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.audit_event import AuditEvent


class AuditRepository(ABC):
    @abstractmethod
    def insert(self, db, event: AuditEvent) -> dict:
        """Persist an audit event. Returns the stored dict."""

    @abstractmethod
    def find_by_workspace(
        self,
        db,
        workspace_id: UUID,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List audit events for a workspace, newest first."""
