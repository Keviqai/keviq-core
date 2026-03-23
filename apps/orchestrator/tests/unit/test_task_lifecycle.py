"""Tests for Q1 task lifecycle: launch readiness validation + handler.

Covers: _validate_launch_readiness, handle_launch_task, full draft→launch flow.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from src.application.commands import CreateTaskDraft, LaunchTask, UpdateTaskBrief
from src.application.handlers import (
    LaunchTaskResult,
    _validate_launch_readiness,
    handle_create_draft,
    handle_launch_task,
    handle_update_brief,
)
from src.domain.agent_template import AgentTemplate
from src.domain.errors import DomainError, DomainValidationError
from src.domain.task import Task, TaskStatus, TaskType

from .fake_uow import FakeUnitOfWork


# ── Factories ────────────────────────────────────────────────


def _make_launchable_draft(uow: FakeUnitOfWork, **overrides) -> Task:
    """Create a draft task with all fields required for launch."""
    agent_id = uuid4()
    defaults = dict(
        workspace_id=uuid4(),
        title="Research AI trends",
        task_type="research",
        created_by_id=uuid4(),
        goal="Analyze current AI market",
        desired_output="3-page report with sources",
        agent_template_id=agent_id,
    )
    defaults.update(overrides)
    cmd = CreateTaskDraft(**defaults)
    result = handle_create_draft(cmd, uow)
    return result.task


def _seed_agent_template(
    uow: FakeUnitOfWork, *, template_id=None, risk='low',
) -> AgentTemplate:
    """Seed an agent template into fake UoW."""
    a = AgentTemplate(
        name="Research Analyst",
        default_risk_profile=risk,
        id=template_id,
    )
    uow.agent_templates.save(a)
    return a


# ── Validate Launch Readiness ─────────────────────────────────


class TestValidateLaunchReadiness:
    def test_valid_draft_passes(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        _validate_launch_readiness(task)  # should not raise

    def test_rejects_non_draft_status(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        task.submit()  # draft → pending
        with pytest.raises(DomainValidationError, match="cannot launch from status"):
            _validate_launch_readiness(task)

    def test_rejects_missing_goal(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow, goal=None)
        with pytest.raises(DomainValidationError, match="goal"):
            _validate_launch_readiness(task)

    def test_rejects_missing_desired_output(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow, desired_output=None)
        with pytest.raises(DomainValidationError, match="desired_output"):
            _validate_launch_readiness(task)

    def test_rejects_missing_agent_template_id(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow, agent_template_id=None)
        with pytest.raises(DomainValidationError, match="agent_template_id"):
            _validate_launch_readiness(task)

    def test_rejects_multiple_missing_fields(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(
            uow, goal=None, desired_output=None, agent_template_id=None,
        )
        with pytest.raises(DomainValidationError, match="goal") as exc_info:
            _validate_launch_readiness(task)
        msg = str(exc_info.value)
        assert "desired_output" in msg
        assert "agent_template_id" in msg

    def test_whitespace_only_goal_rejected(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        task.update_brief(goal="   ")
        with pytest.raises(DomainValidationError, match="goal"):
            _validate_launch_readiness(task)

    def test_whitespace_only_desired_output_rejected(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        task.update_brief(desired_output="  ")
        with pytest.raises(DomainValidationError, match="desired_output"):
            _validate_launch_readiness(task)


# ── Handle Launch Task ────────────────────────────────────────


class TestHandleLaunchTask:
    def test_happy_path(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        result = handle_launch_task(cmd, uow)
        assert result.task.task_status == TaskStatus.PENDING
        assert uow.committed

    def test_auto_sets_risk_from_agent_template(self):
        uow = FakeUnitOfWork()
        agent_id = uuid4()
        _seed_agent_template(uow, template_id=agent_id, risk='high')
        task = _make_launchable_draft(
            uow, agent_template_id=agent_id, risk_level=None,
        )
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        result = handle_launch_task(cmd, uow)
        assert result.task.risk_level == 'high'

    def test_keeps_existing_risk_level(self):
        uow = FakeUnitOfWork()
        agent_id = uuid4()
        _seed_agent_template(uow, template_id=agent_id, risk='high')
        task = _make_launchable_draft(
            uow, agent_template_id=agent_id, risk_level='low',
        )
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        result = handle_launch_task(cmd, uow)
        assert result.task.risk_level == 'low'  # not overwritten

    def test_task_not_found_raises(self):
        uow = FakeUnitOfWork()
        cmd = LaunchTask(task_id=uuid4(), launched_by_id=uuid4())
        with pytest.raises(DomainError, match="not found"):
            handle_launch_task(cmd, uow)

    def test_non_draft_raises(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        task.submit()
        uow.tasks.save(task)
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        with pytest.raises(DomainValidationError, match="cannot launch"):
            handle_launch_task(cmd, uow)

    def test_missing_fields_raises(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow, goal=None)
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        with pytest.raises(DomainValidationError, match="goal"):
            handle_launch_task(cmd, uow)

    def test_writes_submitted_event(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(uow)
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        handle_launch_task(cmd, uow)
        assert len(uow.outbox.events) == 1
        evt = uow.outbox.events[0]
        assert evt.event_type == "task.submitted"


# ── Full Draft → Update → Launch Flow ─────────────────────────


class TestLaunchWithExistingBrief:
    def test_create_draft_then_update_then_launch(self):
        uow = FakeUnitOfWork()
        agent_id = uuid4()
        _seed_agent_template(uow, template_id=agent_id, risk='medium')

        # Step 1: Create draft (minimal)
        draft_cmd = CreateTaskDraft(
            workspace_id=uuid4(),
            title="Draft task",
            task_type="research",
            created_by_id=uuid4(),
        )
        draft_result = handle_create_draft(draft_cmd, uow)
        task = draft_result.task
        assert task.task_status == TaskStatus.DRAFT

        # Step 2: Update brief
        update_cmd = UpdateTaskBrief(
            task_id=task.id,
            updates={
                "goal": "Research competitors",
                "desired_output": "Summary report",
                "agent_template_id": agent_id,
            },
        )
        handle_update_brief(update_cmd, uow)

        # Step 3: Launch
        launch_cmd = LaunchTask(
            task_id=task.id, launched_by_id=uuid4(),
        )
        result = handle_launch_task(launch_cmd, uow)
        assert result.task.task_status == TaskStatus.PENDING
        assert result.task.risk_level == 'medium'

    def test_launch_preserves_all_brief_fields(self):
        uow = FakeUnitOfWork()
        task = _make_launchable_draft(
            uow,
            goal="Goal text",
            context="Context text",
            constraints="Constraint text",
            desired_output="Output text",
        )
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        result = handle_launch_task(cmd, uow)
        assert result.task.goal == "Goal text"
        assert result.task.context == "Context text"
        assert result.task.constraints == "Constraint text"
        assert result.task.desired_output == "Output text"

    def test_launch_with_template_id(self):
        uow = FakeUnitOfWork()
        tid = uuid4()
        task = _make_launchable_draft(uow, template_id=tid)
        cmd = LaunchTask(task_id=task.id, launched_by_id=uuid4())
        result = handle_launch_task(cmd, uow)
        assert result.task.template_id == tid
