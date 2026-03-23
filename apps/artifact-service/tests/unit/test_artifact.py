"""Unit tests for Artifact domain entity and state machine."""

from __future__ import annotations

import uuid

import pytest

from src.domain.artifact import Artifact, ArtifactStatus, ArtifactType, RootType
from src.domain.errors import (
    DomainValidationError,
    IncompleteProvenanceError,
    InvalidTransitionError,
    TerminalStateError,
)
from src.domain.provenance import ArtifactProvenance


def _make_artifact(**overrides) -> Artifact:
    defaults = {
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "name": "output.txt",
        "artifact_type": ArtifactType.FILE,
        "root_type": RootType.GENERATED,
    }
    defaults.update(overrides)
    return Artifact(**defaults)


def _make_complete_provenance(artifact_id: uuid.UUID) -> ArtifactProvenance:
    """Create a provenance with all required fields for finalization."""
    return ArtifactProvenance(
        artifact_id=artifact_id,
        input_snapshot=[],
        run_config_hash="a" * 64,
        model_provider="anthropic",
        model_name_concrete="claude-sonnet-4-20250514",
        model_version_concrete="claude-sonnet-4-20250514",
        lineage_chain=[],
    )


VALID_CHECKSUM = "a" * 64  # 64 hex chars = valid SHA-256


# ── Construction ──────────────────────────────────────────────


class TestArtifactConstruction:
    def test_default_status_is_pending(self):
        a = _make_artifact()
        assert a.artifact_status == ArtifactStatus.PENDING

    def test_default_root_type_is_generated(self):
        a = _make_artifact()
        assert a.root_type == RootType.GENERATED

    def test_timestamps_populated(self):
        a = _make_artifact()
        assert a.created_at is not None
        assert a.updated_at is not None

    def test_id_assigned_by_service(self):
        a = _make_artifact()
        assert a.id is not None

    def test_explicit_id_honored(self):
        eid = uuid.uuid4()
        a = _make_artifact(id=eid)
        assert a.id == eid

    def test_blank_name_rejected(self):
        with pytest.raises(DomainValidationError, match="name must not be blank"):
            _make_artifact(name="")

    def test_whitespace_name_rejected(self):
        with pytest.raises(DomainValidationError, match="name must not be blank"):
            _make_artifact(name="   ")

    def test_defaults_empty_collections(self):
        a = _make_artifact()
        assert a.lineage == []
        assert a.metadata == {}

    def test_nullable_fields_initially_none(self):
        a = _make_artifact()
        assert a.step_id is None
        assert a.agent_invocation_id is None
        assert a.checksum is None
        assert a.size_bytes is None
        assert a.storage_ref is None
        assert a.ready_at is None
        assert a.failed_at is None

    def test_equality_by_id(self):
        aid = uuid.uuid4()
        a1 = _make_artifact(id=aid)
        a2 = _make_artifact(id=aid)
        assert a1 == a2
        assert hash(a1) == hash(a2)

    def test_inequality_different_id(self):
        a1 = _make_artifact()
        a2 = _make_artifact()
        assert a1 != a2


# ── State Machine: Valid Transitions ─────────────────────────


class TestArtifactValidTransitions:
    def test_pending_to_writing(self):
        a = _make_artifact()
        prev = a.begin_writing(storage_ref="s3://bucket/key")
        assert prev == ArtifactStatus.PENDING
        assert a.artifact_status == ArtifactStatus.WRITING
        assert a.storage_ref == "s3://bucket/key"

    def test_pending_to_failed(self):
        a = _make_artifact()
        prev = a.fail(failure_reason="provision error")
        assert prev == ArtifactStatus.PENDING
        assert a.artifact_status == ArtifactStatus.FAILED
        assert a.failed_at is not None
        assert a.metadata["failure_reason"] == "provision error"

    def test_writing_to_ready(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        prev = a.finalize(checksum=VALID_CHECKSUM, size_bytes=1024, provenance=prov)
        assert prev == ArtifactStatus.WRITING
        assert a.artifact_status == ArtifactStatus.READY
        assert a.checksum == VALID_CHECKSUM
        assert a.size_bytes == 1024
        assert a.ready_at is not None

    def test_writing_to_failed(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prev = a.fail(failure_reason="write error", partial_data=True)
        assert prev == ArtifactStatus.WRITING
        assert a.artifact_status == ArtifactStatus.FAILED
        assert a.metadata["partial_data_available"] is True

    def test_updated_at_changes_on_transition(self):
        a = _make_artifact()
        original = a.updated_at
        a.begin_writing(storage_ref="s3://bucket/key")
        assert a.updated_at >= original


# ── State Machine: Invalid Transitions ───────────────────────


class TestArtifactInvalidTransitions:
    def test_pending_to_ready_not_allowed(self):
        a = _make_artifact()
        prov = _make_complete_provenance(a.id)
        with pytest.raises(InvalidTransitionError):
            a.finalize(checksum=VALID_CHECKSUM, size_bytes=0, provenance=prov)

    def test_writing_to_writing_not_allowed(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        with pytest.raises(InvalidTransitionError):
            a.begin_writing(storage_ref="s3://bucket/key2")

    def test_ready_is_terminal(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        a.finalize(checksum=VALID_CHECKSUM, size_bytes=0, provenance=prov)
        with pytest.raises(TerminalStateError):
            a.fail()

    def test_failed_is_terminal(self):
        a = _make_artifact()
        a.fail()
        with pytest.raises(TerminalStateError):
            a.begin_writing(storage_ref="s3://bucket/key")


# ── Finalize Validation ──────────────────────────────────────


class TestArtifactFinalize:
    def test_invalid_checksum_length_rejected(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        with pytest.raises(DomainValidationError, match="SHA-256"):
            a.finalize(checksum="abc", size_bytes=0, provenance=prov)

    def test_empty_checksum_rejected(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        with pytest.raises(DomainValidationError, match="SHA-256"):
            a.finalize(checksum="", size_bytes=0, provenance=prov)

    def test_non_hex_checksum_rejected(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        bad_checksum = "g" * 64  # 'g' is not hex
        with pytest.raises(DomainValidationError, match="hexadecimal"):
            a.finalize(checksum=bad_checksum, size_bytes=0, provenance=prov)

    def test_negative_size_rejected(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        with pytest.raises(DomainValidationError, match="size_bytes"):
            a.finalize(checksum=VALID_CHECKSUM, size_bytes=-1, provenance=prov)

    def test_incomplete_provenance_rejected(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        incomplete = ArtifactProvenance(artifact_id=a.id)
        with pytest.raises(IncompleteProvenanceError):
            a.finalize(checksum=VALID_CHECKSUM, size_bytes=0, provenance=incomplete)

    def test_storage_ref_required_for_writing(self):
        a = _make_artifact()
        with pytest.raises(DomainValidationError, match="storage_ref"):
            a.begin_writing(storage_ref="")

    def test_checksum_normalized_to_lowercase(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        upper_checksum = "A" * 64
        a.finalize(checksum=upper_checksum, size_bytes=100, provenance=prov)
        assert a.checksum == "a" * 64  # normalized to lowercase


# ── Query Helpers ─────────────────────────────────────────────


class TestArtifactQueryHelpers:
    def test_is_terminal_ready(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        prov = _make_complete_provenance(a.id)
        a.finalize(checksum=VALID_CHECKSUM, size_bytes=0, provenance=prov)
        assert a.is_terminal is True
        assert a.is_ready is True
        assert a.is_failed is False

    def test_is_terminal_failed(self):
        a = _make_artifact()
        a.fail()
        assert a.is_terminal is True
        assert a.is_ready is False
        assert a.is_failed is True

    def test_pending_not_terminal(self):
        a = _make_artifact()
        assert a.is_terminal is False

    def test_writing_not_terminal(self):
        a = _make_artifact()
        a.begin_writing(storage_ref="s3://bucket/key")
        assert a.is_terminal is False
