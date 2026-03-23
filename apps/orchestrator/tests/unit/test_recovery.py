"""Unit tests for orchestrator recovery sweep.

Covers stuck runs, stuck steps, orphaned tasks,
idempotency guards, and outbox event emission.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.recovery import (
    STUCK_COMPLETING_MINUTES,
    STUCK_PREPARING_MINUTES,
    STUCK_RUNNING_MINUTES,
    STUCK_STEP_RUNNING_MINUTES,
    _recover_single_run,
    _recover_single_step,
    _recover_single_task,
    recover_stuck_entities,
)
from src.domain.run import Run, RunStatus, TriggerType
from src.domain.step import Step, StepStatus, StepType
from src.domain.task import Task, TaskStatus, TaskType

from .fake_uow import FakeUnitOfWork


# ── Helpers ────────────────────────────────────────────────────


def _old(minutes: int) -> datetime:
    """Return a timestamp `minutes` in the past."""
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def _make_run(
    uow: FakeUnitOfWork,
    *,
    task_id: UUID | None = None,
    workspace_id: UUID | None = None,
    status: RunStatus = RunStatus.RUNNING,
    created_minutes_ago: int = 60,
) -> Run:
    """Create a run in the given status, backdated to simulate being stuck."""
    ws = workspace_id or uuid4()
    tid = task_id or uuid4()
    old_time = _old(created_minutes_ago)

    run = Run(
        task_id=tid,
        workspace_id=ws,
        trigger_type=TriggerType.MANUAL,
        created_at=old_time,
    )

    # Drive through state machine to reach target status
    if status in (RunStatus.PREPARING, RunStatus.RUNNING, RunStatus.COMPLETING):
        run.prepare()
    if status in (RunStatus.RUNNING, RunStatus.COMPLETING):
        run.start()
    if status == RunStatus.COMPLETING:
        run.begin_completing()

    # Backdate updated_at so the run appears stuck past the threshold
    run.updated_at = old_time

    uow.runs.save(run)
    return run


def _make_step(
    uow: FakeUnitOfWork,
    *,
    run_id: UUID | None = None,
    workspace_id: UUID | None = None,
    status: StepStatus = StepStatus.RUNNING,
    created_minutes_ago: int = 60,
) -> Step:
    """Create a step in the given status, backdated."""
    ws = workspace_id or uuid4()
    rid = run_id or uuid4()
    old_time = _old(created_minutes_ago)

    step = Step(
        run_id=rid,
        workspace_id=ws,
        sequence=1,
        step_type=StepType.AGENT_INVOCATION,
        created_at=old_time,
    )

    if status == StepStatus.RUNNING:
        step.start()

    # Backdate updated_at so the step appears stuck past the threshold
    step.updated_at = old_time

    uow.steps.save(step)
    return step


def _make_task(
    uow: FakeUnitOfWork,
    *,
    status: TaskStatus = TaskStatus.RUNNING,
    workspace_id: UUID | None = None,
) -> Task:
    """Create a task in the given status."""
    ws = workspace_id or uuid4()
    task = Task(
        workspace_id=ws,
        title="Test task",
        task_type=TaskType.CODING,
        created_by_id=uuid4(),
    )
    task.submit()
    if status in (TaskStatus.RUNNING,):
        task.start()
    uow.tasks.save(task)
    return task


# ── Stuck run recovery ─────────────────────────────────────────


class TestRecoverStuckRuns:
    def test_preparing_run_marked_failed(self):
        uow = FakeUnitOfWork()
        run = _make_run(uow, status=RunStatus.PREPARING, created_minutes_ago=10)

        results = recover_stuck_entities(uow)

        recovered = [r for r in results if r.id == str(run.id)]
        assert len(recovered) == 1
        assert recovered[0].recovery_action == "marked_failed"
        assert recovered[0].previous_status == "preparing"
        assert recovered[0].success is True

        reloaded = uow.runs.get_by_id(run.id)
        assert reloaded.run_status == RunStatus.FAILED

    def test_running_run_marked_failed(self):
        uow = FakeUnitOfWork()
        run = _make_run(uow, status=RunStatus.RUNNING, created_minutes_ago=60)

        results = recover_stuck_entities(uow)

        recovered = [r for r in results if r.id == str(run.id)]
        assert len(recovered) == 1
        assert recovered[0].recovery_action == "marked_failed"

    def test_completing_run_force_completed(self):
        uow = FakeUnitOfWork()
        run = _make_run(uow, status=RunStatus.COMPLETING, created_minutes_ago=10)

        results = recover_stuck_entities(uow)

        recovered = [r for r in results if r.id == str(run.id)]
        assert len(recovered) == 1
        assert recovered[0].recovery_action == "force_completed"

        reloaded = uow.runs.get_by_id(run.id)
        assert reloaded.run_status == RunStatus.COMPLETED

    def test_recent_run_not_recovered(self):
        """Runs within threshold should not be touched."""
        uow = FakeUnitOfWork()
        _make_run(uow, status=RunStatus.PREPARING, created_minutes_ago=2)

        results = recover_stuck_entities(uow)

        assert len(results) == 0

    def test_running_run_within_threshold_not_recovered(self):
        """RUNNING threshold is 30 min — 10 min old RUNNING run is fine."""
        uow = FakeUnitOfWork()
        _make_run(uow, status=RunStatus.RUNNING, created_minutes_ago=10)

        results = recover_stuck_entities(uow)

        assert len(results) == 0

    def test_active_steps_cancelled_on_run_recovery(self):
        uow = FakeUnitOfWork()
        ws = uuid4()
        run = _make_run(uow, status=RunStatus.RUNNING, workspace_id=ws,
                        created_minutes_ago=60)
        step = _make_step(uow, run_id=run.id, workspace_id=ws,
                          created_minutes_ago=60)

        recover_stuck_entities(uow)

        reloaded_step = uow.steps.get_by_id(step.id)
        assert reloaded_step.step_status == StepStatus.CANCELLED

    def test_run_recovered_event_emitted(self):
        uow = FakeUnitOfWork()
        run = _make_run(uow, status=RunStatus.PREPARING, created_minutes_ago=10)

        recover_stuck_entities(uow)

        run_events = [e for e in uow.outbox.events
                      if e.event_type == "run.recovered"]
        assert len(run_events) == 1
        assert run_events[0].payload["run_id"] == str(run.id)
        assert run_events[0].payload["previous_status"] == "preparing"
        assert run_events[0].payload["recovery_action"] == "marked_failed"


# ── Idempotency guards ────────────────────────────────────────


class TestRecoveryIdempotency:
    def test_skips_already_terminal_run(self):
        """If run became terminal between list_stuck and recovery, skip it."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        tid = uuid4()
        run = _make_run(uow, task_id=tid, workspace_id=ws,
                        status=RunStatus.RUNNING, created_minutes_ago=60)
        # Simulate: run completes between list and recover
        run.begin_completing()
        run.complete()
        uow.runs.save(run)

        result = _recover_single_run(
            run.id, tid, ws, RunStatus.RUNNING, uow,
        )

        assert result.recovery_action == "skipped_already_terminal"
        assert result.success is True

    def test_skips_run_no_longer_stuck(self):
        """If run left stuck status between list and recovery, skip it."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        tid = uuid4()
        # Create a RUNNING run, then move to WAITING_APPROVAL
        run = _make_run(uow, task_id=tid, workspace_id=ws,
                        status=RunStatus.RUNNING, created_minutes_ago=60)
        run.request_approval()
        uow.runs.save(run)

        result = _recover_single_run(
            run.id, tid, ws, RunStatus.RUNNING, uow,
        )

        assert result.recovery_action == "skipped_no_longer_stuck"
        assert result.success is True

    def test_double_sweep_is_stable(self):
        """Running sweep twice produces same results (idempotent)."""
        uow = FakeUnitOfWork()
        _make_run(uow, status=RunStatus.PREPARING, created_minutes_ago=10)

        results1 = recover_stuck_entities(uow)
        results2 = recover_stuck_entities(uow)

        assert len(results1) == 1
        assert len(results2) == 0  # Already recovered


# ── Stuck step recovery ──────────────────────────────────────


class TestRecoverStuckSteps:
    def test_running_step_marked_failed(self):
        uow = FakeUnitOfWork()
        step = _make_step(uow, status=StepStatus.RUNNING, created_minutes_ago=60)

        results = recover_stuck_entities(uow)

        step_results = [r for r in results if r.entity == "step"]
        assert len(step_results) == 1
        assert step_results[0].recovery_action == "marked_failed"

        reloaded = uow.steps.get_by_id(step.id)
        assert reloaded.step_status == StepStatus.FAILED
        assert reloaded.error_detail["code"] == "RECOVERY_SWEEP"

    def test_recent_step_not_recovered(self):
        uow = FakeUnitOfWork()
        _make_step(uow, status=StepStatus.RUNNING, created_minutes_ago=10)

        results = recover_stuck_entities(uow)

        step_results = [r for r in results if r.entity == "step"]
        assert len(step_results) == 0

    def test_step_recovered_event_emitted(self):
        uow = FakeUnitOfWork()
        ws = uuid4()
        tid = uuid4()
        # Create a completed run so the step's run_id resolves for task_id lookup
        run = Run(task_id=tid, workspace_id=ws)
        run.prepare()
        run.start()
        run.begin_completing()
        run.complete()
        uow.runs.save(run)

        step = _make_step(uow, run_id=run.id, workspace_id=ws,
                          created_minutes_ago=60)

        recover_stuck_entities(uow)

        step_events = [e for e in uow.outbox.events
                       if e.event_type == "step.recovered"]
        assert len(step_events) == 1
        assert step_events[0].payload["step_id"] == str(step.id)

    def test_skips_already_terminal_step(self):
        uow = FakeUnitOfWork()
        ws = uuid4()
        rid = uuid4()
        step = _make_step(uow, run_id=rid, workspace_id=ws,
                          status=StepStatus.RUNNING, created_minutes_ago=60)
        # Simulate: step completed between list and recover
        step.complete(output_snapshot={"result": "ok"})
        uow.steps.save(step)

        result = _recover_single_step(step.id, rid, ws, uow)

        assert result.recovery_action == "skipped_already_terminal"


# ── Orphaned task recovery ───────────────────────────────────


class TestRecoverOrphanedTasks:
    def test_running_task_with_completed_latest_run(self):
        """Task RUNNING, latest run COMPLETED → task should complete."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        task = _make_task(uow, status=TaskStatus.RUNNING, workspace_id=ws)

        # Create a completed run
        run = Run(task_id=task.id, workspace_id=ws)
        run.prepare()
        run.start()
        run.begin_completing()
        run.complete()
        uow.runs.save(run)

        results = recover_stuck_entities(uow)

        task_results = [r for r in results if r.entity == "task"]
        assert len(task_results) == 1
        assert task_results[0].recovery_action == "marked_completed"

        reloaded = uow.tasks.get_by_id(task.id)
        assert reloaded.task_status == TaskStatus.COMPLETED

    def test_running_task_with_failed_latest_run(self):
        """Task RUNNING, latest run FAILED → conservative: fail the task."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        task = _make_task(uow, status=TaskStatus.RUNNING, workspace_id=ws)

        run = Run(task_id=task.id, workspace_id=ws)
        run.prepare()
        run.fail(error_summary="Something broke")
        uow.runs.save(run)

        results = recover_stuck_entities(uow)

        task_results = [r for r in results if r.entity == "task"]
        assert len(task_results) == 1
        assert task_results[0].recovery_action == "marked_failed"

        reloaded = uow.tasks.get_by_id(task.id)
        assert reloaded.task_status == TaskStatus.FAILED

    def test_running_task_with_no_runs(self):
        """Task RUNNING with zero runs → orphaned, fail it."""
        uow = FakeUnitOfWork()
        task = _make_task(uow, status=TaskStatus.RUNNING)

        results = recover_stuck_entities(uow)

        task_results = [r for r in results if r.entity == "task"]
        assert len(task_results) == 1
        assert task_results[0].recovery_action == "marked_failed"

    def test_running_task_with_active_runs_not_recovered(self):
        """Task RUNNING with active runs → not orphaned, skip it."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        task = _make_task(uow, status=TaskStatus.RUNNING, workspace_id=ws)

        # Create an active (RUNNING) run
        run = Run(task_id=task.id, workspace_id=ws)
        run.prepare()
        run.start()
        uow.runs.save(run)

        results = recover_stuck_entities(uow)

        task_results = [r for r in results if r.entity == "task"]
        assert len(task_results) == 0

    def test_task_recovered_event_emitted(self):
        uow = FakeUnitOfWork()
        ws = uuid4()
        task = _make_task(uow, status=TaskStatus.RUNNING, workspace_id=ws)

        run = Run(task_id=task.id, workspace_id=ws)
        run.prepare()
        run.fail()
        uow.runs.save(run)

        recover_stuck_entities(uow)

        task_events = [e for e in uow.outbox.events
                       if e.event_type == "task.recovered"]
        assert len(task_events) == 1
        assert task_events[0].payload["task_id"] == str(task.id)
        assert task_events[0].payload["recovery_action"] == "marked_failed"

    def test_skips_terminal_task(self):
        """Already terminal task → return None (not recovered)."""
        uow = FakeUnitOfWork()
        ws = uuid4()
        tid = uuid4()

        result = _recover_single_task(tid, ws, uow)

        assert result is None


# ── Full sweep integration ────────────────────────────────────


class TestFullSweep:
    def test_recovers_all_entity_types(self):
        """Single sweep handles runs, steps, and tasks together."""
        uow = FakeUnitOfWork()
        ws = uuid4()

        # Stuck run (PREPARING, old)
        run = _make_run(uow, status=RunStatus.PREPARING, workspace_id=ws,
                        created_minutes_ago=10)

        # Stuck step (RUNNING, old)
        step = _make_step(uow, workspace_id=ws, created_minutes_ago=60)

        # Orphaned task
        task = _make_task(uow, status=TaskStatus.RUNNING, workspace_id=ws)
        done_run = Run(task_id=task.id, workspace_id=ws)
        done_run.prepare()
        done_run.fail()
        uow.runs.save(done_run)

        results = recover_stuck_entities(uow)

        entities = {r.entity for r in results}
        assert "run" in entities
        assert "step" in entities
        assert "task" in entities

    def test_empty_sweep_returns_empty(self):
        uow = FakeUnitOfWork()

        results = recover_stuck_entities(uow)

        assert results == []
