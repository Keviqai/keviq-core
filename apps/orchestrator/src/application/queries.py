"""Query handlers for orchestrator.

Read-only operations — never mutate state.
Each handler uses repository abstractions (no raw SQL).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.domain.errors import DomainError
from src.domain.run import Run
from src.domain.step import Step
from src.domain.task import Task

from .ports import UnitOfWork


def list_tasks_by_workspace(
    workspace_id: UUID, uow: UnitOfWork, *, limit: int = 50, offset: int = 0,
) -> list[tuple[Task, Run | None]]:
    """List tasks in a workspace with their latest run."""
    with uow:
        tasks = uow.tasks.list_by_workspace(workspace_id, limit=limit, offset=offset)
        result = []
        for task in tasks:
            latest_run = uow.runs.get_latest_by_task(task.id)
            result.append((task, latest_run))
        return result


def get_task(task_id: UUID, uow: UnitOfWork) -> Task:
    """Get a task by ID. Raises DomainError if not found."""
    with uow:
        task = uow.tasks.get_by_id(task_id)
        if task is None:
            raise DomainError(f"Task {task_id} not found")
        return task


def get_run(run_id: UUID, uow: UnitOfWork) -> Run:
    """Get a run by ID. Raises DomainError if not found."""
    with uow:
        run = uow.runs.get_by_id(run_id)
        if run is None:
            raise DomainError(f"Run {run_id} not found")
        return run


def get_task_with_latest_run(
    task_id: UUID, uow: UnitOfWork
) -> tuple[Task, Run | None]:
    """Get a task and its latest run (if any)."""
    with uow:
        task = uow.tasks.get_by_id(task_id)
        if task is None:
            raise DomainError(f"Task {task_id} not found")
        latest_run = uow.runs.get_latest_by_task(task_id)
        return task, latest_run


def get_run_steps(run_id: UUID, uow: UnitOfWork) -> tuple[Run, list[Step]]:
    """Get a run and its steps ordered by sequence."""
    with uow:
        run = uow.runs.get_by_id(run_id)
        if run is None:
            raise DomainError(f"Run {run_id} not found")
        steps = uow.steps.list_by_run(run_id)
        return run, steps


# ── Serialization helpers ──────────────────────────────────────

def task_to_dict(task: Task, latest_run: Run | None = None) -> dict[str, Any]:
    """Serialize a Task to a dict suitable for JSON response."""
    result: dict[str, Any] = {
        "task_id": str(task.id),
        "workspace_id": str(task.workspace_id),
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type.value,
        "task_status": task.task_status.value,
        "input_config": task.input_config,
        "created_by_id": str(task.created_by_id),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        # Q1 brief fields
        "goal": task.goal,
        "context": task.context,
        "constraints": task.constraints,
        "desired_output": task.desired_output,
        "risk_level": task.risk_level,
    }
    if task.template_id:
        result["template_id"] = str(task.template_id)
    if task.agent_template_id:
        result["agent_template_id"] = str(task.agent_template_id)
    if task.repo_snapshot_id:
        result["repo_snapshot_id"] = str(task.repo_snapshot_id)
    if task.policy_id:
        result["policy_id"] = str(task.policy_id)
    if task.parent_task_id:
        result["parent_task_id"] = str(task.parent_task_id)
    if latest_run:
        result["latest_run_id"] = str(latest_run.id)
    return result


def run_to_dict(run: Run) -> dict[str, Any]:
    """Serialize a Run to a dict suitable for JSON response."""
    result: dict[str, Any] = {
        "run_id": str(run.id),
        "task_id": str(run.task_id),
        "workspace_id": str(run.workspace_id),
        "run_status": run.run_status.value,
        "trigger_type": run.trigger_type.value,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_ms": run.duration_ms,
        "created_at": run.created_at.isoformat(),
    }
    if run.error_summary:
        result["error_summary"] = run.error_summary
    return result


def step_to_dict(step: Step) -> dict[str, Any]:
    """Serialize a Step to a dict suitable for JSON response."""
    result: dict[str, Any] = {
        "step_id": str(step.id),
        "run_id": str(step.run_id),
        "sequence": step.sequence,
        "step_type": step.step_type.value,
        "step_status": step.step_status.value,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
    }
    if step.error_detail:
        result["error_detail"] = step.error_detail
    if step.output_snapshot:
        result["output_snapshot"] = step.output_snapshot
    return result
