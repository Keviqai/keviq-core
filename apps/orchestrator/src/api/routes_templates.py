"""Template API routes — list and get system/workspace templates.

Read-only in Q1. Write endpoints deferred to later Q1 or Q2.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.internal_auth import require_service

from src.application.bootstrap import get_uow
from src.application.template_queries import (
    agent_template_to_dict,
    get_agent_template,
    get_task_template,
    list_system_agent_templates,
    list_system_task_templates,
    task_template_to_dict,
)
from src.domain.errors import DomainError

router = APIRouter()


# ── Task Templates ────────────────────────────────────────────


@router.get("/internal/v1/task-templates")
def list_task_templates_endpoint(
    category: str | None = None,
    _claims=Depends(require_service("api-gateway")),
):
    """List system task templates. Optional category filter."""
    uow = get_uow()
    templates = list_system_task_templates(uow, category=category)
    items = [task_template_to_dict(t) for t in templates]
    return {"items": items, "count": len(items)}


@router.get("/internal/v1/task-templates/{template_id}")
def get_task_template_endpoint(
    template_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """Get a single task template by ID."""
    try:
        tid = UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template_id format",
        )

    uow = get_uow()
    try:
        template = get_task_template(tid, uow)
    except DomainError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task template not found",
        )
    return task_template_to_dict(template)


# ── Agent Templates ───────────────────────────────────────────


@router.get("/internal/v1/agent-templates")
def list_agent_templates_endpoint(
    _claims=Depends(require_service("api-gateway")),
):
    """List system agent templates."""
    uow = get_uow()
    templates = list_system_agent_templates(uow)
    items = [agent_template_to_dict(a) for a in templates]
    return {"items": items, "count": len(items)}


@router.get("/internal/v1/agent-templates/{template_id}")
def get_agent_template_endpoint(
    template_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """Get a single agent template by ID."""
    try:
        tid = UUID(template_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template_id format",
        )

    uow = get_uow()
    try:
        template = get_agent_template(tid, uow)
    except DomainError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent template not found",
        )
    return agent_template_to_dict(template)
