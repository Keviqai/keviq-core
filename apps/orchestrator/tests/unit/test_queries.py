"""Unit tests for query handlers.

Uses FakeUnitOfWork — no database needed.
"""

import pytest
from uuid import uuid4

from src.application.queries import (
    get_run,
    get_run_steps,
    get_task,
    get_task_with_latest_run,
    run_to_dict,
    step_to_dict,
    task_to_dict,
)
from src.domain.errors import DomainError
from src.domain.run import Run, TriggerType
from src.domain.step import Step, StepType
from src.domain.task import Task, TaskType

from .fake_uow import FakeUnitOfWork


# ── Helpers ──────────────────────────────────────────────────────

def _make_task(**overrides) -> Task:
    defaults = dict(
        workspace_id=uuid4(),
        title="Test task",
        task_type=TaskType.CODING,
        created_by_id=uuid4(),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_run(task: Task, **overrides) -> Run:
    defaults = dict(
        task_id=task.id,
        workspace_id=task.workspace_id,
        trigger_type=TriggerType.MANUAL,
    )
    defaults.update(overrides)
    return Run(**defaults)


def _make_step(run: Run, sequence: int = 1, **overrides) -> Step:
    defaults = dict(
        run_id=run.id,
        workspace_id=run.workspace_id,
        sequence=sequence,
        step_type=StepType.AGENT_INVOCATION,
    )
    defaults.update(overrides)
    return Step(**defaults)


# ── get_task ──────────────────────────────────────────────────────

class TestGetTask:
    def test_found(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)

        result = get_task(task.id, uow)
        assert result.id == task.id

    def test_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_task(uuid4(), uow)


# ── get_run ───────────────────────────────────────────────────────

class TestGetRun:
    def test_found(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)
        run = _make_run(task)
        uow.runs.save(run)

        result = get_run(run.id, uow)
        assert result.id == run.id

    def test_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_run(uuid4(), uow)


# ── get_task_with_latest_run ──────────────────────────────────────

class TestGetTaskWithLatestRun:
    def test_task_with_no_runs(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)

        t, r = get_task_with_latest_run(task.id, uow)
        assert t.id == task.id
        assert r is None

    def test_task_with_run(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)
        run = _make_run(task)
        uow.runs.save(run)

        t, r = get_task_with_latest_run(task.id, uow)
        assert t.id == task.id
        assert r is not None
        assert r.id == run.id

    def test_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_task_with_latest_run(uuid4(), uow)


# ── get_run_steps ─────────────────────────────────────────────────

class TestGetRunSteps:
    def test_run_with_steps(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)
        run = _make_run(task)
        uow.runs.save(run)
        s1 = _make_step(run, sequence=1)
        s2 = _make_step(run, sequence=2)
        uow.steps.save(s1)
        uow.steps.save(s2)

        r, steps = get_run_steps(run.id, uow)
        assert r.id == run.id
        assert len(steps) == 2
        assert steps[0].sequence <= steps[1].sequence

    def test_run_with_no_steps(self):
        uow = FakeUnitOfWork()
        task = _make_task()
        uow.tasks.save(task)
        run = _make_run(task)
        uow.runs.save(run)

        r, steps = get_run_steps(run.id, uow)
        assert r.id == run.id
        assert steps == []

    def test_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_run_steps(uuid4(), uow)


# ── Serialization helpers ─────────────────────────────────────────

class TestTaskToDict:
    def test_basic_fields(self):
        task = _make_task()
        d = task_to_dict(task)

        assert d["task_id"] == str(task.id)
        assert d["workspace_id"] == str(task.workspace_id)
        assert d["title"] == "Test task"
        assert d["task_type"] == "coding"
        assert d["task_status"] == "draft"
        assert "created_at" in d
        assert "updated_at" in d

    def test_with_latest_run(self):
        task = _make_task()
        run = _make_run(task)
        d = task_to_dict(task, latest_run=run)

        assert d["latest_run_id"] == str(run.id)

    def test_without_latest_run(self):
        task = _make_task()
        d = task_to_dict(task)

        assert "latest_run_id" not in d

    def test_optional_fields_present(self):
        task = _make_task(
            description="desc",
            repo_snapshot_id=uuid4(),
            policy_id=uuid4(),
            parent_task_id=uuid4(),
        )
        d = task_to_dict(task)

        assert d.get("repo_snapshot_id") is not None
        assert d.get("policy_id") is not None
        assert d.get("parent_task_id") is not None


class TestRunToDict:
    def test_basic_fields(self):
        task = _make_task()
        run = _make_run(task)
        d = run_to_dict(run)

        assert d["run_id"] == str(run.id)
        assert d["task_id"] == str(task.id)
        assert d["run_status"] == "queued"
        assert d["trigger_type"] == "manual"
        assert "created_at" in d


class TestStepToDict:
    def test_basic_fields(self):
        task = _make_task()
        run = _make_run(task)
        step = _make_step(run, sequence=3)
        d = step_to_dict(step)

        assert d["step_id"] == str(step.id)
        assert d["run_id"] == str(run.id)
        assert d["sequence"] == 3
        assert d["step_type"] == "agent_invocation"
        assert d["step_status"] == "pending"
