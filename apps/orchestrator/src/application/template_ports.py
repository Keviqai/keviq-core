"""Repository ports for template domain objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.agent_template import AgentTemplate
from src.domain.task_template import TaskTemplate


class TaskTemplateRepository(ABC):
    @abstractmethod
    def get_by_id(self, template_id: UUID) -> TaskTemplate | None: ...

    @abstractmethod
    def list_system(self, *, category: str | None = None) -> list[TaskTemplate]: ...

    @abstractmethod
    def list_by_workspace(self, workspace_id: UUID) -> list[TaskTemplate]: ...


class AgentTemplateRepository(ABC):
    @abstractmethod
    def get_by_id(self, template_id: UUID) -> AgentTemplate | None: ...

    @abstractmethod
    def list_system(self) -> list[AgentTemplate]: ...

    @abstractmethod
    def list_by_workspace(self, workspace_id: UUID) -> list[AgentTemplate]: ...
