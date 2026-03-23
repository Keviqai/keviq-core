"""Unit tests for Run domain model and state machine.

Validates all transitions from doc 05, section 2.
"""

import pytest
from uuid import uuid4

from src.domain.run import Run, RunStatus, TriggerType
from src.domain.errors import (
    DomainValidationError,
    ImmutableFieldError,
    InvalidTransitionError,
    TerminalStateError,
)


# ── Fixtures ────────────────────────────────────────────────────

def make_run(**overrides) -> Run:
    defaults = dict(
        task_id=uuid4(),
        workspace_id=uuid4(),
    )
    defaults.update(overrides)
    return Run(**defaults)


def make_run_at(status: RunStatus) -> Run:
    return make_run(run_status=status)


# ── Construction ────────────────────────────────────────────────

class TestRunConstruction:
    def test_defaults(self):
        r = make_run()
        assert r.run_status == RunStatus.QUEUED
        assert r.trigger_type == TriggerType.MANUAL
        assert r.run_config == {}

    def test_negative_duration_rejected(self):
        with pytest.raises(DomainValidationError, match="duration_ms"):
            make_run(duration_ms=-1)

    def test_zero_duration_ok(self):
        r = make_run(duration_ms=0)
        assert r.duration_ms == 0


# ── Valid transitions (doc 05, section 2.3) ─────────────────────

class TestRunValidTransitions:
    def test_queued_to_preparing(self):
        r = make_run_at(RunStatus.QUEUED)
        r.prepare()
        assert r.run_status == RunStatus.PREPARING

    def test_queued_to_cancelled(self):
        r = make_run_at(RunStatus.QUEUED)
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED

    def test_preparing_to_running(self):
        r = make_run_at(RunStatus.PREPARING)
        r.start()
        assert r.run_status == RunStatus.RUNNING
        assert r.started_at is not None

    def test_preparing_to_failed(self):
        r = make_run_at(RunStatus.PREPARING)
        r.fail("config load error")
        assert r.run_status == RunStatus.FAILED
        assert r.error_summary == "config load error"

    def test_preparing_to_cancelled(self):
        r = make_run_at(RunStatus.PREPARING)
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED

    def test_running_to_waiting_approval(self):
        r = make_run_at(RunStatus.RUNNING)
        r.request_approval()
        assert r.run_status == RunStatus.WAITING_APPROVAL

    def test_running_to_completing(self):
        r = make_run_at(RunStatus.RUNNING)
        r.begin_completing()
        assert r.run_status == RunStatus.COMPLETING

    def test_running_to_failed(self):
        r = make_run_at(RunStatus.RUNNING)
        r.fail()
        assert r.run_status == RunStatus.FAILED

    def test_running_to_cancelled(self):
        r = make_run_at(RunStatus.RUNNING)
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED

    def test_running_to_timed_out(self):
        r = make_run_at(RunStatus.RUNNING)
        r.time_out()
        assert r.run_status == RunStatus.TIMED_OUT

    def test_waiting_approval_to_running(self):
        r = make_run_at(RunStatus.WAITING_APPROVAL)
        r.approve()
        assert r.run_status == RunStatus.RUNNING

    def test_waiting_approval_to_cancelled(self):
        r = make_run_at(RunStatus.WAITING_APPROVAL)
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED

    def test_completing_to_completed(self):
        r = make_run_at(RunStatus.COMPLETING)
        r.complete()
        assert r.run_status == RunStatus.COMPLETED
        assert r.completed_at is not None

    def test_completing_to_failed(self):
        r = make_run_at(RunStatus.COMPLETING)
        r.fail("artifact write error")
        assert r.run_status == RunStatus.FAILED

    def test_timed_out_to_cancelled(self):
        r = make_run_at(RunStatus.TIMED_OUT)
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED


# ── Invalid transitions ────────────────────────────────────────

class TestRunInvalidTransitions:
    def test_queued_cannot_start(self):
        r = make_run_at(RunStatus.QUEUED)
        with pytest.raises(InvalidTransitionError):
            r.start()

    def test_preparing_cannot_complete(self):
        r = make_run_at(RunStatus.PREPARING)
        with pytest.raises(InvalidTransitionError):
            r.complete()

    def test_failed_no_resume(self):
        """Doc 05, section 2.7: Run failed cannot be resumed."""
        r = make_run_at(RunStatus.FAILED)
        with pytest.raises(TerminalStateError):
            r.start()

    def test_cancelled_no_resume(self):
        r = make_run_at(RunStatus.CANCELLED)
        with pytest.raises(TerminalStateError):
            r.prepare()

    def test_completed_is_terminal(self):
        r = make_run_at(RunStatus.COMPLETED)
        with pytest.raises(TerminalStateError):
            r.fail()


# ── Config immutability (doc 05, section 2.5) ──────────────────

class TestRunConfigImmutability:
    def test_config_mutable_in_queued(self):
        r = make_run_at(RunStatus.QUEUED)
        r.update_config({"model": "claude-3"})
        assert r.run_config == {"model": "claude-3"}

    def test_config_locked_after_prepare(self):
        r = make_run_at(RunStatus.QUEUED)
        r.prepare()
        with pytest.raises(ImmutableFieldError, match="run_config"):
            r.update_config({"model": "gpt-4"})

    def test_config_locked_on_reconstitution(self):
        r = make_run(run_status=RunStatus.RUNNING)
        with pytest.raises(ImmutableFieldError):
            r.update_config({})


# ── Terminal state checks ───────────────────────────────────────

class TestRunTerminal:
    def test_terminal_states(self):
        for status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            r = make_run_at(status)
            assert r.is_terminal is True

    def test_non_terminal_states(self):
        for status in (RunStatus.QUEUED, RunStatus.PREPARING, RunStatus.RUNNING,
                       RunStatus.WAITING_APPROVAL, RunStatus.COMPLETING):
            r = make_run_at(status)
            assert r.is_terminal is False

    def test_timed_out_is_not_terminal(self):
        """timed_out can still transition to cancelled."""
        r = make_run_at(RunStatus.TIMED_OUT)
        assert r.is_terminal is False


# ── Side effects ────────────────────────────────────────────────

class TestRunSideEffects:
    def test_start_sets_started_at(self):
        r = make_run_at(RunStatus.PREPARING)
        assert r.started_at is None
        r.start()
        assert r.started_at is not None

    def test_complete_sets_completed_at_and_duration(self):
        r = make_run_at(RunStatus.PREPARING)
        r.start()
        r.begin_completing()
        r.complete()
        assert r.completed_at is not None
        assert r.duration_ms is not None
        assert r.duration_ms >= 0

    def test_fail_sets_error_summary(self):
        r = make_run_at(RunStatus.RUNNING)
        r.fail("boom")
        assert r.error_summary == "boom"

    def test_cancel_sets_completed_at(self):
        r = make_run_at(RunStatus.RUNNING)
        r.cancel()
        assert r.completed_at is not None

    def test_time_out_sets_completed_at(self):
        r = make_run_at(RunStatus.RUNNING)
        r.time_out()
        assert r.completed_at is not None


# ── Full lifecycle ──────────────────────────────────────────────

class TestRunFullLifecycle:
    def test_happy_path(self):
        r = make_run()
        r.prepare()
        r.start()
        r.begin_completing()
        r.complete()
        assert r.run_status == RunStatus.COMPLETED

    def test_fail_during_preparing(self):
        r = make_run()
        r.prepare()
        r.fail("secret load error")
        assert r.run_status == RunStatus.FAILED
        assert r.is_terminal is True

    def test_approval_flow(self):
        r = make_run()
        r.prepare()
        r.start()
        r.request_approval()
        r.approve()
        r.begin_completing()
        r.complete()
        assert r.run_status == RunStatus.COMPLETED

    def test_timeout_then_cancel(self):
        r = make_run()
        r.prepare()
        r.start()
        r.time_out()
        r.cancel()
        assert r.run_status == RunStatus.CANCELLED
