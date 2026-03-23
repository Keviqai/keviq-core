"""User domain entity."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class User:
    id: uuid.UUID
    email: str
    display_name: str
    password_hash: str | None
    auth_provider: str
    auth_provider_id: str | None
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    @staticmethod
    def create_local(
        email: str,
        display_name: str,
        password_hash: str,
    ) -> User:
        now = datetime.now(timezone.utc)
        return User(
            id=uuid.uuid4(),
            email=email.lower().strip(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            auth_provider='local',
            auth_provider_id=None,
            created_at=now,
            updated_at=now,
            last_active_at=now,
        )
