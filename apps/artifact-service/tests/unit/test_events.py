"""Unit tests for artifact outbox event factories."""

from __future__ import annotations

import uuid

from src.application.events import (
    OutboxEvent,
    artifact_failed_event,
    artifact_lineage_recorded_event,
    artifact_ready_event,
    artifact_registered_event,
    artifact_writing_event,
)


class TestOutboxEvent:
    def test_event_has_auto_id(self):
        e = OutboxEvent(
            event_type="test",
            workspace_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            payload={},
        )
        assert e.event_id is not None
        assert e.occurred_at is not None

    def test_event_is_frozen(self):
        e = OutboxEvent(
            event_type="test",
            workspace_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            payload={},
        )
        # frozen=True → immutable
        import pytest
        with pytest.raises(AttributeError):
            e.event_type = "changed"


class TestArtifactRegisteredEvent:
    def test_event_type(self):
        e = artifact_registered_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            artifact_type="file",
            root_type="generated",
            name="output.txt",
        )
        assert e.event_type == "artifact.registered"
        assert e.payload["artifact_type"] == "file"
        assert e.payload["root_type"] == "generated"
        assert e.payload["name"] == "output.txt"

    def test_causation_id_optional(self):
        e = artifact_registered_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            artifact_type="file",
            root_type="generated",
            name="output.txt",
        )
        assert e.causation_id is None


class TestArtifactWritingEvent:
    def test_event_type(self):
        e = artifact_writing_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            storage_ref="s3://bucket/key",
        )
        assert e.event_type == "artifact.writing"
        assert e.payload["storage_ref"] == "s3://bucket/key"
        assert e.run_id is not None


class TestArtifactReadyEvent:
    def test_event_type(self):
        e = artifact_ready_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            checksum="a" * 64,
            size_bytes=1024,
        )
        assert e.event_type == "artifact.ready"
        assert e.payload["checksum"] == "a" * 64
        assert e.payload["size_bytes"] == 1024


class TestArtifactFailedEvent:
    def test_event_type_with_reason(self):
        e = artifact_failed_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            failure_reason="disk full",
        )
        assert e.event_type == "artifact.failed"
        assert e.payload["failure_reason"] == "disk full"

    def test_event_without_reason(self):
        e = artifact_failed_event(
            artifact_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
        assert "failure_reason" not in e.payload


class TestArtifactLineageRecordedEvent:
    def test_event_type(self):
        e = artifact_lineage_recorded_event(
            edge_id=uuid.uuid4(),
            child_artifact_id=uuid.uuid4(),
            parent_artifact_id=uuid.uuid4(),
            edge_type="derived_from",
            workspace_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
        )
        assert e.event_type == "artifact.lineage_recorded"
        assert e.payload["edge_type"] == "derived_from"
        assert "child_artifact_id" in e.payload
        assert "parent_artifact_id" in e.payload
        assert "edge_id" in e.payload
