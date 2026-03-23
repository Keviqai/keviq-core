"""Workspace and Member domain entities."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Workspace:
    id: uuid.UUID
    slug: str
    display_name: str
    plan: str
    deployment_mode: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    settings: dict

    @staticmethod
    def create(slug: str, display_name: str, owner_id: uuid.UUID) -> Workspace:
        now = datetime.now(timezone.utc)
        return Workspace(
            id=uuid.uuid4(),
            slug=_slugify(slug),
            display_name=display_name.strip(),
            plan='personal',
            deployment_mode='local',
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
            settings={},
        )


@dataclass
class Member:
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    updated_at: datetime
    invited_by_id: uuid.UUID | None


VALID_ROLES = {'owner', 'admin', 'editor', 'viewer'}


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text
