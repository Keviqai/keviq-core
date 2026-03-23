"""Application ports — abstract interfaces for notification-service."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class NotificationRepository(ABC):
    """Port for notification persistence."""

    @abstractmethod
    def find_by_workspace_user(
        self, db, workspace_id: uuid.UUID, user_id: str,
        *, is_read: bool | None = None, delivery_status: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[dict]: ...

    @abstractmethod
    def count_unread(self, db, workspace_id: uuid.UUID, user_id: str) -> int: ...

    @abstractmethod
    def find_by_id(self, db, notification_id: uuid.UUID) -> dict | None: ...

    @abstractmethod
    def insert(self, db, notification: dict) -> dict: ...

    @abstractmethod
    def mark_read(self, db, notification_id: uuid.UUID, user_id: str, workspace_id: uuid.UUID | None = None) -> bool: ...

    @abstractmethod
    def mark_all_read(self, db, workspace_id: uuid.UUID, user_id: str) -> int: ...

    @abstractmethod
    def update_delivery_status(
        self, db, notification_id: uuid.UUID, *,
        delivery_status: str, delivery_attempts: int,
        last_delivery_error: str | None, delivered_at=None,
    ) -> None: ...


class EmailDelivery(ABC):
    """Port for email delivery."""

    @abstractmethod
    def send(self, *, to_email: str, subject: str, body_text: str) -> bool:
        """Send an email. Returns True on success, False on failure. Never raises."""
        ...
