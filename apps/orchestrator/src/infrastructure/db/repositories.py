"""SQLAlchemy repository implementations.

All writes go through orchestrator_core schema only (S1 principle).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import RunRepository, StepRepository, TaskRepository
from src.domain.run import Run, RunStatus
from src.domain.step import Step, StepStatus
from src.domain.task import Task

from .mapping import (
    run_domain_to_row,
    run_row_to_domain,
    step_domain_to_row,
    step_row_to_domain,
    task_domain_to_row,
    task_row_to_domain,
)
from .models import RunRow, StepRow, TaskRow


class SqlTaskRepository(TaskRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, task: Task) -> None:
        data = task_domain_to_row(task)
        stmt = pg_insert(TaskRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, task_id: UUID) -> Task | None:
        row = self._session.get(TaskRow, str(task_id))
        if row is None:
            return None
        return task_row_to_domain(row)

    def list_pending(self, limit: int = 10) -> list[Task]:
        stmt = (
            select(TaskRow)
            .where(TaskRow.task_status == "pending")
            .order_by(TaskRow.created_at.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [task_row_to_domain(r) for r in rows]

    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(TaskRow)
            .where(TaskRow.workspace_id == str(workspace_id))
            .order_by(TaskRow.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [task_row_to_domain(r) for r in rows]

    def list_running(self, limit: int = 50) -> list[Task]:
        stmt = (
            select(TaskRow)
            .where(TaskRow.task_status == "running")
            .order_by(TaskRow.updated_at.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [task_row_to_domain(r) for r in rows]


class SqlRunRepository(RunRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, run: Run) -> None:
        data = run_domain_to_row(run)
        stmt = pg_insert(RunRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, run_id: UUID) -> Run | None:
        row = self._session.get(RunRow, str(run_id))
        if row is None:
            return None
        return run_row_to_domain(row)

    def get_by_id_for_update(self, run_id: UUID) -> Run | None:
        """Load a run with SELECT ... FOR UPDATE row lock."""
        stmt = (
            select(RunRow)
            .where(RunRow.id == str(run_id))
            .with_for_update()
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return run_row_to_domain(row)

    def list_active_by_task(self, task_id: UUID) -> list[Run]:
        # Must match Run.is_active — excludes TIMED_OUT (can only → cancelled)
        active_statuses = [s.value for s in RunStatus if s not in (
            RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED,
            RunStatus.TIMED_OUT,
        )]
        stmt = select(RunRow).where(
            RunRow.task_id == str(task_id),
            RunRow.run_status.in_(active_statuses),
        )
        rows = self._session.execute(stmt).scalars().all()
        return [run_row_to_domain(r) for r in rows]

    def list_by_task(self, task_id: UUID) -> list[Run]:
        """Return all runs for a task, newest first."""
        stmt = (
            select(RunRow)
            .where(RunRow.task_id == str(task_id))
            .order_by(RunRow.created_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [run_row_to_domain(r) for r in rows]

    def get_latest_by_task(self, task_id: UUID) -> Run | None:
        stmt = (
            select(RunRow)
            .where(RunRow.task_id == str(task_id))
            .order_by(RunRow.created_at.desc())
            .limit(1)
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return run_row_to_domain(row)

    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Run]:
        stmt = (
            select(RunRow)
            .where(
                RunRow.run_status.in_(statuses),
                RunRow.updated_at < stuck_before,
            )
            .order_by(RunRow.updated_at.asc())
            .limit(100)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [run_row_to_domain(r) for r in rows]

    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Run]:
        """List stuck runs with FOR UPDATE SKIP LOCKED to avoid double-claim."""
        stmt = (
            select(RunRow)
            .where(
                RunRow.run_status.in_(statuses),
                RunRow.updated_at < stuck_before,
            )
            .order_by(RunRow.updated_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [run_row_to_domain(r) for r in rows]


class SqlStepRepository(StepRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, step: Step) -> None:
        data = step_domain_to_row(step)
        stmt = pg_insert(StepRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, step_id: UUID) -> Step | None:
        row = self._session.get(StepRow, str(step_id))
        if row is None:
            return None
        return step_row_to_domain(row)

    def get_by_id_for_update(self, step_id: UUID) -> Step | None:
        """Load a step with SELECT ... FOR UPDATE row lock."""
        stmt = (
            select(StepRow)
            .where(StepRow.id == str(step_id))
            .with_for_update()
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return step_row_to_domain(row)

    def list_active_by_run(self, run_id: UUID) -> list[Step]:
        active_statuses = [s.value for s in StepStatus if s not in (
            StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED,
        )]
        stmt = select(StepRow).where(
            StepRow.run_id == str(run_id),
            StepRow.step_status.in_(active_statuses),
        )
        rows = self._session.execute(stmt).scalars().all()
        return [step_row_to_domain(r) for r in rows]

    def list_by_run(self, run_id: UUID) -> list[Step]:
        stmt = (
            select(StepRow)
            .where(StepRow.run_id == str(run_id))
            .order_by(StepRow.sequence.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [step_row_to_domain(r) for r in rows]

    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Step]:
        stmt = (
            select(StepRow)
            .where(
                StepRow.step_status.in_(statuses),
                StepRow.updated_at < stuck_before,
            )
            .order_by(StepRow.updated_at.asc())
            .limit(100)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [step_row_to_domain(r) for r in rows]

    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Step]:
        """List stuck steps with FOR UPDATE SKIP LOCKED to avoid double-claim."""
        stmt = (
            select(StepRow)
            .where(
                StepRow.step_status.in_(statuses),
                StepRow.updated_at < stuck_before,
            )
            .order_by(StepRow.updated_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [step_row_to_domain(r) for r in rows]
