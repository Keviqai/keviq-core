"""AgentTemplate domain entity.

Describes agent capabilities, risk profile, and suitability for task types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.domain.errors import DomainValidationError
from src.domain.task import VALID_RISK_LEVELS
from src.domain.task_template import TemplateScope


class AgentTemplate:
    """A reusable agent template with capability manifest and risk profile."""

    __slots__ = (
        'id', 'name', 'description', 'best_for', 'not_for',
        'capabilities_manifest', 'default_output_types',
        'default_risk_profile', 'scope', 'workspace_id',
        'created_at', 'updated_at',
    )

    def __init__(
        self,
        *,
        name: str,
        default_risk_profile: str = 'medium',
        capabilities_manifest: list[str] | None = None,
        default_output_types: list[str] | None = None,
        description: str | None = None,
        best_for: str | None = None,
        not_for: str | None = None,
        scope: TemplateScope = TemplateScope.SYSTEM,
        workspace_id: UUID | None = None,
        # Reconstitution:
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not name or not name.strip():
            raise DomainValidationError(
                "AgentTemplate", "name must not be blank")
        if default_risk_profile not in VALID_RISK_LEVELS:
            raise DomainValidationError(
                "AgentTemplate",
                f"invalid default_risk_profile: {default_risk_profile}",
            )
        scope_val = TemplateScope(scope) if isinstance(scope, str) else scope
        _validate_scope(scope_val, workspace_id)

        now = datetime.now(timezone.utc)
        self.id = id or uuid4()
        self.name = name
        self.description = description
        self.best_for = best_for
        self.not_for = not_for
        self.capabilities_manifest = capabilities_manifest or []
        self.default_output_types = default_output_types or []
        self.default_risk_profile = default_risk_profile
        self.scope = scope_val
        self.workspace_id = workspace_id
        self.created_at = created_at or now
        self.updated_at = updated_at or now


def _validate_scope(
    scope: TemplateScope, workspace_id: UUID | None,
) -> None:
    if scope == TemplateScope.SYSTEM and workspace_id is not None:
        raise DomainValidationError(
            "AgentTemplate",
            "system-scoped template must not have workspace_id",
        )
    if scope == TemplateScope.WORKSPACE and workspace_id is None:
        raise DomainValidationError(
            "AgentTemplate",
            "workspace-scoped template requires workspace_id",
        )
