"""UnitOfWork abstract base class.

Transaction boundary: state mutation + outbox write in same commit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.application.ports import (
    ApprovalRepository,
    OutboxWriter,
    RunRepository,
    StepRepository,
    TaskRepository,
)
from src.application.template_ports import AgentTemplateRepository, TaskTemplateRepository


class UnitOfWork(ABC):
    """Transaction boundary. State mutation + outbox write in same commit."""
    tasks: TaskRepository
    runs: RunRepository
    steps: StepRepository
    approvals: ApprovalRepository
    outbox: OutboxWriter
    task_templates: TaskTemplateRepository
    agent_templates: AgentTemplateRepository

    @abstractmethod
    def __enter__(self) -> UnitOfWork: ...
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    @abstractmethod
    def commit(self) -> None: ...
    @abstractmethod
    def rollback(self) -> None: ...
