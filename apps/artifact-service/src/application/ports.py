"""Application-layer port interfaces (abstractions).

Infrastructure layer implements these. Application layer depends on these only.
No SQLAlchemy, no FastAPI imports allowed here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.annotation import ArtifactAnnotation
    from src.domain.artifact import Artifact
    from src.domain.lineage import ArtifactLineageEdge
    from src.domain.provenance import ArtifactProvenance

    from .events import OutboxEvent


@dataclass(frozen=True)
class ArtifactSearchFilters:
    """Value object for artifact search/filter criteria."""

    workspace_id: UUID
    run_id: UUID | None = None
    name_contains: str | None = None
    artifact_type: str | None = None
    artifact_status: str | None = None
    root_type: str | None = None
    mime_type: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    tag: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0


class ArtifactRepository(ABC):
    @abstractmethod
    def save(self, artifact: Artifact) -> None: ...

    @abstractmethod
    def get_by_id(self, artifact_id: UUID) -> Artifact | None: ...

    @abstractmethod
    def list_by_run(self, run_id: UUID, workspace_id: UUID, *, limit: int = 100) -> list[Artifact]: ...

    @abstractmethod
    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50,
    ) -> list[Artifact]: ...

    @abstractmethod
    def search(self, filters: ArtifactSearchFilters) -> list[Artifact]: ...


class ProvenanceRepository(ABC):
    @abstractmethod
    def save(self, provenance: ArtifactProvenance) -> None: ...

    @abstractmethod
    def get_by_artifact_id(self, artifact_id: UUID) -> ArtifactProvenance | None: ...


class LineageEdgeRepository(ABC):
    @abstractmethod
    def save(self, edge: ArtifactLineageEdge) -> None: ...

    @abstractmethod
    def list_parents(self, child_artifact_id: UUID) -> list[ArtifactLineageEdge]: ...

    @abstractmethod
    def list_edges_by_workspace(self, workspace_id: UUID) -> list[tuple[UUID, UUID]]:
        """Return (child_id, parent_id) tuples scoped to a workspace for cycle detection."""
        ...

    @abstractmethod
    def list_ancestor_edges(self, artifact_id: UUID) -> list[ArtifactLineageEdge]:
        """Return all edges in the ancestor subgraph via recursive CTE."""
        ...


class TagRepository(ABC):
    @abstractmethod
    def add_tag(
        self, artifact_id: UUID, workspace_id: UUID, tag: str,
    ) -> None: ...

    @abstractmethod
    def remove_tag(self, artifact_id: UUID, tag: str) -> bool: ...

    @abstractmethod
    def get_tags(self, artifact_id: UUID) -> list[str]: ...

    @abstractmethod
    def list_by_tag(
        self, workspace_id: UUID, tag: str, *, limit: int = 50,
    ) -> list[UUID]: ...


class AnnotationRepository(ABC):
    @abstractmethod
    def save(self, annotation: ArtifactAnnotation) -> None: ...

    @abstractmethod
    def list_by_artifact(
        self, artifact_id: UUID, workspace_id: UUID, *, limit: int = 50,
    ) -> list[ArtifactAnnotation]: ...


class StorageBackend(ABC):
    """Artifact content storage abstraction.

    Implementations: local filesystem (PR47), S3/object storage (PR55).
    Storage paths follow PR44 naming convention:
      workspaces/<workspace_id>/runs/<run_id>/artifacts/<artifact_id>/content
    """

    @abstractmethod
    def write_content(self, storage_key: str, data: bytes) -> None:
        """Write artifact content to storage."""
        ...

    @abstractmethod
    def read_content(self, storage_key: str) -> bytes:
        """Read artifact content from storage. Raises FileNotFoundError if missing."""
        ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        """Check if content exists at storage key."""
        ...

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        """Delete content at storage key. No-op if missing."""
        ...


class OutboxWriter(ABC):
    @abstractmethod
    def write(self, event: OutboxEvent) -> None: ...


class UnitOfWork(ABC):
    """Transaction boundary. State mutation + outbox write in same commit."""

    artifacts: ArtifactRepository
    provenance: ProvenanceRepository
    lineage_edges: LineageEdgeRepository
    annotations: AnnotationRepository
    tags: TagRepository
    outbox: OutboxWriter

    @abstractmethod
    def __enter__(self) -> UnitOfWork: ...

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
