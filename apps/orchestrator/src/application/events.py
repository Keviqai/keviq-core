"""Outbox event definitions for orchestrator.

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
    """Event to be written to the orchestrator outbox.

    Follows the envelope spec from doc 06, section 2.
    The outbox relay (PR11) will read these and forward to event_core.
    """

    event_type: str
    workspace_id: UUID
    correlation_id: UUID
    payload: dict[str, Any]
    task_id: UUID | None = None
    run_id: UUID | None = None
    step_id: UUID | None = None
    causation_id: UUID | None = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Event factory helpers ───────────────────────────────────────

def task_submitted_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    created_by_id: UUID,
    title: str,
    task_type: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="task.submitted",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "task_id": str(task_id),
            "created_by_id": str(created_by_id),
            "title": title,
            "task_type": task_type,
        },
    )


def task_started_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="task.started",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"task_id": str(task_id)},
    )


def task_completed_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="task.completed",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"task_id": str(task_id)},
    )


def task_cancelled_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    cancelled_by_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"task_id": str(task_id)}
    if cancelled_by_id is not None:
        payload["cancelled_by_id"] = str(cancelled_by_id)
    return OutboxEvent(
        event_type="task.cancelled",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def run_queued_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    trigger_type: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.queued",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "run_id": str(run_id),
            "task_id": str(task_id),
            "trigger_type": trigger_type,
        },
    )


def run_started_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.started",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"run_id": str(run_id), "task_id": str(task_id)},
    )


def run_completing_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.completing",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"run_id": str(run_id), "task_id": str(task_id)},
    )


def run_completed_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    duration_ms: int | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.completed",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "run_id": str(run_id),
            "task_id": str(task_id),
            "duration_ms": duration_ms,
        },
    )


def run_cancelled_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.cancelled",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"run_id": str(run_id), "task_id": str(task_id)},
    )


def step_started_event(
    *,
    step_id: UUID,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    step_type: str,
    sequence: int,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="step.started",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        step_id=step_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "step_id": str(step_id),
            "run_id": str(run_id),
            "step_type": step_type,
            "sequence": sequence,
        },
    )


def step_completed_event(
    *,
    step_id: UUID,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="step.completed",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        step_id=step_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"step_id": str(step_id), "run_id": str(run_id)},
    )


def step_failed_event(
    *,
    step_id: UUID,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    error_code: str | None = None,
    error_message: str | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"step_id": str(step_id), "run_id": str(run_id)}
    if error_code:
        payload["error_code"] = error_code
    if error_message:
        payload["error_message"] = error_message
    return OutboxEvent(
        event_type="step.failed",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        step_id=step_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def step_cancelled_event(
    *,
    step_id: UUID,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="step.cancelled",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        step_id=step_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"step_id": str(step_id), "run_id": str(run_id)},
    )


# ── Failure / timeout event helpers ──────────────────────────────

def task_failed_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    error_summary: str | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"task_id": str(task_id)}
    if error_summary:
        payload["error_summary"] = error_summary
    return OutboxEvent(
        event_type="task.failed",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def run_failed_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    error_summary: str | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"run_id": str(run_id), "task_id": str(task_id)}
    if error_summary:
        payload["error_summary"] = error_summary
    return OutboxEvent(
        event_type="run.failed",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def run_timed_out_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.timed_out",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"run_id": str(run_id), "task_id": str(task_id)},
    )


# ── Recovery event helpers ──────────────────────────────────────


def run_recovered_event(
    *,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    previous_status: str,
    recovery_action: str,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="run.recovered",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        correlation_id=correlation_id,
        payload={
            "run_id": str(run_id),
            "task_id": str(task_id),
            "previous_status": previous_status,
            "recovery_action": recovery_action,
        },
    )


def step_recovered_event(
    *,
    step_id: UUID,
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    previous_status: str,
    recovery_action: str,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="step.recovered",
        workspace_id=workspace_id,
        task_id=task_id,
        run_id=run_id,
        step_id=step_id,
        correlation_id=correlation_id,
        payload={
            "step_id": str(step_id),
            "run_id": str(run_id),
            "previous_status": previous_status,
            "recovery_action": recovery_action,
        },
    )


def task_retried_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    retried_by_id: UUID,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="task.retried",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        payload={
            "task_id": str(task_id),
            "retried_by_id": str(retried_by_id),
        },
    )


def task_recovered_event(
    *,
    task_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    previous_status: str,
    recovery_action: str,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="task.recovered",
        workspace_id=workspace_id,
        task_id=task_id,
        correlation_id=correlation_id,
        payload={
            "task_id": str(task_id),
            "previous_status": previous_status,
            "recovery_action": recovery_action,
        },
    )
