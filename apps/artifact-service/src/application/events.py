"""Outbox event definitions for artifact-service.

Maps domain transitions to event types per doc 06.
Events are written to the outbox table in the same transaction as state mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Event to be written to the artifact-service outbox.

    Follows the envelope spec from doc 06, section 2.
    The outbox relay will read these and forward to event_core.
    """

    event_type: str
    workspace_id: UUID
    correlation_id: UUID
    payload: dict[str, Any]
    artifact_id: UUID | None = None
    run_id: UUID | None = None
    causation_id: UUID | None = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Event factory helpers ───────────────────────────────────────


def artifact_registered_event(
    *,
    artifact_id: UUID,
    workspace_id: UUID,
    run_id: UUID,
    correlation_id: UUID,
    artifact_type: str,
    root_type: str,
    name: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="artifact.registered",
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "artifact_id": str(artifact_id),
            "run_id": str(run_id),
            "artifact_type": artifact_type,
            "root_type": root_type,
            "name": name,
        },
    )


def artifact_writing_event(
    *,
    artifact_id: UUID,
    workspace_id: UUID,
    run_id: UUID,
    correlation_id: UUID,
    storage_ref: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="artifact.writing",
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "artifact_id": str(artifact_id),
            "storage_ref": storage_ref,
        },
    )


def artifact_ready_event(
    *,
    artifact_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    checksum: str,
    size_bytes: int,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="artifact.ready",
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "artifact_id": str(artifact_id),
            "checksum": checksum,
            "size_bytes": size_bytes,
        },
    )


def artifact_failed_event(
    *,
    artifact_id: UUID,
    workspace_id: UUID,
    run_id: UUID,
    correlation_id: UUID,
    failure_reason: str | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"artifact_id": str(artifact_id)}
    if failure_reason:
        payload["failure_reason"] = failure_reason
    return OutboxEvent(
        event_type="artifact.failed",
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def artifact_lineage_recorded_event(
    *,
    edge_id: UUID,
    child_artifact_id: UUID,
    parent_artifact_id: UUID,
    edge_type: str,
    workspace_id: UUID,
    run_id: UUID | None,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="artifact.lineage_recorded",
        workspace_id=workspace_id,
        artifact_id=child_artifact_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "edge_id": str(edge_id),
            "child_artifact_id": str(child_artifact_id),
            "parent_artifact_id": str(parent_artifact_id),
            "edge_type": edge_type,
        },
    )
