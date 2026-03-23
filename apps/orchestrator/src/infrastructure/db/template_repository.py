"""SQL repositories for TaskTemplate and AgentTemplate."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.template_ports import (
    AgentTemplateRepository,
    TaskTemplateRepository,
)
from src.domain.agent_template import AgentTemplate
from src.domain.task_template import TaskTemplate

from .mapping import (
    agent_template_row_to_domain,
    task_template_row_to_domain,
)
from .models import AgentTemplateRow, TaskTemplateRow


class SqlTaskTemplateRepository(TaskTemplateRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, template_id: UUID) -> TaskTemplate | None:
        row = self._session.get(TaskTemplateRow, str(template_id))
        if row is None:
            return None
        return task_template_row_to_domain(row)

    def list_system(
        self, *, category: str | None = None,
    ) -> list[TaskTemplate]:
        stmt = (
            select(TaskTemplateRow)
            .where(TaskTemplateRow.scope == 'system')
            .order_by(TaskTemplateRow.name)
        )
        if category:
            stmt = stmt.where(TaskTemplateRow.category == category)
        rows = self._session.execute(stmt).scalars().all()
        return [task_template_row_to_domain(r) for r in rows]

    def list_by_workspace(
        self, workspace_id: UUID,
    ) -> list[TaskTemplate]:
        stmt = (
            select(TaskTemplateRow)
            .where(TaskTemplateRow.workspace_id == str(workspace_id))
            .order_by(TaskTemplateRow.name)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [task_template_row_to_domain(r) for r in rows]


class SqlAgentTemplateRepository(AgentTemplateRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, template_id: UUID) -> AgentTemplate | None:
        row = self._session.get(AgentTemplateRow, str(template_id))
        if row is None:
            return None
        return agent_template_row_to_domain(row)

    def list_system(self) -> list[AgentTemplate]:
        stmt = (
            select(AgentTemplateRow)
            .where(AgentTemplateRow.scope == 'system')
            .order_by(AgentTemplateRow.name)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [agent_template_row_to_domain(r) for r in rows]

    def list_by_workspace(
        self, workspace_id: UUID,
    ) -> list[AgentTemplate]:
        stmt = (
            select(AgentTemplateRow)
            .where(AgentTemplateRow.workspace_id == str(workspace_id))
            .order_by(AgentTemplateRow.name)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [agent_template_row_to_domain(r) for r in rows]
