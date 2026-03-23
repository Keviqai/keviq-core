"""Tests for Q1 Task Brief Schema — domain, handlers, and serialization.

Covers: Task.update_brief(), handle_create_draft(), handle_update_brief(),
task_to_dict() with brief fields.

Incident: INC-001 — these tests were missing from original S1 delivery.
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from src.application.commands import CreateTaskDraft, UpdateTaskBrief
from src.application.handlers import handle_create_draft, handle_update_brief
from src.application.queries import task_to_dict
from src.domain.errors import DomainError, DomainValidationError
from src.domain.task import Task, TaskStatus, TaskType

from .fake_uow import FakeUnitOfWork


# ── Factories ────────────────────────────────────────────────

def _make_draft(**overrides) -> Task:
    defaults = dict(
        workspace_id=uuid4(),
        title="Research market trends",
        task_type=TaskType.RESEARCH,
        created_by_id=uuid4(),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_draft_cmd(**overrides) -> CreateTaskDraft:
    defaults = dict(
        workspace_id=uuid4(),
        title="Draft task",
        task_type="research",
        created_by_id=uuid4(),
    )
    defaults.update(overrides)
    return CreateTaskDraft(**defaults)


# ── Domain: Task.__init__ with brief fields ──────────────────


class TestTaskInitBriefFields:
    def test_creates_with_all_brief_fields(self):
        t = _make_draft(
            goal="Analyze competitors",
            context="Q1 planning",
            constraints="Public data only",
            desired_output="3-page report",
            risk_level="low",
        )
        assert t.goal == "Analyze competitors"
        assert t.context == "Q1 planning"
        assert t.constraints == "Public data only"
        assert t.desired_output == "3-page report"
        assert t.risk_level == "low"

    def test_brief_fields_default_to_none(self):
        t = _make_draft()
        assert t.goal is None
        assert t.context is None
        assert t.constraints is None
        assert t.desired_output is None
        assert t.template_id is None
        assert t.agent_template_id is None
        assert t.risk_level is None

    def test_rejects_invalid_risk_level(self):
        with pytest.raises(DomainValidationError, match="invalid risk_level"):
            _make_draft(risk_level="critical")

    def test_accepts_valid_risk_levels(self):
        for level in ("low", "medium", "high"):
            t = _make_draft(risk_level=level)
            assert t.risk_level == level

    def test_stores_template_ids(self):
        tid = uuid4()
        aid = uuid4()
        t = _make_draft(template_id=tid, agent_template_id=aid)
        assert t.template_id == tid
        assert t.agent_template_id == aid


# ── Domain: Task.update_brief() ──────────────────────────────


class TestUpdateBrief:
    def test_updates_goal(self):
        t = _make_draft()
        t.update_brief(goal="New goal")
        assert t.goal == "New goal"

    def test_updates_multiple_fields(self):
        t = _make_draft()
        t.update_brief(
            goal="Goal", context="Context",
            constraints="None", desired_output="Report",
        )
        assert t.goal == "Goal"
        assert t.context == "Context"

    def test_rejects_update_on_non_draft(self):
        t = _make_draft()
        t.submit()  # draft → pending
        with pytest.raises(DomainValidationError, match="cannot update brief"):
            t.update_brief(goal="New goal")

    def test_rejects_disallowed_field(self):
        t = _make_draft()
        with pytest.raises(DomainValidationError, match="cannot update field"):
            t.update_brief(workspace_id=uuid4())

    def test_rejects_blank_title(self):
        t = _make_draft()
        with pytest.raises(DomainValidationError, match="title must not be blank"):
            t.update_brief(title="   ")

    def test_rejects_invalid_risk_level(self):
        t = _make_draft()
        with pytest.raises(DomainValidationError, match="invalid risk_level"):
            t.update_brief(risk_level="extreme")

    def test_updates_timestamp(self):
        t = _make_draft()
        old_updated = t.updated_at
        t.update_brief(goal="Changed")
        assert t.updated_at >= old_updated

    def test_updates_template_id(self):
        t = _make_draft()
        tid = uuid4()
        t.update_brief(template_id=tid)
        assert t.template_id == tid


# ── Handlers: handle_create_draft ─────────────────────────────


class TestHandleCreateDraft:
    def test_creates_draft_task(self):
        uow = FakeUnitOfWork()
        cmd = _make_draft_cmd(goal="Research AI trends")
        result = handle_create_draft(cmd, uow)
        assert result.task.task_status == TaskStatus.DRAFT
        assert result.task.goal == "Research AI trends"
        assert uow.committed

    def test_stays_in_draft(self):
        uow = FakeUnitOfWork()
        cmd = _make_draft_cmd()
        result = handle_create_draft(cmd, uow)
        assert result.task.task_status == TaskStatus.DRAFT

    def test_persists_task(self):
        uow = FakeUnitOfWork()
        cmd = _make_draft_cmd()
        result = handle_create_draft(cmd, uow)
        saved = uow.tasks.get_by_id(result.task.id)
        assert saved is not None
        assert saved.title == cmd.title

    def test_with_all_brief_fields(self):
        uow = FakeUnitOfWork()
        tid = uuid4()
        aid = uuid4()
        cmd = _make_draft_cmd(
            goal="Goal", context="Context",
            constraints="None", desired_output="Report",
            template_id=tid, agent_template_id=aid,
            risk_level="medium",
        )
        result = handle_create_draft(cmd, uow)
        assert result.task.template_id == tid
        assert result.task.risk_level == "medium"


# ── Handlers: handle_update_brief ─────────────────────────────


class TestHandleUpdateBrief:
    def _setup_draft(self) -> tuple[FakeUnitOfWork, Task]:
        uow = FakeUnitOfWork()
        cmd = _make_draft_cmd()
        result = handle_create_draft(cmd, uow)
        return uow, result.task

    def test_updates_brief_fields(self):
        uow, task = self._setup_draft()
        cmd = UpdateTaskBrief(task_id=task.id, updates={"goal": "Updated"})
        result = handle_update_brief(cmd, uow)
        assert result.task.goal == "Updated"

    def test_task_not_found_raises(self):
        uow = FakeUnitOfWork()
        cmd = UpdateTaskBrief(task_id=uuid4(), updates={"goal": "X"})
        with pytest.raises(DomainError, match="not found"):
            handle_update_brief(cmd, uow)

    def test_non_draft_raises(self):
        uow, task = self._setup_draft()
        task.submit()  # draft → pending
        uow.tasks.save(task)
        cmd = UpdateTaskBrief(task_id=task.id, updates={"goal": "X"})
        with pytest.raises(DomainValidationError, match="cannot update brief"):
            handle_update_brief(cmd, uow)


# ── Queries: task_to_dict with brief fields ───────────────────


class TestTaskToDictBrief:
    def test_includes_brief_fields(self):
        t = _make_draft(
            goal="Goal", context="Context",
            constraints="Limit", desired_output="Report",
            risk_level="high",
        )
        d = task_to_dict(t)
        assert d["goal"] == "Goal"
        assert d["context"] == "Context"
        assert d["constraints"] == "Limit"
        assert d["desired_output"] == "Report"
        assert d["risk_level"] == "high"

    def test_null_brief_fields_in_old_tasks(self):
        t = _make_draft()
        d = task_to_dict(t)
        assert d["goal"] is None
        assert d["context"] is None
        assert d["risk_level"] is None
        assert "template_id" not in d
        assert "agent_template_id" not in d

    def test_includes_template_ids_when_set(self):
        tid = uuid4()
        aid = uuid4()
        t = _make_draft(template_id=tid, agent_template_id=aid)
        d = task_to_dict(t)
        assert d["template_id"] == str(tid)
        assert d["agent_template_id"] == str(aid)
