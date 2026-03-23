"""Query functions and serialization for templates."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.application.ports import UnitOfWork
from src.domain.agent_template import AgentTemplate
from src.domain.errors import DomainError
from src.domain.task_template import TaskTemplate


# ── Task Template queries ─────────────────────────────────────


def list_system_task_templates(
    uow: UnitOfWork,
    *,
    category: str | None = None,
) -> list[TaskTemplate]:
    """List all system-scoped task templates."""
    with uow:
        return uow.task_templates.list_system(category=category)


def get_task_template(
    template_id: UUID, uow: UnitOfWork,
) -> TaskTemplate:
    """Get a task template by ID. Raises DomainError if not found."""
    with uow:
        t = uow.task_templates.get_by_id(template_id)
        if t is None:
            raise DomainError(f"TaskTemplate {template_id} not found")
        return t


# ── Agent Template queries ────────────────────────────────────


def list_system_agent_templates(uow: UnitOfWork) -> list[AgentTemplate]:
    """List all system-scoped agent templates."""
    with uow:
        return uow.agent_templates.list_system()


def get_agent_template(
    template_id: UUID, uow: UnitOfWork,
) -> AgentTemplate:
    """Get an agent template by ID. Raises DomainError if not found."""
    with uow:
        a = uow.agent_templates.get_by_id(template_id)
        if a is None:
            raise DomainError(f"AgentTemplate {template_id} not found")
        return a


# ── Serialization ─────────────────────────────────────────────


def task_template_to_dict(t: TaskTemplate) -> dict[str, Any]:
    """Serialize a TaskTemplate for JSON response."""
    result: dict[str, Any] = {
        "template_id": str(t.id),
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "prefilled_fields": t.prefilled_fields,
        "expected_output_type": t.expected_output_type,
        "scope": t.scope.value if hasattr(t.scope, 'value') else t.scope,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if t.workspace_id:
        result["workspace_id"] = str(t.workspace_id)
    return result


def agent_template_to_dict(a: AgentTemplate) -> dict[str, Any]:
    """Serialize an AgentTemplate for JSON response."""
    result: dict[str, Any] = {
        "template_id": str(a.id),
        "name": a.name,
        "description": a.description,
        "best_for": a.best_for,
        "not_for": a.not_for,
        "capabilities_manifest": a.capabilities_manifest,
        "default_output_types": a.default_output_types,
        "default_risk_profile": a.default_risk_profile,
        "scope": a.scope.value if hasattr(a.scope, 'value') else a.scope,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }
    if a.workspace_id:
        result["workspace_id"] = str(a.workspace_id)
    return result
