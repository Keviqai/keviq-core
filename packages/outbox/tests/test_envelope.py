"""Tests for shared outbox envelope builder."""

import uuid
from unittest.mock import patch

from src.envelope import build_envelope


def test_build_envelope_basic():
    """Envelope has all required fields."""
    env = build_envelope(
        event_type="workspace.created",
        service_name="workspace-service",
        payload={"key": "value"},
        workspace_id=uuid.uuid4(),
    )
    assert env["event_type"] == "workspace.created"
    assert env["schema_version"] == "1.0"
    assert env["payload"] == {"key": "value"}
    assert env["workspace_id"] is not None
    assert env["emitted_by"]["service"] == "workspace-service"
    assert env["event_id"] is not None
    assert env["occurred_at"] is not None


def test_build_envelope_optional_ids_none():
    """Optional IDs default to None."""
    env = build_envelope(
        event_type="test.event",
        service_name="test-service",
        payload={},
    )
    assert env["task_id"] is None
    assert env["run_id"] is None
    assert env["step_id"] is None
    assert env["sandbox_id"] is None
    assert env["artifact_id"] is None


def test_build_envelope_custom_event_id():
    """Custom event_id is used when provided."""
    eid = uuid.uuid4()
    env = build_envelope(
        event_type="test.event",
        service_name="test-service",
        payload={},
        event_id=eid,
    )
    assert env["event_id"] == str(eid)


def test_build_envelope_actor():
    """Actor fields are set correctly."""
    env = build_envelope(
        event_type="test.event",
        service_name="test-service",
        payload={},
        actor_type="user",
        actor_id="user-123",
    )
    assert env["actor"]["type"] == "user"
    assert env["actor"]["id"] == "user-123"


def test_build_envelope_all_entity_ids():
    """All entity IDs are included when provided."""
    ids = {
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "step_id": uuid.uuid4(),
        "agent_invocation_id": uuid.uuid4(),
        "sandbox_id": uuid.uuid4(),
        "artifact_id": uuid.uuid4(),
        "correlation_id": uuid.uuid4(),
        "causation_id": uuid.uuid4(),
    }
    env = build_envelope(
        event_type="test.event",
        service_name="test-service",
        payload={},
        **ids,
    )
    for key, val in ids.items():
        assert env[key] == str(val), f"{key} mismatch"
