"""SQLAlchemy repository implementations.

All writes go through artifact_core schema only (S5-G1 principle).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.application.ports import (
    AnnotationRepository,
    ArtifactRepository,
    ArtifactSearchFilters,
    LineageEdgeRepository,
    ProvenanceRepository,
)
from src.domain.annotation import ArtifactAnnotation
from src.domain.artifact import Artifact
from src.domain.lineage import ArtifactLineageEdge
from src.domain.provenance import ArtifactProvenance

from .mapping import (
    artifact_domain_to_row,
    artifact_row_to_domain,
    edge_domain_to_row,
    edge_row_to_domain,
    provenance_domain_to_row,
    provenance_row_to_domain,
)
from .models import AnnotationRow, ArtifactRow, ArtifactTagRow, LineageEdgeRow, ProvenanceRow


class SqlArtifactRepository(ArtifactRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, artifact: Artifact) -> None:
        data = artifact_domain_to_row(artifact)
        # Remap Python attribute 'metadata_' to DB column name 'metadata'
        update_data = {
            ("metadata" if k == "metadata_" else k): v
            for k, v in data.items() if k != "id"
        }
        stmt = pg_insert(ArtifactRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_=update_data,
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        row = self._session.get(ArtifactRow, str(artifact_id))
        if row is None:
            return None
        return artifact_row_to_domain(row)

    def list_by_run(self, run_id: UUID, workspace_id: UUID, *, limit: int = 100) -> list[Artifact]:
        capped = min(limit, self._MAX_LIMIT)
        stmt = (
            select(ArtifactRow)
            .where(ArtifactRow.run_id == str(run_id))
            .where(ArtifactRow.workspace_id == str(workspace_id))
            .order_by(ArtifactRow.created_at.asc())
            .limit(capped)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [artifact_row_to_domain(r) for r in rows]

    _MAX_LIMIT = 200

    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50,
    ) -> list[Artifact]:
        capped = min(limit, self._MAX_LIMIT)
        stmt = (
            select(ArtifactRow)
            .where(ArtifactRow.workspace_id == str(workspace_id))
            .order_by(ArtifactRow.created_at.desc())
            .limit(capped)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [artifact_row_to_domain(r) for r in rows]

    def search(self, filters: ArtifactSearchFilters) -> list[Artifact]:
        """Build dynamic query from search filters."""
        capped = min(filters.limit, self._MAX_LIMIT)
        stmt = select(ArtifactRow).where(
            ArtifactRow.workspace_id == str(filters.workspace_id),
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_sort(stmt, filters)
        stmt = stmt.offset(filters.offset).limit(capped)
        rows = self._session.execute(stmt).scalars().all()
        return [artifact_row_to_domain(r) for r in rows]

    @staticmethod
    def _apply_filters(stmt, filters: ArtifactSearchFilters):
        """Apply WHERE clauses from filter values."""
        if filters.run_id:
            stmt = stmt.where(ArtifactRow.run_id == str(filters.run_id))
        if filters.name_contains:
            pattern = f"%{filters.name_contains}%"
            stmt = stmt.where(ArtifactRow.name.ilike(pattern))
        if filters.artifact_type:
            stmt = stmt.where(ArtifactRow.artifact_type == filters.artifact_type)
        if filters.artifact_status:
            stmt = stmt.where(ArtifactRow.artifact_status == filters.artifact_status)
        if filters.root_type:
            stmt = stmt.where(ArtifactRow.root_type == filters.root_type)
        if filters.mime_type:
            if "%" in filters.mime_type:
                stmt = stmt.where(ArtifactRow.mime_type.ilike(filters.mime_type))
            else:
                stmt = stmt.where(ArtifactRow.mime_type == filters.mime_type)
        if filters.created_after:
            stmt = stmt.where(ArtifactRow.created_at >= filters.created_after)
        if filters.created_before:
            stmt = stmt.where(ArtifactRow.created_at <= filters.created_before)
        if filters.tag:
            stmt = stmt.where(
                ArtifactRow.id.in_(
                    select(ArtifactTagRow.artifact_id).where(
                        ArtifactTagRow.workspace_id == str(filters.workspace_id),
                        ArtifactTagRow.tag == filters.tag,
                    )
                )
            )
        return stmt

    @staticmethod
    def _apply_sort(stmt, filters: ArtifactSearchFilters):
        """Apply ORDER BY from sort parameters."""
        sort_columns = {
            "created_at": ArtifactRow.created_at,
            "name": ArtifactRow.name,
            "size_bytes": ArtifactRow.size_bytes,
        }
        col = sort_columns.get(filters.sort_by, ArtifactRow.created_at)
        if filters.sort_order == "asc":
            stmt = stmt.order_by(col.asc())
        else:
            stmt = stmt.order_by(col.desc())
        return stmt


class SqlProvenanceRepository(ProvenanceRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, provenance: ArtifactProvenance) -> None:
        data = provenance_domain_to_row(provenance)
        stmt = pg_insert(ProvenanceRow).values(**data).on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in data.items() if k != "id"},
        )
        self._session.execute(stmt)
        self._session.expire_all()

    def get_by_artifact_id(self, artifact_id: UUID) -> ArtifactProvenance | None:
        stmt = select(ProvenanceRow).where(
            ProvenanceRow.artifact_id == str(artifact_id),
        )
        row = self._session.execute(stmt).scalars().first()
        if row is None:
            return None
        return provenance_row_to_domain(row)


class SqlLineageEdgeRepository(LineageEdgeRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, edge: ArtifactLineageEdge) -> None:
        data = edge_domain_to_row(edge)
        stmt = pg_insert(LineageEdgeRow).values(**data)
        self._session.execute(stmt)
        self._session.expire_all()

    def list_parents(self, child_artifact_id: UUID) -> list[ArtifactLineageEdge]:
        stmt = (
            select(LineageEdgeRow)
            .where(LineageEdgeRow.child_artifact_id == str(child_artifact_id))
            .order_by(LineageEdgeRow.created_at.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [edge_row_to_domain(r) for r in rows]

    def list_edges_by_workspace(self, workspace_id: UUID) -> list[tuple[UUID, UUID]]:
        """Return (child_id, parent_id) tuples scoped to a workspace for cycle detection."""
        stmt = text("""
            SELECT e.child_artifact_id, e.parent_artifact_id
            FROM artifact_core.artifact_lineage_edges e
            JOIN artifact_core.artifacts a ON a.id = e.child_artifact_id
            WHERE a.workspace_id = :workspace_id
        """)
        rows = self._session.execute(stmt, {"workspace_id": str(workspace_id)}).all()
        return [
            (UUID(str(r.child_artifact_id)), UUID(str(r.parent_artifact_id)))
            for r in rows
        ]

    def list_ancestor_edges(self, artifact_id: UUID) -> list[ArtifactLineageEdge]:
        """Return all edges in the ancestor subgraph via recursive CTE."""
        cte_sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT e.id, e.child_artifact_id, e.parent_artifact_id,
                       e.edge_type, e.run_id, e.step_id,
                       e.transform_detail, e.created_at, 1 AS depth
                FROM artifact_core.artifact_lineage_edges e
                WHERE e.child_artifact_id = :artifact_id
              UNION
                SELECT e.id, e.child_artifact_id, e.parent_artifact_id,
                       e.edge_type, e.run_id, e.step_id,
                       e.transform_detail, e.created_at, a.depth + 1
                FROM artifact_core.artifact_lineage_edges e
                JOIN ancestors a ON e.child_artifact_id = a.parent_artifact_id
                WHERE a.depth < 100
            )
            SELECT id, child_artifact_id, parent_artifact_id,
                   edge_type, run_id, step_id, transform_detail, created_at
            FROM ancestors
            ORDER BY created_at ASC
        """)
        rows = self._session.execute(cte_sql, {"artifact_id": str(artifact_id)}).all()
        return [edge_row_to_domain(r) for r in rows]


class SqlAnnotationRepository(AnnotationRepository):
    _MAX_LIMIT = 200

    def __init__(self, session: Session):
        self._session = session

    def save(self, annotation: ArtifactAnnotation) -> None:
        row = AnnotationRow(
            id=str(annotation.id),
            artifact_id=str(annotation.artifact_id),
            workspace_id=str(annotation.workspace_id),
            author_id=str(annotation.author_id),
            body=annotation.body,
            created_at=annotation.created_at,
        )
        self._session.add(row)

    def list_by_artifact(
        self, artifact_id: UUID, workspace_id: UUID, *, limit: int = 50,
    ) -> list[ArtifactAnnotation]:
        capped = min(limit, self._MAX_LIMIT)
        stmt = (
            select(AnnotationRow)
            .where(AnnotationRow.artifact_id == str(artifact_id))
            .where(AnnotationRow.workspace_id == str(workspace_id))
            .order_by(AnnotationRow.created_at.asc())
            .limit(capped)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_annotation_row_to_domain(r) for r in rows]


def _annotation_row_to_domain(row: AnnotationRow) -> ArtifactAnnotation:
    return ArtifactAnnotation(
        id=UUID(str(row.id)),
        artifact_id=UUID(str(row.artifact_id)),
        workspace_id=UUID(str(row.workspace_id)),
        author_id=UUID(str(row.author_id)),
        body=row.body,
        created_at=row.created_at,
    )
