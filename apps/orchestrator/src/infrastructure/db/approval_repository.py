"""SQLAlchemy repository for ApprovalRequest.

Separate file to keep repositories.py under 300-line limit.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import ApprovalRepository
from src.domain.approval_request import ApprovalRequest

from .mapping import approval_request_domain_to_row, approval_request_row_to_domain
from .models import ApprovalRequestRow


class SqlApprovalRepository(ApprovalRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, approval: ApprovalRequest) -> None:
        data = approval_request_domain_to_row(approval)
        stmt = pg_insert(ApprovalRequestRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)

    def get_by_id(self, approval_id: UUID) -> ApprovalRequest | None:
        row = self._session.get(ApprovalRequestRow, str(approval_id))
        return approval_request_row_to_domain(row) if row else None

    def get_by_id_for_update(self, approval_id: UUID) -> ApprovalRequest | None:
        stmt = (
            select(ApprovalRequestRow)
            .where(ApprovalRequestRow.id == str(approval_id))
            .with_for_update()
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return approval_request_row_to_domain(row) if row else None

    def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        decision: str | None = None,
        reviewer_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequestRow).where(
            ApprovalRequestRow.workspace_id == str(workspace_id),
        )
        if decision:
            stmt = stmt.where(ApprovalRequestRow.decision == decision)
        if reviewer_id is not None:
            stmt = stmt.where(ApprovalRequestRow.reviewer_id == str(reviewer_id))
        stmt = stmt.order_by(ApprovalRequestRow.created_at.desc()).limit(limit).offset(offset)
        rows = self._session.execute(stmt).scalars().all()
        return [approval_request_row_to_domain(r) for r in rows]

    def count_pending_by_workspace(self, workspace_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ApprovalRequestRow)
            .where(ApprovalRequestRow.workspace_id == str(workspace_id))
            .where(ApprovalRequestRow.decision == "pending")
        )
        return self._session.execute(stmt).scalar_one()
