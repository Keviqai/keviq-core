"""Application ports — abstract interfaces for secret-broker."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class SecretRepository(ABC):
    """Port for secret persistence."""

    @abstractmethod
    def find_by_workspace(self, db, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> list[dict]: ...

    @abstractmethod
    def find_by_id(self, db, secret_id: uuid.UUID) -> dict | None: ...

    @abstractmethod
    def find_raw_by_id(self, db, secret_id: uuid.UUID, workspace_id: uuid.UUID) -> dict | None:
        """Return secret row including secret_ciphertext. Internal use only."""
        ...

    @abstractmethod
    def insert(self, db, secret: dict) -> dict: ...

    @abstractmethod
    def delete(self, db, secret_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> bool: ...

    @abstractmethod
    def update_metadata(self, db, secret_id: uuid.UUID, updates: dict, workspace_id: uuid.UUID | None = None) -> dict | None: ...

    @abstractmethod
    def find_all_raw_by_workspace(self, db, workspace_id: uuid.UUID) -> list[dict]:
        """Return all secret rows with ciphertext for a workspace (rotation)."""
        ...

    @abstractmethod
    def update_ciphertext(
        self, db, secret_id: uuid.UUID, workspace_id: uuid.UUID,
        ciphertext: str, key_version: int,
    ) -> bool:
        """Update ciphertext and key version after re-encryption."""
        ...
