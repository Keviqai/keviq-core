"""Mapping between SQLAlchemy rows and domain objects.

Bidirectional conversion keeping domain objects free of ORM concerns.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.domain.sandbox import (
    Sandbox,
    SandboxStatus,
    SandboxType,
    TerminationReason,
)

from .models import SandboxAttemptRow, SandboxRow


# ── Sandbox ──────────────────────────────────────────────────


def sandbox_row_to_domain(row: SandboxRow) -> Sandbox:
    return Sandbox(
        id=UUID(str(row.id)),
        workspace_id=UUID(str(row.workspace_id)),
        task_id=UUID(str(row.task_id)),
        run_id=UUID(str(row.run_id)),
        step_id=UUID(str(row.step_id)),
        agent_invocation_id=UUID(str(row.agent_invocation_id)),
        sandbox_type=SandboxType(row.sandbox_type),
        sandbox_status=SandboxStatus(row.sandbox_status),
        policy_snapshot=row.policy_snapshot or {},
        resource_limits=row.resource_limits or {},
        network_egress_policy=row.network_egress_policy or {},
        started_at=row.started_at,
        terminated_at=row.terminated_at,
        termination_reason=(
            TerminationReason(row.termination_reason)
            if row.termination_reason else None
        ),
        error_detail=row.error_detail,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def sandbox_domain_to_row(sandbox: Sandbox) -> dict[str, Any]:
    return dict(
        id=str(sandbox.id),
        workspace_id=str(sandbox.workspace_id),
        task_id=str(sandbox.task_id),
        run_id=str(sandbox.run_id),
        step_id=str(sandbox.step_id),
        agent_invocation_id=str(sandbox.agent_invocation_id),
        sandbox_type=sandbox.sandbox_type.value,
        sandbox_status=sandbox.sandbox_status.value,
        policy_snapshot=sandbox.policy_snapshot,
        resource_limits=sandbox.resource_limits,
        network_egress_policy=sandbox.network_egress_policy,
        started_at=sandbox.started_at,
        terminated_at=sandbox.terminated_at,
        termination_reason=(
            sandbox.termination_reason.value
            if sandbox.termination_reason else None
        ),
        error_detail=sandbox.error_detail,
        created_at=sandbox.created_at,
        updated_at=sandbox.updated_at,
    )


# ── Execution Attempt ────────────────────────────────────────


def attempt_row_to_dict(row: SandboxAttemptRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "sandbox_id": str(row.sandbox_id),
        "attempt_index": row.attempt_index,
        "tool_name": row.tool_name,
        "tool_input": row.tool_input,
        "status": row.status,
        "stdout": row.stdout,
        "stderr": row.stderr,
        "exit_code": row.exit_code,
        "truncated": row.truncated,
        "error_detail": row.error_detail,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_at": row.created_at,
    }
