"""Command DTOs for orchestrator application layer.

Pure data — no logic, no infra imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SubmitTask:
    workspace_id: UUID
    title: str
    task_type: str
    created_by_id: UUID
    description: str | None = None
    input_config: dict[str, Any] | None = None
    repo_snapshot_id: UUID | None = None
    policy_id: UUID | None = None
    parent_task_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateTaskDraft:
    """Create a task in DRAFT status (no auto-submit)."""
    workspace_id: UUID
    title: str
    task_type: str
    created_by_id: UUID
    description: str | None = None
    goal: str | None = None
    context: str | None = None
    constraints: str | None = None
    desired_output: str | None = None
    template_id: UUID | None = None
    agent_template_id: UUID | None = None
    risk_level: str | None = None
    input_config: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class UpdateTaskBrief:
    """Update brief fields on a draft task."""
    task_id: UUID
    updates: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LaunchTask:
    """Validate readiness and launch a draft task."""
    task_id: UUID
    launched_by_id: UUID


@dataclass(frozen=True, slots=True)
class CancelTask:
    task_id: UUID
    cancelled_by_id: UUID


@dataclass(frozen=True, slots=True)
class RetryTask:
    task_id: UUID
    retried_by_id: UUID
