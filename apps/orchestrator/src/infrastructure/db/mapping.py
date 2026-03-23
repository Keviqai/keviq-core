"""Mapping between SQLAlchemy rows and domain objects.

Bidirectional conversion keeping domain objects free of ORM concerns.
"""

from __future__ import annotations

from uuid import UUID

from src.domain.agent_template import AgentTemplate
from src.domain.approval_request import ApprovalDecision, ApprovalRequest, ApprovalTargetType
from src.domain.run import Run, RunStatus, TriggerType
from src.domain.step import Step, StepStatus, StepType
from src.domain.task import Task, TaskStatus, TaskType
from src.domain.task_template import TaskTemplate

from .models import ApprovalRequestRow, RunRow, StepRow, TaskRow


# ── Task ────────────────────────────────────────────────────────

def task_row_to_domain(row: TaskRow) -> Task:
    return Task(
        id=UUID(str(row.id)),
        workspace_id=UUID(str(row.workspace_id)),
        title=row.title,
        description=row.description,
        task_type=TaskType(row.task_type),
        task_status=TaskStatus(row.task_status),
        input_config=row.input_config or {},
        repo_snapshot_id=UUID(str(row.repo_snapshot_id)) if row.repo_snapshot_id else None,
        policy_id=UUID(str(row.policy_id)) if row.policy_id else None,
        parent_task_id=UUID(str(row.parent_task_id)) if row.parent_task_id else None,
        created_by_id=UUID(str(row.created_by_id)),
        created_at=row.created_at,
        updated_at=row.updated_at,
        goal=row.goal,
        context=row.context,
        constraints=row.constraints,
        desired_output=row.desired_output,
        template_id=UUID(str(row.template_id)) if row.template_id else None,
        agent_template_id=UUID(str(row.agent_template_id)) if row.agent_template_id else None,
        risk_level=row.risk_level,
    )


def task_domain_to_row(task: Task) -> dict:
    return dict(
        id=str(task.id),
        workspace_id=str(task.workspace_id),
        title=task.title,
        description=task.description,
        task_type=task.task_type.value,
        task_status=task.task_status.value,
        input_config=task.input_config,
        repo_snapshot_id=str(task.repo_snapshot_id) if task.repo_snapshot_id else None,
        policy_id=str(task.policy_id) if task.policy_id else None,
        parent_task_id=str(task.parent_task_id) if task.parent_task_id else None,
        created_by_id=str(task.created_by_id),
        created_at=task.created_at,
        updated_at=task.updated_at,
        goal=task.goal,
        context=task.context,
        constraints=task.constraints,
        desired_output=task.desired_output,
        template_id=str(task.template_id) if task.template_id else None,
        agent_template_id=str(task.agent_template_id) if task.agent_template_id else None,
        risk_level=task.risk_level,
    )


# ── Run ─────────────────────────────────────────────────────────

def run_row_to_domain(row: RunRow) -> Run:
    return Run(
        id=UUID(str(row.id)),
        task_id=UUID(str(row.task_id)),
        workspace_id=UUID(str(row.workspace_id)),
        run_status=RunStatus(row.run_status),
        trigger_type=TriggerType(row.trigger_type),
        triggered_by_id=UUID(str(row.triggered_by_id)) if row.triggered_by_id else None,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
        run_config=row.run_config or {},
        error_summary=row.error_summary,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def run_domain_to_row(run: Run) -> dict:
    return dict(
        id=str(run.id),
        task_id=str(run.task_id),
        workspace_id=str(run.workspace_id),
        run_status=run.run_status.value,
        trigger_type=run.trigger_type.value,
        triggered_by_id=str(run.triggered_by_id) if run.triggered_by_id else None,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms,
        run_config=run.run_config,
        error_summary=run.error_summary,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


# ── Step ────────────────────────────────────────────────────────

def step_row_to_domain(row: StepRow) -> Step:
    return Step(
        id=UUID(str(row.id)),
        run_id=UUID(str(row.run_id)),
        workspace_id=UUID(str(row.workspace_id)),
        step_type=StepType(row.step_type),
        step_status=StepStatus(row.step_status),
        sequence=row.sequence,
        parent_step_id=UUID(str(row.parent_step_id)) if row.parent_step_id else None,
        input_snapshot=row.input_snapshot,
        output_snapshot=row.output_snapshot,
        started_at=row.started_at,
        completed_at=row.completed_at,
        error_detail=row.error_detail,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def step_domain_to_row(step: Step) -> dict:
    return dict(
        id=str(step.id),
        run_id=str(step.run_id),
        workspace_id=str(step.workspace_id),
        step_type=step.step_type.value,
        step_status=step.step_status.value,
        sequence=step.sequence,
        parent_step_id=str(step.parent_step_id) if step.parent_step_id else None,
        input_snapshot=step.input_snapshot,
        output_snapshot=step.output_snapshot,
        started_at=step.started_at,
        completed_at=step.completed_at,
        error_detail=step.error_detail,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


# ── ApprovalRequest ───────────────────────────────────────────

def approval_request_row_to_domain(row: ApprovalRequestRow) -> ApprovalRequest:
    return ApprovalRequest(
        id=UUID(str(row.id)),
        workspace_id=UUID(str(row.workspace_id)),
        target_type=ApprovalTargetType(row.target_type),
        target_id=UUID(str(row.target_id)),
        requested_by=row.requested_by,
        reviewer_id=UUID(str(row.reviewer_id)) if row.reviewer_id else None,
        prompt=row.prompt,
        timeout_at=row.timeout_at,
        decision=ApprovalDecision(row.decision),
        decided_by_id=UUID(str(row.decided_by_id)) if row.decided_by_id else None,
        decided_at=row.decided_at,
        decision_comment=row.decision_comment,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def approval_request_domain_to_row(approval: ApprovalRequest) -> dict:
    return dict(
        id=str(approval.id),
        workspace_id=str(approval.workspace_id),
        target_type=approval.target_type.value,
        target_id=str(approval.target_id),
        requested_by=approval.requested_by,
        reviewer_id=str(approval.reviewer_id) if approval.reviewer_id else None,
        prompt=approval.prompt,
        timeout_at=approval.timeout_at,
        decision=approval.decision.value,
        decided_by_id=str(approval.decided_by_id) if approval.decided_by_id else None,
        decided_at=approval.decided_at,
        decision_comment=approval.decision_comment,
        created_at=approval.created_at,
        updated_at=approval.updated_at,
    )


# ── TaskTemplate mapping ──────────────────────────────────────


def task_template_row_to_domain(row) -> TaskTemplate:
    from src.domain.task_template import TemplateScope
    return TaskTemplate(
        id=UUID(str(row.id)),
        name=row.name,
        description=row.description,
        category=row.category,
        prefilled_fields=row.prefilled_fields or {},
        expected_output_type=row.expected_output_type,
        scope=TemplateScope(row.scope),
        workspace_id=UUID(str(row.workspace_id)) if row.workspace_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def task_template_domain_to_row(t: TaskTemplate) -> dict:
    return dict(
        id=str(t.id),
        name=t.name,
        description=t.description,
        category=t.category,
        prefilled_fields=t.prefilled_fields,
        expected_output_type=t.expected_output_type,
        scope=t.scope.value if hasattr(t.scope, 'value') else t.scope,
        workspace_id=str(t.workspace_id) if t.workspace_id else None,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ── AgentTemplate mapping ─────────────────────────────────────


def agent_template_row_to_domain(row) -> AgentTemplate:
    from src.domain.task_template import TemplateScope
    return AgentTemplate(
        id=UUID(str(row.id)),
        name=row.name,
        description=row.description,
        best_for=row.best_for,
        not_for=row.not_for,
        capabilities_manifest=row.capabilities_manifest or [],
        default_output_types=row.default_output_types or [],
        default_risk_profile=row.default_risk_profile,
        scope=TemplateScope(row.scope),
        workspace_id=UUID(str(row.workspace_id)) if row.workspace_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def agent_template_domain_to_row(a: AgentTemplate) -> dict:
    return dict(
        id=str(a.id),
        name=a.name,
        description=a.description,
        best_for=a.best_for,
        not_for=a.not_for,
        capabilities_manifest=a.capabilities_manifest,
        default_output_types=a.default_output_types,
        default_risk_profile=a.default_risk_profile,
        scope=a.scope.value if hasattr(a.scope, 'value') else a.scope,
        workspace_id=str(a.workspace_id) if a.workspace_id else None,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )
