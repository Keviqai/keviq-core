"""SQLAlchemy tag repository for artifact tagging.

Tags are stored in artifact_core.artifact_tags (S5-G1 principle).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import TagRepository

from .models import ArtifactTagRow


class SqlTagRepository(TagRepository):
    _MAX_LIMIT = 200

    def __init__(self, session: Session):
        self._session = session

    def add_tag(
        self, artifact_id: UUID, workspace_id: UUID, tag: str,
    ) -> None:
        stmt = pg_insert(ArtifactTagRow).values(
            artifact_id=str(artifact_id),
            workspace_id=str(workspace_id),
            tag=tag,
        ).on_conflict_do_nothing(
            constraint="uq_artifact_tag",
        )
        self._session.execute(stmt)

    def remove_tag(self, artifact_id: UUID, tag: str) -> bool:
        stmt = text(
            "DELETE FROM artifact_core.artifact_tags "
            "WHERE artifact_id = :aid AND tag = :tag"
        )
        result = self._session.execute(
            stmt, {"aid": str(artifact_id), "tag": tag},
        )
        return result.rowcount > 0

    def get_tags(self, artifact_id: UUID) -> list[str]:
        stmt = (
            select(ArtifactTagRow.tag)
            .where(ArtifactTagRow.artifact_id == str(artifact_id))
            .order_by(ArtifactTagRow.tag.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return list(rows)

    def list_by_tag(
        self, workspace_id: UUID, tag: str, *, limit: int = 50,
    ) -> list[UUID]:
        capped = min(limit, self._MAX_LIMIT)
        stmt = (
            select(ArtifactTagRow.artifact_id)
            .where(ArtifactTagRow.workspace_id == str(workspace_id))
            .where(ArtifactTagRow.tag == tag)
            .limit(capped)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [UUID(str(r)) for r in rows]
