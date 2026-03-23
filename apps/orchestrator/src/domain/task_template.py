"""TaskTemplate domain entity.

System and workspace-scoped templates that prefill task brief fields.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.domain.errors import DomainValidationError


class TemplateScope(str, enum.Enum):
    SYSTEM = "system"
    WORKSPACE = "workspace"


VALID_CATEGORIES = frozenset({'research', 'analysis', 'operation', 'custom'})


class TaskTemplate:
    """A reusable task template that prefills brief fields."""

    __slots__ = (
        'id', 'name', 'description', 'category',
        'prefilled_fields', 'expected_output_type',
        'scope', 'workspace_id', 'created_at', 'updated_at',
    )

    def __init__(
        self,
        *,
        name: str,
        category: str,
        scope: TemplateScope = TemplateScope.SYSTEM,
        prefilled_fields: dict[str, Any] | None = None,
        expected_output_type: str | None = None,
        description: str | None = None,
        workspace_id: UUID | None = None,
        # Reconstitution:
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not name or not name.strip():
            raise DomainValidationError("TaskTemplate", "name must not be blank")
        if category not in VALID_CATEGORIES:
            raise DomainValidationError(
                "TaskTemplate", f"invalid category: {category}")
        scope_val = TemplateScope(scope) if isinstance(scope, str) else scope
        self._validate_scope(scope_val, workspace_id)

        now = datetime.now(timezone.utc)
        self.id = id or uuid4()
        self.name = name
        self.description = description
        self.category = category
        self.prefilled_fields = prefilled_fields or {}
        self.expected_output_type = expected_output_type
        self.scope = scope_val
        self.workspace_id = workspace_id
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    @staticmethod
    def _validate_scope(
        scope: TemplateScope, workspace_id: UUID | None,
    ) -> None:
        if scope == TemplateScope.SYSTEM and workspace_id is not None:
            raise DomainValidationError(
                "TaskTemplate",
                "system-scoped template must not have workspace_id",
            )
        if scope == TemplateScope.WORKSPACE and workspace_id is None:
            raise DomainValidationError(
                "TaskTemplate",
                "workspace-scoped template requires workspace_id",
            )
