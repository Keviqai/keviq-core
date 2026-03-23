"""In-memory fake UoW for unit testing handlers and loop.

No database needed — stores domain objects in dicts.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.application.events import OutboxEvent
from src.application.ports import (
    OutboxWriter,
    RunRepository,
    StepRepository,
    TaskRepository,
    UnitOfWork,
)
from src.domain.run import Run
from src.domain.step import Step
from src.domain.task import Task, TaskStatus


class FakeTaskRepository(TaskRepository):
    def __init__(self):
        self._store: dict[UUID, Task] = {}

    def save(self, task: Task) -> None:
        self._store[task.id] = task

    def get_by_id(self, task_id: UUID) -> Task | None:
        return self._store.get(task_id)

    def list_pending(self, limit: int = 10) -> list[Task]:
        pending = [
            t for t in self._store.values()
            if t.task_status == TaskStatus.PENDING
        ]
        pending.sort(key=lambda t: t.created_at)
        return pending[:limit]

    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, offset: int = 0,
    ) -> list[Task]:
        tasks = [
            t for t in self._store.values()
            if t.workspace_id == workspace_id
        ]
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        return tasks[offset:offset + limit]

    def list_running(self, limit: int = 50) -> list[Task]:
        running = [
            t for t in self._store.values()
            if t.task_status == TaskStatus.RUNNING
        ]
        running.sort(key=lambda t: t.updated_at)
        return running[:limit]


class FakeRunRepository(RunRepository):
    def __init__(self):
        self._store: dict[UUID, Run] = {}

    def save(self, run: Run) -> None:
        self._store[run.id] = run

    def get_by_id(self, run_id: UUID) -> Run | None:
        return self._store.get(run_id)

    def list_active_by_task(self, task_id: UUID) -> list[Run]:
        return [r for r in self._store.values() if r.task_id == task_id and r.is_active]

    def get_latest_by_task(self, task_id: UUID) -> Run | None:
        runs = [r for r in self._store.values() if r.task_id == task_id]
        if not runs:
            return None
        return max(runs, key=lambda r: r.created_at)

    def get_by_id_for_update(self, run_id: UUID) -> Run | None:
        return self._store.get(run_id)

    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Run]:
        return [
            r for r in self._store.values()
            if r.run_status.value in statuses and r.updated_at < stuck_before
        ]

    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Run]:
        result = [
            r for r in self._store.values()
            if r.run_status.value in statuses and r.updated_at < stuck_before
        ]
        result.sort(key=lambda r: r.updated_at)
        return result[:limit]


class FakeStepRepository(StepRepository):
    def __init__(self):
        self._store: dict[UUID, Step] = {}

    def save(self, step: Step) -> None:
        self._store[step.id] = step

    def get_by_id(self, step_id: UUID) -> Step | None:
        return self._store.get(step_id)

    def list_active_by_run(self, run_id: UUID) -> list[Step]:
        return [s for s in self._store.values() if s.run_id == run_id and s.is_active]

    def list_by_run(self, run_id: UUID) -> list[Step]:
        steps = [s for s in self._store.values() if s.run_id == run_id]
        steps.sort(key=lambda s: s.sequence)
        return steps

    def get_by_id_for_update(self, step_id: UUID) -> Step | None:
        return self._store.get(step_id)

    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Step]:
        return [
            s for s in self._store.values()
            if s.step_status.value in statuses and s.updated_at < stuck_before
        ]

    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Step]:
        result = [
            s for s in self._store.values()
            if s.step_status.value in statuses and s.updated_at < stuck_before
        ]
        result.sort(key=lambda s: s.updated_at)
        return result[:limit]


class FakeTaskTemplateRepository:
    def __init__(self):
        self._store: dict[UUID, object] = {}

    def get_by_id(self, template_id: UUID):
        return self._store.get(template_id)

    def list_system(self, *, category: str | None = None) -> list:
        items = [t for t in self._store.values() if t.scope.value == 'system']
        if category:
            items = [t for t in items if t.category == category]
        items.sort(key=lambda t: t.name)
        return items

    def list_by_workspace(self, workspace_id: UUID) -> list:
        return [t for t in self._store.values() if t.workspace_id == workspace_id]

    def save(self, template) -> None:
        self._store[template.id] = template


class FakeAgentTemplateRepository:
    def __init__(self):
        self._store: dict[UUID, object] = {}

    def get_by_id(self, template_id: UUID):
        return self._store.get(template_id)

    def list_system(self) -> list:
        items = [a for a in self._store.values() if a.scope.value == 'system']
        items.sort(key=lambda a: a.name)
        return items

    def list_by_workspace(self, workspace_id: UUID) -> list:
        return [a for a in self._store.values() if a.workspace_id == workspace_id]

    def save(self, template) -> None:
        self._store[template.id] = template


class FakeOutboxWriter(OutboxWriter):
    def __init__(self):
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.tasks = FakeTaskRepository()
        self.runs = FakeRunRepository()
        self.steps = FakeStepRepository()
        self.task_templates = FakeTaskTemplateRepository()
        self.agent_templates = FakeAgentTemplateRepository()
        self.outbox = FakeOutboxWriter()
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rolled_back = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
