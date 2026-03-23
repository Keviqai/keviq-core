"""Application-layer port interfaces for policy-service.

Infrastructure implements these. No SQLAlchemy imports here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class PolicyRepository(ABC):
    @abstractmethod
    def find_policies_by_workspace(self, db, workspace_id: UUID, *, limit: int = 50, offset: int = 0) -> list[dict]: ...
    @abstractmethod
    def find_policy_by_id(self, db, policy_id: UUID) -> dict | None: ...
    @abstractmethod
    def insert_policy(self, db, policy: dict) -> dict: ...
    @abstractmethod
    def update_policy(self, db, policy_id: UUID, updates: dict) -> dict | None: ...
    @abstractmethod
    def log_permission_decision(
        self, db, *, actor_id: UUID, workspace_id: UUID,
        permission: str, decision: str, reason: str | None = None,
        resource_id: str | None = None,
    ) -> None: ...
