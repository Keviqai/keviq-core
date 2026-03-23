"""Outbox event definitions for execution-service.

Maps sandbox lifecycle transitions to event types per doc 06.
Events are written to the outbox table in the same transaction as state mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Event to be written to the execution-service outbox.

    Follows the envelope spec from doc 06, section 2.
    """

    event_type: str
    workspace_id: UUID
    correlation_id: UUID
    payload: dict[str, Any]
    sandbox_id: UUID | None = None
    causation_id: UUID | None = None
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Event factory helpers ───────────────────────────────────────


def sandbox_provision_requested_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    sandbox_type: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.provision_requested",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "sandbox_id": str(sandbox_id),
            "sandbox_type": sandbox_type,
        },
    )


def sandbox_provisioned_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.provisioned",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"sandbox_id": str(sandbox_id)},
    )


def sandbox_provision_failed_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    error_message: str | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {"sandbox_id": str(sandbox_id)}
    if error_message:
        payload["error_message"] = error_message
    return OutboxEvent(
        event_type="sandbox.provision_failed",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def sandbox_termination_requested_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    reason: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.termination_requested",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "sandbox_id": str(sandbox_id),
            "reason": reason,
        },
    )


def sandbox_terminated_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.terminated",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={"sandbox_id": str(sandbox_id)},
    )


# ── Tool Execution Events ─────────────────────────────────────


def tool_execution_requested_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    execution_id: UUID,
    tool_name: str,
    attempt_index: int,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.tool_execution.requested",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "sandbox_id": str(sandbox_id),
            "execution_id": str(execution_id),
            "tool_name": tool_name,
            "attempt_index": attempt_index,
        },
    )


def tool_execution_succeeded_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    execution_id: UUID,
    tool_name: str,
    attempt_index: int,
    exit_code: int,
    duration_ms: int | None = None,
    truncated: bool = False,
    stdout_size_bytes: int | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {
        "sandbox_id": str(sandbox_id),
        "execution_id": str(execution_id),
        "tool_name": tool_name,
        "attempt_index": attempt_index,
        "exit_code": exit_code,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if truncated:
        payload["truncated"] = True
    if stdout_size_bytes is not None:
        payload["stdout_size_bytes"] = stdout_size_bytes
    return OutboxEvent(
        event_type="sandbox.tool_execution.succeeded",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


def sandbox_recovered_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    previous_status: str,
    recovery_action: str,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="sandbox.recovered",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "sandbox_id": str(sandbox_id),
            "previous_status": previous_status,
            "recovery_action": recovery_action,
        },
    )


# ── Terminal Events ───────────────────────────────────────────


def terminal_command_executed_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    session_id: UUID,
    command_id: UUID,
    command: str,
    exit_code: int | None,
    duration_ms: int,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        event_type="terminal.command.executed",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={
            "sandbox_id": str(sandbox_id),
            "session_id": str(session_id),
            "command_id": str(command_id),
            "command": command[:200],
            "exit_code": exit_code,
            "duration_ms": duration_ms,
        },
    )


def tool_execution_failed_event(
    *,
    sandbox_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
    execution_id: UUID,
    tool_name: str,
    attempt_index: int,
    error_code: str | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
    exit_code: int | None = None,
    causation_id: UUID | None = None,
) -> OutboxEvent:
    payload: dict[str, Any] = {
        "sandbox_id": str(sandbox_id),
        "execution_id": str(execution_id),
        "tool_name": tool_name,
        "attempt_index": attempt_index,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    if error_message is not None:
        payload["error_message"] = error_message
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if exit_code is not None:
        payload["exit_code"] = exit_code
    return OutboxEvent(
        event_type="sandbox.tool_execution.failed",
        workspace_id=workspace_id,
        sandbox_id=sandbox_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )
