"""Unit tests for artifact application services.

Uses in-memory fake repositories for isolation.
Tests service-level behavior: register, begin_writing, finalize, fail, record_lineage.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import pytest

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
    fail_artifact,
    finalize_artifact,
    record_lineage_edge,
    register_artifact,
)
from src.domain.artifact import Artifact, ArtifactStatus
from src.domain.errors import (
    ArtifactNotFoundError,
    DomainValidationError,
    LineageCycleError,
    LineageSelfLoopError,
)
from src.domain.lineage import ArtifactLineageEdge
from src.domain.provenance import ArtifactProvenance


# ── Fakes ──────────────────────────────────────────────────────


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


# ── Helpers ────────────────────────────────────────────────────


VALID_CHECKSUM = "a" * 64


def _make_register_cmd(**overrides) -> RegisterArtifactCommand:
    defaults: dict[str, Any] = {
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "name": "output.txt",
        "artifact_type": "file",
        "root_type": "generated",
        "model_provider": "anthropic",
        "model_name_concrete": "claude-sonnet-4-20250514",
        "model_version_concrete": "claude-sonnet-4-20250514",
        "run_config_hash": "a" * 64,
    }
    defaults.update(overrides)
    return RegisterArtifactCommand(**defaults)


def _register_and_write(uow: FakeUnitOfWork, **overrides) -> Artifact:
    """Register artifact and transition to WRITING."""
    cmd = _make_register_cmd(**overrides)
    artifact = register_artifact(cmd, uow)
    artifact = begin_writing(
        artifact.id, storage_ref="s3://bucket/key", uow=uow,
    )
    return artifact


# ── Register Tests ─────────────────────────────────────────────


class TestRegisterArtifact:
    def test_creates_pending_artifact(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        assert artifact.artifact_status == ArtifactStatus.PENDING
        assert artifact.name == "output.txt"
        assert uow._committed

    def test_creates_provenance_record(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        prov = uow.provenance.get_by_artifact_id(artifact.id)
        assert prov is not None
        assert prov.model_provider == "anthropic"
        assert prov.model_name_concrete == "claude-sonnet-4-20250514"
        assert prov.run_config_hash == "a" * 64

    def test_emits_registered_event(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        assert len(uow.outbox.events) == 1
        event = uow.outbox.events[0]
        assert event.event_type == "artifact.registered"
        assert event.payload["artifact_id"] == str(artifact.id)
        assert event.payload["artifact_type"] == "file"

    def test_artifact_id_assigned_by_service(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        assert artifact.id is not None

    def test_model_alias_rejected(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd(model_name_concrete="latest")
        with pytest.raises(Exception, match="alias"):
            register_artifact(cmd, uow)

    def test_agent_invocation_id_preserved(self):
        uow = FakeUnitOfWork()
        inv_id = uuid.uuid4()
        cmd = _make_register_cmd(agent_invocation_id=inv_id)
        artifact = register_artifact(cmd, uow)
        assert artifact.agent_invocation_id == inv_id

    def test_correlation_id_propagated(self):
        uow = FakeUnitOfWork()
        cid = uuid.uuid4()
        cmd = _make_register_cmd(correlation_id=cid)
        register_artifact(cmd, uow)
        event = uow.outbox.events[0]
        assert event.correlation_id == cid


# ── Begin Writing Tests ────────────────────────────────────────


class TestBeginWriting:
    def test_transitions_to_writing(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        result = begin_writing(
            artifact.id, storage_ref="s3://bucket/key", uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.WRITING
        assert result.storage_ref == "s3://bucket/key"

    def test_emits_writing_event(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        begin_writing(artifact.id, storage_ref="s3://bucket/key", uow=uow)
        # registered + writing events
        assert len(uow.outbox.events) == 2
        assert uow.outbox.events[1].event_type == "artifact.writing"

    def test_not_found_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(ArtifactNotFoundError):
            begin_writing(
                uuid.uuid4(), storage_ref="s3://bucket/key", uow=uow,
            )

    def test_empty_storage_ref_rejected(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        with pytest.raises(DomainValidationError, match="storage_ref"):
            begin_writing(artifact.id, storage_ref="", uow=uow)


# ── Finalize Tests ─────────────────────────────────────────────


class TestFinalizeArtifact:
    def test_writing_to_ready(self):
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        result = finalize_artifact(
            artifact.id,
            checksum=VALID_CHECKSUM,
            size_bytes=1024,
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.READY
        assert result.checksum == VALID_CHECKSUM
        assert result.size_bytes == 1024
        assert result.ready_at is not None

    def test_emits_ready_event(self):
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        finalize_artifact(
            artifact.id,
            checksum=VALID_CHECKSUM,
            size_bytes=512,
            uow=uow,
        )
        ready_events = [e for e in uow.outbox.events if e.event_type == "artifact.ready"]
        assert len(ready_events) == 1
        assert ready_events[0].payload["checksum"] == VALID_CHECKSUM
        assert ready_events[0].payload["size_bytes"] == 512

    def test_not_found_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(ArtifactNotFoundError):
            finalize_artifact(
                uuid.uuid4(),
                checksum=VALID_CHECKSUM,
                size_bytes=0,
                uow=uow,
            )

    def test_no_provenance_raises(self):
        """If provenance was somehow deleted, finalize rejects."""
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        # Remove provenance
        uow.provenance._store.clear()
        with pytest.raises(DomainValidationError, match="no provenance"):
            finalize_artifact(
                artifact.id,
                checksum=VALID_CHECKSUM,
                size_bytes=0,
                uow=uow,
            )

    def test_incomplete_provenance_rejected(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd(model_provider=None)
        artifact = register_artifact(cmd, uow)
        begin_writing(artifact.id, storage_ref="s3://bucket/key", uow=uow)
        with pytest.raises(Exception):  # IncompleteProvenanceError
            finalize_artifact(
                artifact.id,
                checksum=VALID_CHECKSUM,
                size_bytes=0,
                uow=uow,
            )

    def test_invalid_checksum_rejected(self):
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        with pytest.raises(DomainValidationError, match="SHA-256"):
            finalize_artifact(
                artifact.id,
                checksum="abc",
                size_bytes=0,
                uow=uow,
            )

    def test_ready_artifact_cannot_be_refinalized(self):
        """Carry-over from PR26: checksum/provenance immutability."""
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        finalize_artifact(
            artifact.id,
            checksum=VALID_CHECKSUM,
            size_bytes=100,
            uow=uow,
        )
        with pytest.raises(DomainValidationError, match="immutable"):
            finalize_artifact(
                artifact.id,
                checksum="b" * 64,
                size_bytes=200,
                uow=uow,
            )

    def test_checksum_normalized_to_lowercase(self):
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        upper_checksum = "A" * 64
        result = finalize_artifact(
            artifact.id,
            checksum=upper_checksum,
            size_bytes=50,
            uow=uow,
        )
        assert result.checksum == "a" * 64


# ── Fail Tests ─────────────────────────────────────────────────


class TestFailArtifact:
    def test_pending_to_failed(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        result = fail_artifact(
            artifact.id,
            failure_reason="provision error",
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.FAILED
        assert result.failed_at is not None

    def test_writing_to_failed(self):
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        result = fail_artifact(
            artifact.id,
            failure_reason="write error",
            partial_data=True,
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.FAILED
        assert result.metadata["partial_data_available"] is True

    def test_emits_failed_event(self):
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        fail_artifact(
            artifact.id,
            failure_reason="error",
            uow=uow,
        )
        failed_events = [e for e in uow.outbox.events if e.event_type == "artifact.failed"]
        assert len(failed_events) == 1
        assert failed_events[0].payload["failure_reason"] == "error"

    def test_not_found_raises(self):
        uow = FakeUnitOfWork()
        with pytest.raises(ArtifactNotFoundError):
            fail_artifact(uuid.uuid4(), uow=uow)


# ── Lineage Edge Tests ────────────────────────────────────────


class TestRecordLineageEdge:
    def _make_two_artifacts(self, uow: FakeUnitOfWork):
        wid = uuid.uuid4()
        cmd1 = _make_register_cmd(workspace_id=wid, name="parent.txt")
        cmd2 = _make_register_cmd(workspace_id=wid, name="child.txt")
        parent = register_artifact(cmd1, uow)
        child = register_artifact(cmd2, uow)
        return parent, child, wid

    def test_records_edge(self):
        uow = FakeUnitOfWork()
        parent, child, wid = self._make_two_artifacts(uow)
        edge = record_lineage_edge(
            child_artifact_id=child.id,
            parent_artifact_id=parent.id,
            workspace_id=wid,
            uow=uow,
        )
        assert edge.child_artifact_id == child.id
        assert edge.parent_artifact_id == parent.id
        assert edge.edge_type.value == "derived_from"

    def test_emits_lineage_recorded_event(self):
        uow = FakeUnitOfWork()
        parent, child, wid = self._make_two_artifacts(uow)
        record_lineage_edge(
            child_artifact_id=child.id,
            parent_artifact_id=parent.id,
            workspace_id=wid,
            uow=uow,
        )
        lineage_events = [
            e for e in uow.outbox.events
            if e.event_type == "artifact.lineage_recorded"
        ]
        assert len(lineage_events) == 1
        assert lineage_events[0].payload["child_artifact_id"] == str(child.id)

    def test_self_loop_rejected(self):
        uow = FakeUnitOfWork()
        wid = uuid.uuid4()
        cmd = _make_register_cmd(workspace_id=wid)
        artifact = register_artifact(cmd, uow)
        with pytest.raises(LineageSelfLoopError):
            record_lineage_edge(
                child_artifact_id=artifact.id,
                parent_artifact_id=artifact.id,
                workspace_id=wid,
                uow=uow,
            )

    def test_cycle_detected(self):
        uow = FakeUnitOfWork()
        wid = uuid.uuid4()
        a = register_artifact(_make_register_cmd(workspace_id=wid, name="a"), uow)
        b = register_artifact(_make_register_cmd(workspace_id=wid, name="b"), uow)
        c = register_artifact(_make_register_cmd(workspace_id=wid, name="c"), uow)

        # a → b → c
        record_lineage_edge(
            child_artifact_id=b.id, parent_artifact_id=a.id,
            workspace_id=wid, uow=uow,
        )
        record_lineage_edge(
            child_artifact_id=c.id, parent_artifact_id=b.id,
            workspace_id=wid, uow=uow,
        )

        # c → a would create cycle
        with pytest.raises(LineageCycleError):
            record_lineage_edge(
                child_artifact_id=a.id, parent_artifact_id=c.id,
                workspace_id=wid, uow=uow,
            )

    def test_child_not_found_raises(self):
        uow = FakeUnitOfWork()
        wid = uuid.uuid4()
        parent = register_artifact(
            _make_register_cmd(workspace_id=wid), uow,
        )
        with pytest.raises(ArtifactNotFoundError):
            record_lineage_edge(
                child_artifact_id=uuid.uuid4(),
                parent_artifact_id=parent.id,
                workspace_id=wid,
                uow=uow,
            )

    def test_parent_not_found_raises(self):
        uow = FakeUnitOfWork()
        wid = uuid.uuid4()
        child = register_artifact(
            _make_register_cmd(workspace_id=wid), uow,
        )
        with pytest.raises(ArtifactNotFoundError):
            record_lineage_edge(
                child_artifact_id=child.id,
                parent_artifact_id=uuid.uuid4(),
                workspace_id=wid,
                uow=uow,
            )

    def test_valid_dag_accepted(self):
        """Diamond DAG: a→c, a→d, b→c, b→d — no cycle."""
        uow = FakeUnitOfWork()
        wid = uuid.uuid4()
        a = register_artifact(_make_register_cmd(workspace_id=wid, name="a"), uow)
        b = register_artifact(_make_register_cmd(workspace_id=wid, name="b"), uow)
        c = register_artifact(_make_register_cmd(workspace_id=wid, name="c"), uow)
        d = register_artifact(_make_register_cmd(workspace_id=wid, name="d"), uow)

        record_lineage_edge(child_artifact_id=c.id, parent_artifact_id=a.id, workspace_id=wid, uow=uow)
        record_lineage_edge(child_artifact_id=c.id, parent_artifact_id=b.id, workspace_id=wid, uow=uow)
        record_lineage_edge(child_artifact_id=d.id, parent_artifact_id=a.id, workspace_id=wid, uow=uow)
        record_lineage_edge(child_artifact_id=d.id, parent_artifact_id=b.id, workspace_id=wid, uow=uow)
        # All should succeed — DAG is valid


# ── Full Lifecycle Tests ───────────────────────────────────────


class TestFullLifecycle:
    def test_register_write_finalize_happy_path(self):
        """Complete happy path: register → writing → ready."""
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        result = finalize_artifact(
            artifact.id,
            checksum=VALID_CHECKSUM,
            size_bytes=2048,
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.READY
        assert result.checksum == VALID_CHECKSUM
        assert result.size_bytes == 2048

        # Verify events: registered, writing, ready
        event_types = [e.event_type for e in uow.outbox.events]
        assert "artifact.registered" in event_types
        assert "artifact.writing" in event_types
        assert "artifact.ready" in event_types

    def test_register_write_fail_path(self):
        """Failure path: register → writing → failed."""
        uow = FakeUnitOfWork()
        artifact = _register_and_write(uow)
        result = fail_artifact(
            artifact.id,
            failure_reason="disk full",
            partial_data=True,
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.FAILED
        assert result.metadata["failure_reason"] == "disk full"
        assert result.metadata["partial_data_available"] is True

    def test_register_fail_path(self):
        """Failure from pending: register → failed."""
        uow = FakeUnitOfWork()
        cmd = _make_register_cmd()
        artifact = register_artifact(cmd, uow)
        result = fail_artifact(
            artifact.id,
            failure_reason="provision error",
            uow=uow,
        )
        assert result.artifact_status == ArtifactStatus.FAILED
