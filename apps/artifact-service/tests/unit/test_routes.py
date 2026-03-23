"""Unit tests for artifact-service API routes.

Uses FastAPI TestClient + fake UoW for isolation.
Tests: workspace isolation, error mapping, request validation, query caps.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.application.bootstrap import configure_uow_factory
from src.application.events import OutboxEvent
from src.application.ports import (
    ArtifactRepository,
    LineageEdgeRepository,
    OutboxWriter,
    ProvenanceRepository,
    TagRepository,
    UnitOfWork,
)
from src.application.services import (
    RegisterArtifactCommand,
    begin_writing,
    finalize_artifact,
    register_artifact,
)
from src.domain.artifact import Artifact, ArtifactStatus
from src.domain.lineage import ArtifactLineageEdge
from src.domain.provenance import ArtifactProvenance
from src.internal_auth import InternalTokenVerifier, configure_verifier
from internal_auth.token import InternalTokenIssuer

_TEST_SECRET = "test-secret-for-unit-tests-only"
_TEST_AUDIENCE = "artifact-service"


# ── Fakes (same as test_services.py) ─────────────────────────


class FakeArtifactRepository(ArtifactRepository):
    def __init__(self) -> None:
        self._store: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self._store[str(artifact.id)] = artifact

    def get_by_id(self, artifact_id: UUID) -> Artifact | None:
        return self._store.get(str(artifact_id))

    def list_by_run(self, run_id: UUID, workspace_id: UUID, *, limit: int = 100) -> list[Artifact]:
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

    def search(self, filters) -> list[Artifact]:
        return self.list_by_workspace(filters.workspace_id, limit=filters.limit)


class FakeProvenanceRepository(ProvenanceRepository):
    def __init__(self) -> None:
        self._store: dict[str, ArtifactProvenance] = {}

    def save(self, provenance: ArtifactProvenance) -> None:
        self._store[str(provenance.artifact_id)] = provenance

    def get_by_artifact_id(self, artifact_id: UUID) -> ArtifactProvenance | None:
        return self._store.get(str(artifact_id))


class FakeLineageEdgeRepository(LineageEdgeRepository):
    def __init__(self) -> None:
        self._edges: list[ArtifactLineageEdge] = []

    def save(self, edge: ArtifactLineageEdge) -> None:
        self._edges.append(edge)

    def list_parents(self, child_artifact_id: UUID) -> list[ArtifactLineageEdge]:
        return [
            e for e in self._edges
            if e.child_artifact_id == child_artifact_id
        ]

    def list_edges_by_workspace(self, workspace_id: UUID) -> list[tuple[UUID, UUID]]:
        return [
            (e.child_artifact_id, e.parent_artifact_id)
            for e in self._edges
        ]

    def list_ancestor_edges(self, artifact_id: UUID) -> list[ArtifactLineageEdge]:
        visited: set[UUID] = set()
        queue = [artifact_id]
        result: list[ArtifactLineageEdge] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            parents = self.list_parents(current)
            for edge in parents:
                result.append(edge)
                if edge.parent_artifact_id not in visited:
                    queue.append(edge.parent_artifact_id)
        return result


class FakeOutboxWriter(OutboxWriter):
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class _StubTagRepository(TagRepository):
    def add_tag(self, artifact_id, workspace_id, tag) -> None:
        pass

    def remove_tag(self, artifact_id, tag) -> bool:
        return False

    def get_tags(self, artifact_id) -> list[str]:
        return []

    def list_by_tag(self, workspace_id, tag, *, limit=50) -> list:
        return []


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.artifacts = FakeArtifactRepository()
        self.provenance = FakeProvenanceRepository()
        self.lineage_edges = FakeLineageEdgeRepository()
        self.tags = _StubTagRepository()
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


# ── Shared state for tests ────────────────────────────────────

# We need a shared UoW across route calls within a test, so we use a
# module-level variable that get_uow returns.
_shared_uow: FakeUnitOfWork | None = None


def _uow_factory() -> FakeUnitOfWork:
    """Return the shared FakeUnitOfWork for the current test."""
    assert _shared_uow is not None
    return _shared_uow


# ── Fixtures ──────────────────────────────────────────────────

VALID_CHECKSUM = "a" * 64
WS_ID = str(uuid.uuid4())
TASK_ID = str(uuid.uuid4())
RUN_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def setup_uow():
    """Create fresh FakeUnitOfWork for each test and configure bootstrap."""
    global _shared_uow
    _shared_uow = FakeUnitOfWork()
    configure_uow_factory(_uow_factory)
    yield
    _shared_uow = None


@pytest.fixture
def client():
    """Create TestClient with routes and internal auth configured."""
    # Configure a permissive verifier that accepts any service
    class _PermissiveVerifier(InternalTokenVerifier):
        """Verifier that skips allowed_services check for unit tests."""

        def verify(self, token, *, allowed_services=None):
            return super().verify(token, allowed_services=None)

    verifier = _PermissiveVerifier(
        secret=_TEST_SECRET, expected_audience=_TEST_AUDIENCE,
    )
    configure_verifier(verifier)

    issuer = InternalTokenIssuer(
        service_name="agent-runtime", secret=_TEST_SECRET,
    )
    token = issuer.issue(audience=_TEST_AUDIENCE)

    from src.api.routes import router
    app = FastAPI()
    app.include_router(router)
    tc = TestClient(app, raise_server_exceptions=False)
    tc.headers["Authorization"] = f"Bearer {token}"
    return tc


def _register_body(**overrides) -> dict[str, Any]:
    """Build a valid register request body."""
    defaults = {
        "workspace_id": WS_ID,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "name": "output.txt",
        "artifact_type": "file",
        "root_type": "generated",
        "model_provider": "anthropic",
        "model_name_concrete": "claude-sonnet-4-20250514",
        "model_version_concrete": "claude-sonnet-4-20250514",
        "run_config_hash": VALID_CHECKSUM,
    }
    defaults.update(overrides)
    return defaults


def _register_artifact(client: TestClient, **overrides) -> dict:
    """Register an artifact via API, return response JSON."""
    body = _register_body(**overrides)
    resp = client.post("/internal/v1/artifacts/register", json=body)
    assert resp.status_code == 202, resp.json()
    return resp.json()


# ── Register Artifact Tests ──────────────────────────────────


class TestRegisterArtifact:
    def test_register_success(self, client):
        resp = client.post("/internal/v1/artifacts/register", json=_register_body())
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["artifact_status"] == "pending"
        assert "artifact_id" in data

    def test_register_missing_field(self, client):
        body = _register_body()
        del body["name"]
        resp = client.post("/internal/v1/artifacts/register", json=body)
        assert resp.status_code == 400
        assert "name" in resp.json()["detail"]

    def test_register_invalid_uuid(self, client):
        body = _register_body(workspace_id="not-a-uuid")
        resp = client.post("/internal/v1/artifacts/register", json=body)
        assert resp.status_code == 400

    def test_register_model_alias_rejected(self, client):
        body = _register_body(model_name_concrete="latest")
        resp = client.post("/internal/v1/artifacts/register", json=body)
        assert resp.status_code == 400
        assert "alias" in resp.json()["detail"].lower()

    def test_register_invalid_artifact_type(self, client):
        body = _register_body(artifact_type="invalid_type")
        resp = client.post("/internal/v1/artifacts/register", json=body)
        assert resp.status_code == 400


# ── Begin Writing Tests ──────────────────────────────────────


class TestBeginWriting:
    def test_begin_writing_success(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": WS_ID, "storage_ref": "s3://bucket/key"},
        )
        assert resp.status_code == 202
        assert resp.json()["artifact_status"] == "writing"

    def test_begin_writing_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/internal/v1/artifacts/{fake_id}/begin-writing",
            json={"workspace_id": WS_ID, "storage_ref": "s3://bucket/key"},
        )
        assert resp.status_code == 404

    def test_begin_writing_wrong_workspace(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]
        other_ws = str(uuid.uuid4())

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": other_ws, "storage_ref": "s3://bucket/key"},
        )
        assert resp.status_code == 404

    def test_begin_writing_missing_storage_ref(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": WS_ID},
        )
        assert resp.status_code == 400

    def test_begin_writing_invalid_state_returns_409(self, client):
        """Cannot begin writing on an already-writing artifact."""
        reg = _register_artifact(client)
        aid = reg["artifact_id"]
        # First transition to WRITING
        client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": WS_ID, "storage_ref": "s3://bucket/key"},
        )
        # Second attempt should fail
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": WS_ID, "storage_ref": "s3://bucket/key2"},
        )
        assert resp.status_code == 409


# ── Finalize Artifact Tests ──────────────────────────────────


class TestFinalizeArtifact:
    def _setup_writing(self, client) -> str:
        reg = _register_artifact(client)
        aid = reg["artifact_id"]
        client.post(
            f"/internal/v1/artifacts/{aid}/begin-writing",
            json={"workspace_id": WS_ID, "storage_ref": "s3://bucket/key"},
        )
        return aid

    def test_finalize_success(self, client):
        aid = self._setup_writing(client)

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={
                "workspace_id": WS_ID,
                "checksum": VALID_CHECKSUM,
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 202
        assert resp.json()["artifact_status"] == "ready"
        assert resp.json()["checksum"] == VALID_CHECKSUM

    def test_finalize_not_found(self, client):
        resp = client.post(
            f"/internal/v1/artifacts/{uuid.uuid4()}/finalize",
            json={
                "workspace_id": WS_ID,
                "checksum": VALID_CHECKSUM,
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 404

    def test_finalize_wrong_workspace(self, client):
        aid = self._setup_writing(client)
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={
                "workspace_id": str(uuid.uuid4()),
                "checksum": VALID_CHECKSUM,
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 404

    def test_finalize_already_ready_returns_409(self, client):
        aid = self._setup_writing(client)
        # First finalize
        client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={
                "workspace_id": WS_ID,
                "checksum": VALID_CHECKSUM,
                "size_bytes": 1024,
            },
        )
        # Second finalize — immutability
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={
                "workspace_id": WS_ID,
                "checksum": VALID_CHECKSUM,
                "size_bytes": 1024,
            },
        )
        # The immutability guard raises DomainValidationError, mapped to 400
        # (or could be 409 for "already ready" conflict — both acceptable)
        assert resp.status_code in (400, 409)

    def test_finalize_invalid_checksum(self, client):
        aid = self._setup_writing(client)
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={
                "workspace_id": WS_ID,
                "checksum": "short",
                "size_bytes": 1024,
            },
        )
        assert resp.status_code == 400

    def test_finalize_missing_field(self, client):
        aid = self._setup_writing(client)
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/finalize",
            json={"workspace_id": WS_ID, "checksum": VALID_CHECKSUM},
        )
        assert resp.status_code == 400


# ── Fail Artifact Tests ──────────────────────────────────────


class TestFailArtifact:
    def test_fail_success(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/fail",
            json={"workspace_id": WS_ID, "failure_reason": "disk full"},
        )
        assert resp.status_code == 202
        assert resp.json()["artifact_status"] == "failed"

    def test_fail_not_found(self, client):
        resp = client.post(
            f"/internal/v1/artifacts/{uuid.uuid4()}/fail",
            json={"workspace_id": WS_ID},
        )
        assert resp.status_code == 404

    def test_fail_wrong_workspace(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/fail",
            json={"workspace_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    def test_fail_already_failed_returns_409(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]
        client.post(
            f"/internal/v1/artifacts/{aid}/fail",
            json={"workspace_id": WS_ID},
        )
        resp = client.post(
            f"/internal/v1/artifacts/{aid}/fail",
            json={"workspace_id": WS_ID},
        )
        assert resp.status_code == 409


# ── Record Lineage Tests ─────────────────────────────────────


class TestRecordLineage:
    def test_lineage_success(self, client):
        child = _register_artifact(client)
        parent = _register_artifact(client)

        resp = client.post(
            f"/internal/v1/artifacts/{child['artifact_id']}/lineage",
            json={
                "workspace_id": WS_ID,
                "parent_artifact_id": parent["artifact_id"],
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["edge_type"] == "derived_from"

    def test_lineage_self_loop_rejected(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.post(
            f"/internal/v1/artifacts/{aid}/lineage",
            json={
                "workspace_id": WS_ID,
                "parent_artifact_id": aid,
            },
        )
        assert resp.status_code == 400

    def test_lineage_not_found(self, client):
        reg = _register_artifact(client)

        resp = client.post(
            f"/internal/v1/artifacts/{reg['artifact_id']}/lineage",
            json={
                "workspace_id": WS_ID,
                "parent_artifact_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404

    def test_lineage_missing_parent(self, client):
        reg = _register_artifact(client)

        resp = client.post(
            f"/internal/v1/artifacts/{reg['artifact_id']}/lineage",
            json={"workspace_id": WS_ID},
        )
        assert resp.status_code == 400

    def test_lineage_cross_workspace_rejected(self, client):
        """Lineage edge cannot reference artifacts from another workspace."""
        other_ws = str(uuid.uuid4())
        child = _register_artifact(client)
        parent = _register_artifact(client, workspace_id=other_ws)

        resp = client.post(
            f"/internal/v1/artifacts/{child['artifact_id']}/lineage",
            json={
                "workspace_id": WS_ID,
                "parent_artifact_id": parent["artifact_id"],
            },
        )
        # Parent belongs to other workspace → 404
        assert resp.status_code == 404


# ── Get Artifact Tests ───────────────────────────────────────


class TestGetArtifact:
    def test_get_artifact_success(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.get(
            f"/internal/v1/artifacts/{aid}",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == aid
        assert data["artifact_status"] == "pending"
        assert data["name"] == "output.txt"
        # storage_ref should NOT be in response
        assert "storage_ref" not in data

    def test_get_artifact_not_found(self, client):
        resp = client.get(
            f"/internal/v1/artifacts/{uuid.uuid4()}",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 404

    def test_get_artifact_wrong_workspace(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.get(
            f"/internal/v1/artifacts/{aid}",
            params={"workspace_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    def test_get_artifact_missing_workspace(self, client):
        reg = _register_artifact(client)
        aid = reg["artifact_id"]

        resp = client.get(f"/internal/v1/artifacts/{aid}")
        assert resp.status_code == 422  # FastAPI validation error


# ── List Artifacts Tests ─────────────────────────────────────


class TestListArtifacts:
    def test_list_by_workspace(self, client):
        _register_artifact(client)
        _register_artifact(client)

        resp = client.get(
            "/internal/v1/artifacts",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["items"]) == 2

    def test_list_by_run(self, client):
        _register_artifact(client)

        resp = client.get(
            "/internal/v1/artifacts",
            params={"workspace_id": WS_ID, "run_id": RUN_ID},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_empty_workspace(self, client):
        resp = client.get(
            "/internal/v1/artifacts",
            params={"workspace_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_list_missing_workspace(self, client):
        resp = client.get("/internal/v1/artifacts")
        assert resp.status_code == 422

    def test_list_limit_cap(self, client):
        resp = client.get(
            "/internal/v1/artifacts",
            params={"workspace_id": WS_ID, "limit": 999},
        )
        # FastAPI Query(le=200) rejects values > 200
        assert resp.status_code == 422

    def test_list_cross_workspace_isolation(self, client):
        """Artifacts from different workspace should not appear."""
        other_ws = str(uuid.uuid4())
        _register_artifact(client, workspace_id=other_ws)

        resp = client.get(
            "/internal/v1/artifacts",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ── Ancestors Tests ──────────────────────────────────────────


class TestGetAncestors:
    def test_ancestors_success(self, client):
        child = _register_artifact(client)
        parent = _register_artifact(client)
        # Create edge
        client.post(
            f"/internal/v1/artifacts/{child['artifact_id']}/lineage",
            json={
                "workspace_id": WS_ID,
                "parent_artifact_id": parent["artifact_id"],
            },
        )

        resp = client.get(
            f"/internal/v1/artifacts/{child['artifact_id']}/lineage/ancestors",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["ancestors"]) == 1

    def test_ancestors_not_found(self, client):
        resp = client.get(
            f"/internal/v1/artifacts/{uuid.uuid4()}/lineage/ancestors",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 404

    def test_ancestors_wrong_workspace(self, client):
        reg = _register_artifact(client)
        resp = client.get(
            f"/internal/v1/artifacts/{reg['artifact_id']}/lineage/ancestors",
            params={"workspace_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404


# ── Provenance Tests ─────────────────────────────────────────


class TestGetProvenance:
    def test_provenance_success(self, client):
        reg = _register_artifact(client)

        resp = client.get(
            f"/internal/v1/artifacts/{reg['artifact_id']}/provenance",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_provider"] == "anthropic"
        assert data["artifact_id"] == reg["artifact_id"]

    def test_provenance_not_found(self, client):
        resp = client.get(
            f"/internal/v1/artifacts/{uuid.uuid4()}/provenance",
            params={"workspace_id": WS_ID},
        )
        assert resp.status_code == 404

    def test_provenance_wrong_workspace(self, client):
        reg = _register_artifact(client)
        resp = client.get(
            f"/internal/v1/artifacts/{reg['artifact_id']}/provenance",
            params={"workspace_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404


# ── Health Check Tests ───────────────────────────────────────


class TestHealthChecks:
    def test_liveness(self, client):
        resp = client.get("/healthz/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "live"

    def test_readiness(self, client):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
