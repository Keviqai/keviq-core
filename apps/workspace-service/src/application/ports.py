"""Application-layer port interfaces for workspace-service.

Infrastructure implements these. No SQLAlchemy imports here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class WorkspaceRepository(ABC):
    @abstractmethod
    def find_workspace_by_id(self, db, workspace_id: UUID) -> dict | None: ...
    @abstractmethod
    def find_workspace_by_slug(self, db, slug: str) -> dict | None: ...
    @abstractmethod
    def find_workspaces_by_user(self, db, user_id: UUID, *, limit: int = 50, offset: int = 0) -> list[dict]: ...
    @abstractmethod
    def insert_workspace(self, db, ws: dict) -> dict: ...
    @abstractmethod
    def update_workspace(self, db, workspace_id: UUID, updates: dict) -> dict | None: ...
    @abstractmethod
    def delete_workspace(self, db, workspace_id: UUID) -> bool: ...
    @abstractmethod
    def find_members_by_workspace(self, db, workspace_id: UUID, *, limit: int = 200, offset: int = 0) -> list[dict]: ...
    @abstractmethod
    def find_member(self, db, workspace_id: UUID, user_id: UUID) -> dict | None: ...
    @abstractmethod
    def insert_member(self, db, mem: dict) -> dict: ...
    @abstractmethod
    def update_member_role(self, db, workspace_id: UUID, user_id: UUID, role: str) -> dict | None: ...
    @abstractmethod
    def delete_member(self, db, workspace_id: UUID, user_id: UUID) -> bool: ...


class MemberEnricher(ABC):
    """Port: enrich member dicts with display_name and email fields."""
    @abstractmethod
    def enrich(self, members: list[dict]) -> None:
        """Mutate members in-place — add display_name and email."""
        ...


class OutboxWriter(ABC):
    @abstractmethod
    def insert_event(
        self,
        db,
        event_type: str,
        workspace_id: UUID,
        payload: dict,
        correlation_id: UUID,
        actor_id: str,
        actor_type: str = 'user',
        causation_id: UUID | None = None,
    ) -> None: ...
