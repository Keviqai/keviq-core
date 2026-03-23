"""Orchestrator recovery sweep for stuck tasks, runs, and steps.

Finds entities stuck in intermediate states past configurable thresholds
and transitions them to terminal states.  Recovery is idempotent — running
the sweep twice produces stable results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from src.domain.run import Run

from src.domain.run import RunStatus
from src.domain.step import StepStatus
from src.domain.task import TaskStatus

from .events import run_recovered_event, step_recovered_event, task_recovered_event
from .ports import RecoveryResult, UnitOfWork

logger = logging.getLogger(__name__)

# ── Default thresholds ────────────────────────────────────────

# Runs stuck in PREPARING for longer than this.
STUCK_PREPARING_MINUTES = 5

# Runs stuck in RUNNING for longer than this.
STUCK_RUNNING_MINUTES = 30

# Runs stuck in COMPLETING for longer than this.
STUCK_COMPLETING_MINUTES = 5

# Steps stuck in RUNNING for longer than this.
STUCK_STEP_RUNNING_MINUTES = 30

# Statuses eligible for run recovery.
_STUCK_RUN_STATUSES = [
    RunStatus.PREPARING.value,
    RunStatus.RUNNING.value,
    RunStatus.COMPLETING.value,
]

# Statuses eligible for step recovery.
_STUCK_STEP_STATUSES = [
    StepStatus.RUNNING.value,
]


def recover_stuck_entities(
    uow: UnitOfWork,
    *,
    preparing_timeout_minutes: int = STUCK_PREPARING_MINUTES,
    running_timeout_minutes: int = STUCK_RUNNING_MINUTES,
    completing_timeout_minutes: int = STUCK_COMPLETING_MINUTES,
    step_running_timeout_minutes: int = STUCK_STEP_RUNNING_MINUTES,
) -> list[RecoveryResult]:
    """Find and recover stuck runs, steps, and orphaned tasks.

    Returns a list of typed recovery results.
    """
    results: list[RecoveryResult] = []

    # 1. Recover stuck runs
    results.extend(_recover_stuck_runs(
        uow,
        preparing_timeout_minutes=preparing_timeout_minutes,
        running_timeout_minutes=running_timeout_minutes,
        completing_timeout_minutes=completing_timeout_minutes,
    ))

    # 2. Recover stuck steps
    results.extend(_recover_stuck_steps(
        uow,
        step_running_timeout_minutes=step_running_timeout_minutes,
    ))

    # 3. Recover orphaned tasks (RUNNING but all runs terminal)
    results.extend(_recover_orphaned_tasks(uow))

    if results:
        logger.info("Orchestrator recovery sweep: %d entities processed", len(results))
    return results


# ── Run recovery ──────────────────────────────────────────────


def _recover_stuck_runs(
    uow: UnitOfWork,
    *,
    preparing_timeout_minutes: int,
    running_timeout_minutes: int,
    completing_timeout_minutes: int,
) -> list[RecoveryResult]:
    now = datetime.now(timezone.utc)
    results: list[RecoveryResult] = []

    # Issue per-status queries to avoid the LIMIT crowding problem:
    # a single query with min_timeout could fill the batch with
    # not-yet-stuck RUNNING runs, crowding out legitimately stuck ones.
    per_status = [
        ([RunStatus.PREPARING.value], preparing_timeout_minutes),
        ([RunStatus.RUNNING.value], running_timeout_minutes),
        ([RunStatus.COMPLETING.value], completing_timeout_minutes),
    ]

    # Design note: we list candidates with SKIP LOCKED in one transaction,
    # then recover each in its own transaction with FOR UPDATE.  The listing
    # lock is released before individual recovery, so two concurrent sweeps
    # *can* pick up the same row — but the idempotency guards in
    # _recover_single_run (terminal check + status-change check) ensure only
    # one actually mutates.  This is intentional: holding a single long
    # transaction across many rows would cause worse lock contention.
    stuck_runs: list[Run] = []
    with uow:
        for statuses, timeout_minutes in per_status:
            cutoff = now - timedelta(minutes=timeout_minutes)
            stuck_runs.extend(uow.runs.list_stuck_for_update(
                stuck_before=cutoff,
                statuses=statuses,
            ))

    for run in stuck_runs:
        result = _recover_single_run(run.id, run.task_id, run.workspace_id,
                                      run.run_status, uow)
        results.append(result)

    return results


def _recover_single_run(
    run_id: UUID,
    task_id: UUID,
    workspace_id: UUID,
    previous_status: RunStatus,
    uow: UnitOfWork,
) -> RecoveryResult:
    """Recover a single stuck run with row-level locking."""
    correlation_id = uuid4()
    prev_value = previous_status.value

    try:
        with uow:
            run = uow.runs.get_by_id_for_update(run_id)
            if run is None or run.is_terminal:
                return RecoveryResult(
                    entity="run",
                    id=str(run_id),
                    previous_status=prev_value,
                    recovery_action="skipped_already_terminal",
                    success=True,
                )

            # Guard: status may have changed since list_stuck ran
            if run.run_status.value not in _STUCK_RUN_STATUSES:
                return RecoveryResult(
                    entity="run",
                    id=str(run_id),
                    previous_status=prev_value,
                    recovery_action="skipped_no_longer_stuck",
                    success=True,
                )

            # Determine recovery action based on current status
            if run.run_status == RunStatus.COMPLETING:
                # Best-effort: try to complete
                try:
                    run.complete()
                    recovery_action = "force_completed"
                except Exception:
                    run.fail(error_summary="Recovery sweep: stuck in completing")
                    recovery_action = "marked_failed"
            elif run.run_status == RunStatus.RUNNING:
                run.fail(error_summary="Recovery sweep: stuck in running")
                recovery_action = "marked_failed"
            else:  # PREPARING
                run.fail(error_summary="Recovery sweep: stuck in preparing")
                recovery_action = "marked_failed"

            uow.runs.save(run)

            # Cancel any active steps belonging to this run
            active_steps = uow.steps.list_active_by_run(run_id)
            for step in active_steps:
                try:
                    step.cancel()
                    uow.steps.save(step)
                except Exception as step_exc:
                    logger.debug("Recovery: could not cancel step %s: %s", step.id, step_exc)

            uow.outbox.write(run_recovered_event(
                run_id=run_id,
                task_id=task_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                previous_status=prev_value,
                recovery_action=recovery_action,
            ))
            uow.commit()

        logger.info("Recovery: run %s (%s → %s)", run_id, prev_value, recovery_action)
        return RecoveryResult(
            entity="run",
            id=str(run_id),
            previous_status=prev_value,
            recovery_action=recovery_action,
            success=True,
        )
    except Exception as exc:
        logger.error("Recovery: run %s reconciliation failed: %s", run_id, exc)
        return RecoveryResult(
            entity="run",
            id=str(run_id),
            previous_status=prev_value,
            recovery_action="reconciliation_failed",
            success=False,
            error=str(exc),
        )


# ── Step recovery ─────────────────────────────────────────────


def _recover_stuck_steps(
    uow: UnitOfWork,
    *,
    step_running_timeout_minutes: int,
) -> list[RecoveryResult]:
    now = datetime.now(timezone.utc)
    stuck_before = now - timedelta(minutes=step_running_timeout_minutes)

    results: list[RecoveryResult] = []

    with uow:
        stuck_steps = uow.steps.list_stuck_for_update(
            stuck_before=stuck_before,
            statuses=_STUCK_STEP_STATUSES,
        )

    for step in stuck_steps:
        result = _recover_single_step(step.id, step.run_id, step.workspace_id, uow)
        results.append(result)

    return results


def _recover_single_step(
    step_id: UUID,
    run_id: UUID,
    workspace_id: UUID,
    uow: UnitOfWork,
) -> RecoveryResult:
    """Recover a single stuck step with row-level locking."""
    correlation_id = uuid4()

    try:
        with uow:
            step = uow.steps.get_by_id_for_update(step_id)
            if step is None or step.is_terminal:
                return RecoveryResult(
                    entity="step",
                    id=str(step_id),
                    previous_status="running",
                    recovery_action="skipped_already_terminal",
                    success=True,
                )

            prev_value = step.step_status.value

            # Guard: status may have changed
            if prev_value not in _STUCK_STEP_STATUSES:
                return RecoveryResult(
                    entity="step",
                    id=str(step_id),
                    previous_status=prev_value,
                    recovery_action="skipped_no_longer_stuck",
                    success=True,
                )
            step.fail(error_detail={
                "code": "RECOVERY_SWEEP",
                "message": "Step stuck in running, recovered by sweep",
            })
            uow.steps.save(step)

            # Need task_id for the event — get from run
            run = uow.runs.get_by_id(run_id)
            task_id = run.task_id if run else None

            if task_id:
                uow.outbox.write(step_recovered_event(
                    step_id=step_id,
                    run_id=run_id,
                    task_id=task_id,
                    workspace_id=workspace_id,
                    correlation_id=correlation_id,
                    previous_status=prev_value,
                    recovery_action="marked_failed",
                ))
            uow.commit()

        logger.info("Recovery: step %s (running → failed)", step_id)
        return RecoveryResult(
            entity="step",
            id=str(step_id),
            previous_status=prev_value,
            recovery_action="marked_failed",
            success=True,
        )
    except Exception as exc:
        logger.error("Recovery: step %s reconciliation failed: %s", step_id, exc)
        return RecoveryResult(
            entity="step",
            id=str(step_id),
            previous_status="running",
            recovery_action="reconciliation_failed",
            success=False,
            error=str(exc),
        )


# ── Task recovery ─────────────────────────────────────────────


def _recover_orphaned_tasks(uow: UnitOfWork) -> list[RecoveryResult]:
    """Find RUNNING tasks whose runs are all terminal and reconcile."""
    results: list[RecoveryResult] = []

    with uow:
        running_tasks = uow.tasks.list_running()

    for task in running_tasks:
        result = _recover_single_task(task.id, task.workspace_id, uow)
        if result is not None:
            results.append(result)

    return results


def _recover_single_task(
    task_id: UUID,
    workspace_id: UUID,
    uow: UnitOfWork,
) -> RecoveryResult | None:
    """Recover a task whose runs are all terminal.

    Returns None if the task still has active runs (not orphaned).
    """
    correlation_id = uuid4()

    try:
        with uow:
            task = uow.tasks.get_by_id(task_id)
            if task is None or task.is_terminal:
                return None

            if task.task_status != TaskStatus.RUNNING:
                return None

            # Check if there are any active runs
            active_runs = uow.runs.list_active_by_task(task_id)
            if active_runs:
                return None  # Task still has work in progress

            # All runs are terminal — determine outcome from latest run
            latest_run = uow.runs.get_latest_by_task(task_id)

            if latest_run is None:
                # RUNNING task with no runs at all — orphaned
                task.fail()
                recovery_action = "marked_failed"
            elif latest_run.run_status == RunStatus.COMPLETED:
                task.complete()
                recovery_action = "marked_completed"
            else:
                # Latest run failed/cancelled/timed_out — conservative: fail the task
                task.fail()
                recovery_action = "marked_failed"

            uow.tasks.save(task)
            uow.outbox.write(task_recovered_event(
                task_id=task_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                previous_status="running",
                recovery_action=recovery_action,
            ))
            uow.commit()

        logger.info("Recovery: task %s (running → %s)", task_id, recovery_action)
        return RecoveryResult(
            entity="task",
            id=str(task_id),
            previous_status="running",
            recovery_action=recovery_action,
            success=True,
        )
    except Exception as exc:
        logger.error("Recovery: task %s reconciliation failed: %s", task_id, exc)
        return RecoveryResult(
            entity="task",
            id=str(task_id),
            previous_status="running",
            recovery_action="reconciliation_failed",
            success=False,
            error=str(exc),
        )
