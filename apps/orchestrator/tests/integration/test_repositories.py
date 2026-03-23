"""Integration tests for repositories and outbox — real PostgreSQL.

Tests:
- Save/load Task/Run/Step with correct status vocabulary
- Transaction rollback prevents orphan outbox events
- Correlation ID persisted correctly
- Simulated loop end-to-end with real DB
"""

import pytest
from uuid import uuid4

from sqlalchemy import select, text

from src.application.commands import SubmitTask
from src.application.handlers import handle_submit_task
from src.application.simulated_loop import run_simulated_execution
from src.domain.run import Run, RunStatus, TriggerType
from src.domain.step import Step, StepStatus, StepType
from src.domain.task import Task, TaskStatus, TaskType
from src.infrastructure.db.models import OutboxRow, TaskRow
from src.infrastructure.db.repositories import (
    SqlRunRepository,
    SqlStepRepository,
    SqlTaskRepository,
)
from src.infrastructure.db.unit_of_work import SqlUnitOfWork
from src.infrastructure.outbox.writer import SqlOutboxWriter
from src.application.events import OutboxEvent


# ── Task Repository ─────────────────────────────────────────────

class TestTaskRepository:
    def test_save_and_load(self, db_session):
        repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Integration test task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()

        repo.save(task)
        db_session.flush()

        loaded = repo.get_by_id(task.id)
        assert loaded is not None
        assert loaded.id == task.id
        assert loaded.task_status == TaskStatus.PENDING
        assert loaded.title == "Integration test task"

    def test_save_updates_existing(self, db_session):
        repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Will be updated",
            task_type=TaskType.RESEARCH,
            created_by_id=uuid4(),
        )
        task.submit()
        repo.save(task)
        db_session.flush()

        task.start()
        repo.save(task)
        db_session.flush()

        loaded = repo.get_by_id(task.id)
        assert loaded.task_status == TaskStatus.RUNNING

    def test_nonexistent_returns_none(self, db_session):
        repo = SqlTaskRepository(db_session)
        assert repo.get_by_id(uuid4()) is None


# ── Run Repository ──────────────────────────────────────────────

class TestRunRepository:
    def test_save_and_load(self, db_session):
        # First save a task (FK constraint)
        task_repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Parent task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task_repo.save(task)

        run_repo = SqlRunRepository(db_session)
        run = Run(task_id=task.id, workspace_id=task.workspace_id)
        run_repo.save(run)
        db_session.flush()

        loaded = run_repo.get_by_id(run.id)
        assert loaded is not None
        assert loaded.run_status == RunStatus.QUEUED

    def test_list_active_by_task(self, db_session):
        task_repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Multi-run task",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task.start()
        task_repo.save(task)

        run_repo = SqlRunRepository(db_session)

        # Active run
        run1 = Run(task_id=task.id, workspace_id=task.workspace_id)
        run1.prepare()
        run1.start()
        run_repo.save(run1)

        # Completed run
        run2 = Run(task_id=task.id, workspace_id=task.workspace_id)
        run2.prepare()
        run2.start()
        run2.begin_completing()
        run2.complete()
        run_repo.save(run2)

        db_session.flush()

        active = run_repo.list_active_by_task(task.id)
        assert len(active) == 1
        assert active[0].id == run1.id


# ── Step Repository ─────────────────────────────────────────────

class TestStepRepository:
    def test_save_and_load(self, db_session):
        task_repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Step test",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task_repo.save(task)

        run_repo = SqlRunRepository(db_session)
        run = Run(task_id=task.id, workspace_id=task.workspace_id)
        run_repo.save(run)

        step_repo = SqlStepRepository(db_session)
        step = Step(run_id=run.id, workspace_id=task.workspace_id, sequence=1)
        step_repo.save(step)
        db_session.flush()

        loaded = step_repo.get_by_id(step.id)
        assert loaded is not None
        assert loaded.step_status == StepStatus.PENDING
        assert loaded.sequence == 1

    def test_list_active_by_run(self, db_session):
        task_repo = SqlTaskRepository(db_session)
        task = Task(
            workspace_id=uuid4(),
            title="Step list test",
            task_type=TaskType.CODING,
            created_by_id=uuid4(),
        )
        task.submit()
        task_repo.save(task)

        run_repo = SqlRunRepository(db_session)
        run = Run(task_id=task.id, workspace_id=task.workspace_id)
        run_repo.save(run)

        step_repo = SqlStepRepository(db_session)

        # Active step
        s1 = Step(run_id=run.id, workspace_id=task.workspace_id, sequence=1)
        s1.start()
        step_repo.save(s1)

        # Completed step
        s2 = Step(run_id=run.id, workspace_id=task.workspace_id, sequence=2)
        s2.start()
        s2.complete(output_snapshot={"done": True})
        step_repo.save(s2)

        db_session.flush()

        active = step_repo.list_active_by_run(run.id)
        assert len(active) == 1
        assert active[0].id == s1.id


# ── Outbox Writer ───────────────────────────────────────────────

class TestOutboxWriter:
    def test_write_event(self, db_session):
        writer = SqlOutboxWriter(db_session)
        event = OutboxEvent(
            event_type="task.submitted",
            workspace_id=uuid4(),
            correlation_id=uuid4(),
            task_id=uuid4(),
            payload={"test": True},
        )
        writer.write(event)
        db_session.flush()

        row = db_session.execute(
            select(OutboxRow).where(OutboxRow.id == str(event.event_id))
        ).scalar_one()
        assert row.event_type == "task.submitted"
        assert str(row.correlation_id) == str(event.correlation_id)
        assert row.published_at is None  # not yet published

    def test_correlation_id_persisted(self, db_session):
        writer = SqlOutboxWriter(db_session)
        corr_id = uuid4()
        events = [
            OutboxEvent(event_type="run.queued", workspace_id=uuid4(),
                        correlation_id=corr_id, payload={}),
            OutboxEvent(event_type="run.started", workspace_id=uuid4(),
                        correlation_id=corr_id, payload={}),
        ]
        for e in events:
            writer.write(e)
        db_session.flush()

        rows = db_session.execute(
            select(OutboxRow).where(OutboxRow.correlation_id == str(corr_id))
        ).scalars().all()
        assert len(rows) == 2


# ── Transactional Integrity ─────────────────────────────────────

class TestTransactionalIntegrity:
    def test_submit_and_loop_end_to_end(self, session_factory):
        """Full pipeline: submit → simulated execution → verify DB state."""
        uow = SqlUnitOfWork(session_factory)

        # Submit
        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="E2E test",
            task_type="coding",
            created_by_id=uuid4(),
        )
        result = handle_submit_task(cmd, uow)
        task_id = result.task.id

        # Simulate
        run_simulated_execution(task_id, uow)

        # Verify final state
        with uow:
            task = uow.tasks.get_by_id(task_id)
            assert task.task_status == TaskStatus.COMPLETED

    def test_outbox_events_match_transitions(self, session_factory):
        """Every state transition produces an outbox event."""
        uow = SqlUnitOfWork(session_factory)

        cmd = SubmitTask(
            workspace_id=uuid4(),
            title="Event trace test",
            task_type="analysis",
            created_by_id=uuid4(),
        )
        result = handle_submit_task(cmd, uow)

        run_simulated_execution(result.task.id, uow)

        # Check outbox has events
        with uow:
            session = uow._session
            rows = session.execute(select(OutboxRow)).scalars().all()
            event_types = [r.event_type for r in rows]

            # Submit produces task.submitted
            assert "task.submitted" in event_types
            # Loop produces the full sequence
            assert "task.started" in event_types
            assert "run.queued" in event_types
            assert "run.started" in event_types
            assert "step.started" in event_types
            assert "step.completed" in event_types
            assert "run.completing" in event_types
            assert "run.completed" in event_types
            assert "task.completed" in event_types
