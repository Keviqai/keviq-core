"""Application ports — abstract interfaces for integration management."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class IntegrationRepository(ABC):
    """Port for workspace integration persistence."""

    @abstractmethod
    def find_by_workspace(
        self, db: Session, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
    ) -> list[dict]: ...

    @abstractmethod
    def find_by_id(
        self, db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
    ) -> dict | None: ...

    @abstractmethod
    def insert(self, db: Session, integration: dict) -> dict: ...

    @abstractmethod
    def update(
        self, db: Session, integration_id: uuid.UUID, updates: dict,
        workspace_id: uuid.UUID,
    ) -> dict | None: ...

    @abstractmethod
    def delete(
        self, db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
    ) -> bool: ...

    @abstractmethod
    def toggle_enabled(
        self, db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
    ) -> dict | None: ...
