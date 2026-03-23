"""Recovery service for stuck sandboxes and executions.

Sweeps for sandboxes stuck in intermediate states past a configurable
threshold and reconciles them to a terminal/safe state.  Backend cleanup
is best-effort — state reconciliation is always explicit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from src.domain.sandbox import SandboxStatus

from .events import sandbox_recovered_event
from .ports import SandboxBackend, UnitOfWork

logger = logging.getLogger(__name__)

# ── Default thresholds ────────────────────────────────────────

# Sandbox stuck in PROVISIONING for longer than this is considered abandoned.
STUCK_PROVISIONING_MINUTES = 10

# Sandbox stuck in EXECUTING for longer than this is considered abandoned.
STUCK_EXECUTING_MINUTES = 15

# Statuses that can be stuck in an intermediate state.
_STUCK_STATUSES = [
    SandboxStatus.PROVISIONING.value,
    SandboxStatus.EXECUTING.value,
]


def recover_stuck_sandboxes(
    uow: UnitOfWork,
    backend: SandboxBackend,
    *,
    provisioning_timeout_minutes: int = STUCK_PROVISIONING_MINUTES,
    executing_timeout_minutes: int = STUCK_EXECUTING_MINUTES,
) -> list[dict[str, Any]]:
    """Find and recover sandboxes stuck in intermediate states.

    Returns a list of recovery actions taken, each a dict with:
      sandbox_id, previous_status, recovery_action, success
    """
    now = datetime.now(timezone.utc)
    # Use the shorter timeout as the cutoff — list_stuck returns both,
    # and we filter per-status below.
    min_timeout = min(provisioning_timeout_minutes, executing_timeout_minutes)
    stuck_before = now - timedelta(minutes=min_timeout)

    results: list[dict[str, Any]] = []

    with uow:
        stuck_sandboxes = uow.sandboxes.list_stuck(
            stuck_before=stuck_before,
            statuses=_STUCK_STATUSES,
        )

    for sandbox in stuck_sandboxes:
        # Apply per-status threshold
        if sandbox.sandbox_status == SandboxStatus.PROVISIONING:
            cutoff = now - timedelta(minutes=provisioning_timeout_minutes)
        else:
            cutoff = now - timedelta(minutes=executing_timeout_minutes)

        if sandbox.updated_at > cutoff:
            continue  # Not stuck long enough for this status

        result = _recover_single_sandbox(sandbox.id, sandbox.workspace_id,
                                          sandbox.sandbox_status, uow, backend)
        results.append(result)

    if results:
        logger.info("Recovery sweep completed: %d sandboxes processed", len(results))
    return results


def _recover_single_sandbox(
    sandbox_id: UUID,
    workspace_id: UUID,
    previous_status: SandboxStatus,
    uow: UnitOfWork,
    backend: SandboxBackend,
) -> dict[str, Any]:
    """Recover a single stuck sandbox."""
    correlation_id = uuid4()
    prev_status_value = previous_status.value

    # Best-effort backend cleanup
    backend_cleaned = False
    try:
        if backend.is_alive(sandbox_id):
            backend.terminate(sandbox_id)
            backend_cleaned = True
            logger.info("Recovery: terminated backend for sandbox %s", sandbox_id)
        else:
            backend_cleaned = True  # Already gone
            logger.info("Recovery: backend for sandbox %s already gone", sandbox_id)
    except Exception as exc:
        logger.warning(
            "Recovery: backend cleanup failed for sandbox %s: %s",
            sandbox_id, exc,
        )

    # State reconciliation — always explicit regardless of backend result
    try:
        with uow:
            sandbox = uow.sandboxes.get_by_id_for_update(sandbox_id)
            if sandbox is None or sandbox.is_terminal:
                return {
                    "sandbox_id": str(sandbox_id),
                    "previous_status": prev_status_value,
                    "recovery_action": "skipped_already_terminal",
                    "success": True,
                }

            # Guard: sandbox may have recovered naturally since list_stuck ran.
            # Only proceed if still in a stuck-eligible status.
            if sandbox.sandbox_status.value not in [s for s in _STUCK_STATUSES]:
                return {
                    "sandbox_id": str(sandbox_id),
                    "previous_status": prev_status_value,
                    "recovery_action": "skipped_no_longer_stuck",
                    "success": True,
                }

            # Transition: current → FAILED (with error detail)
            sandbox.mark_failed(error_detail={
                "code": "RECOVERY_SWEEP",
                "message": f"Sandbox stuck in {prev_status_value}, recovered by sweep",
                "backend_cleaned": backend_cleaned,
            })
            uow.sandboxes.save(sandbox)

            uow.outbox.write(sandbox_recovered_event(
                sandbox_id=sandbox_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                previous_status=prev_status_value,
                recovery_action="marked_failed",
            ))
            uow.commit()

        logger.info(
            "Recovery: sandbox %s (%s → failed)", sandbox_id, prev_status_value,
        )
        return {
            "sandbox_id": str(sandbox_id),
            "previous_status": prev_status_value,
            "recovery_action": "marked_failed",
            "success": True,
        }
    except Exception as exc:
        logger.error(
            "Recovery: state reconciliation failed for sandbox %s: %s",
            sandbox_id, exc,
        )
        return {
            "sandbox_id": str(sandbox_id),
            "previous_status": prev_status_value,
            "recovery_action": "reconciliation_failed",
            "success": False,
            "error": str(exc),
        }
