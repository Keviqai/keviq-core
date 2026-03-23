"""Shared fakes and fixtures for artifact search/tag tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.bootstrap import configure_uow_factory
from src.application.events import OutboxEvent
from src.application.ports import (
    AnnotationRepository,
    ArtifactRepository,
    ArtifactSearchFilters,
    LineageEdgeRepository,
    OutboxWriter,
    ProvenanceRepository,
    TagRepository,
    UnitOfWork,
)
from src.domain.artifact import Artifact, ArtifactStatus, ArtifactType, RootType


# ── Fakes ─────────────────────────────────────────────────────


class FakeArtifactRepository(ArtifactRepository):
    def __init__(self) -> None:
        self._store: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self._store[str(artifact.id)] = artifact

    def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        return self._store.get(str(artifact_id))

    def list_by_run(
        self, run_id: UUID, workspace_id: UUID, *, limit: int = 100,
    ) -> list[Artifact]:
        return [
            a for a in self._store.values()
            if a.run_id == run_id and a.workspace_id == workspace_id
        ][:limit]

    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50,
    ) -> list[Artifact]:
        return [
            a for a in self._store.values()
            if a.workspace_id == workspace_id
        ][:limit]

    def search(self, filters: ArtifactSearchFilters) -> list[Artifact]:
        """In-memory search matching SqlArtifactRepository.search."""
        results = [
            a for a in self._store.values()
            if a.workspace_id == filters.workspace_id
        ]
        results = _apply_filters(results, filters, self._tag_repo)
        results = _apply_sort(results, filters)
        return results[filters.offset:filters.offset + filters.limit]

    # Set externally by fixture so tag filtering works
    _tag_repo: TagRepository | None = None


def _apply_filters(
    items: list[Artifact],
    f: ArtifactSearchFilters,
    tag_repo: TagRepository | None,
) -> list[Artifact]:
    if f.run_id:
        items = [a for a in items if a.run_id == f.run_id]
    if f.name_contains:
        lc = f.name_contains.lower()
        items = [a for a in items if lc in a.name.lower()]
    if f.artifact_type:
        items = [a for a in items if a.artifact_type.value == f.artifact_type]
    if f.artifact_status:
        items = [a for a in items if a.artifact_status.value == f.artifact_status]
    if f.root_type:
        items = [a for a in items if a.root_type.value == f.root_type]
    if f.mime_type:
        if "%" in f.mime_type:
            prefix = f.mime_type.replace("%", "")
            items = [a for a in items if a.mime_type and a.mime_type.startswith(prefix)]
        else:
            items = [a for a in items if a.mime_type == f.mime_type]
    if f.created_after:
        items = [a for a in items if a.created_at >= f.created_after]
    if f.created_before:
        items = [a for a in items if a.created_at <= f.created_before]
    if f.tag and tag_repo:
        tagged_ids = tag_repo.list_by_tag(f.workspace_id, f.tag)
        items = [a for a in items if a.id in tagged_ids]
    return items


def _apply_sort(
    items: list[Artifact], f: ArtifactSearchFilters,
) -> list[Artifact]:
    key_map = {
        "created_at": lambda a: a.created_at,
        "name": lambda a: a.name.lower(),
        "size_bytes": lambda a: a.size_bytes or 0,
    }
    key_fn = key_map.get(f.sort_by, key_map["created_at"])
    return sorted(items, key=key_fn, reverse=(f.sort_order == "desc"))


class FakeTagRepository(TagRepository):
    def __init__(self) -> None:
        self._tags: dict[str, set[str]] = {}
        self._workspace_map: dict[str, str] = {}

    def add_tag(
        self, artifact_id: UUID, workspace_id: UUID, tag: str,
    ) -> None:
        key = str(artifact_id)
        if key not in self._tags:
            self._tags[key] = set()
        self._tags[key].add(tag)
        self._workspace_map[key] = str(workspace_id)

    def remove_tag(self, artifact_id: UUID, tag: str) -> bool:
        key = str(artifact_id)
        if key in self._tags and tag in self._tags[key]:
            self._tags[key].discard(tag)
            return True
        return False

    def get_tags(self, artifact_id: UUID) -> list[str]:
        return sorted(self._tags.get(str(artifact_id), set()))

    def list_by_tag(
        self, workspace_id: UUID, tag: str, *, limit: int = 50,
    ) -> list[UUID]:
        results: list[UUID] = []
        for aid, tags in self._tags.items():
            if tag in tags and self._workspace_map.get(aid) == str(workspace_id):
                results.append(UUID(aid))
        return results[:limit]


class FakeProvenanceRepository(ProvenanceRepository):
    def __init__(self) -> None:
        self._store: dict = {}

    def save(self, provenance) -> None:
        self._store[str(provenance.artifact_id)] = provenance

    def get_by_artifact_id(self, artifact_id: UUID):
        return self._store.get(str(artifact_id))


class FakeLineageEdgeRepository(LineageEdgeRepository):
    def __init__(self) -> None:
        self._edges: list = []

    def save(self, edge) -> None:
        self._edges.append(edge)

    def list_parents(self, child_artifact_id: UUID) -> list:
        return []

    def list_edges_by_workspace(self, workspace_id: UUID) -> list:
        return []

    def list_ancestor_edges(self, artifact_id: UUID) -> list:
        return []


class FakeAnnotationRepository(AnnotationRepository):
    def save(self, annotation) -> None:
        pass

    def list_by_artifact(self, artifact_id, workspace_id, *, limit=50):
        return []


class FakeOutboxWriter(OutboxWriter):
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self, tag_repo: FakeTagRepository) -> None:
        self.artifacts = FakeArtifactRepository()
        self.artifacts._tag_repo = tag_repo
        self.provenance = FakeProvenanceRepository()
        self.lineage_edges = FakeLineageEdgeRepository()
        self.annotations = FakeAnnotationRepository()
        self.tags = tag_repo
        self.outbox = FakeOutboxWriter()
        self._committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        pass


# ── Shared state ──────────────────────────────────────────────

_shared_uow: FakeUnitOfWork | None = None

WS_ID = str(uuid.uuid4())
TASK_ID = str(uuid.uuid4())
RUN_ID = str(uuid.uuid4())

_TEST_SECRET = "test-secret-for-unit-tests-only"
_TEST_AUDIENCE = "artifact-service"


def _uow_factory() -> FakeUnitOfWork:
    assert _shared_uow is not None
    return _shared_uow


def setup_test_env() -> tuple[TestClient, FakeUnitOfWork]:
    """Create fresh UoW, configure auth, return (client, uow)."""
    global _shared_uow
    tag_repo = FakeTagRepository()
    _shared_uow = FakeUnitOfWork(tag_repo)
    configure_uow_factory(_uow_factory)

    from src.internal_auth import InternalTokenVerifier, configure_verifier
    from internal_auth.token import InternalTokenIssuer

    verifier = InternalTokenVerifier(
        secret=_TEST_SECRET, expected_audience=_TEST_AUDIENCE,
    )
    configure_verifier(verifier)
    issuer = InternalTokenIssuer(
        service_name="api-gateway", secret=_TEST_SECRET,
    )
    token = issuer.issue(audience=_TEST_AUDIENCE)

    app = FastAPI()
    from src.api.routes import router
    app.include_router(router)

    tc = TestClient(app)
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc, _shared_uow


def make_artifact(
    *,
    name: str = "test-artifact",
    artifact_type: ArtifactType = ArtifactType.FILE,
    root_type: RootType = RootType.GENERATED,
    artifact_status: ArtifactStatus = ArtifactStatus.READY,
    mime_type: str | None = "text/plain",
    size_bytes: int | None = 100,
    created_at: datetime | None = None,
    workspace_id: str = WS_ID,
    run_id: str = RUN_ID,
) -> Artifact:
    return Artifact(
        workspace_id=UUID(workspace_id),
        task_id=UUID(TASK_ID),
        run_id=UUID(run_id),
        name=name,
        artifact_type=artifact_type,
        root_type=root_type,
        artifact_status=artifact_status,
        mime_type=mime_type,
        size_bytes=size_bytes,
        created_at=created_at or datetime.now(timezone.utc),
    )
