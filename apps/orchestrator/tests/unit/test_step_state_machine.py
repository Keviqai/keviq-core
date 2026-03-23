"""Unit tests for Step domain model and state machine.

Validates all transitions from doc 05, section 3.
"""

import pytest
from uuid import uuid4

from src.domain.step import Step, StepStatus, StepType
from src.domain.errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


# ── Fixtures ────────────────────────────────────────────────────

def make_step(**overrides) -> Step:
    defaults = dict(
        run_id=uuid4(),
        workspace_id=uuid4(),
        sequence=1,
    )
    defaults.update(overrides)
    return Step(**defaults)


def make_step_at(status: StepStatus) -> Step:
    return make_step(step_status=status)


# ── Construction ────────────────────────────────────────────────

class TestStepConstruction:
    def test_defaults(self):
        s = make_step()
        assert s.step_status == StepStatus.PENDING
        assert s.step_type == StepType.AGENT_INVOCATION
        assert s.sequence == 1

    def test_zero_sequence_rejected(self):
        with pytest.raises(DomainValidationError, match="sequence"):
            make_step(sequence=0)

    def test_negative_sequence_rejected(self):
        with pytest.raises(DomainValidationError, match="sequence"):
            make_step(sequence=-1)

    def test_custom_step_type(self):
        s = make_step(step_type=StepType.APPROVAL_GATE)
        assert s.step_type == StepType.APPROVAL_GATE


# ── Valid transitions (doc 05, section 3.3) ─────────────────────

class TestStepValidTransitions:
    def test_pending_to_running(self):
        s = make_step_at(StepStatus.PENDING)
        s.start(input_snapshot={"prompt": "hello"})
        assert s.step_status == StepStatus.RUNNING
        assert s.started_at is not None
        assert s.input_snapshot == {"prompt": "hello"}

    def test_pending_to_skipped(self):
        s = make_step_at(StepStatus.PENDING)
        s.skip()
        assert s.step_status == StepStatus.SKIPPED

    def test_pending_to_cancelled(self):
        s = make_step_at(StepStatus.PENDING)
        s.cancel()
        assert s.step_status == StepStatus.CANCELLED

    def test_running_to_waiting_approval(self):
        s = make_step_at(StepStatus.RUNNING)
        s.request_approval()
        assert s.step_status == StepStatus.WAITING_APPROVAL

    def test_running_to_blocked(self):
        s = make_step_at(StepStatus.RUNNING)
        s.block()
        assert s.step_status == StepStatus.BLOCKED

    def test_running_to_completed(self):
        s = make_step_at(StepStatus.RUNNING)
        s.complete(output_snapshot={"result": "ok"})
        assert s.step_status == StepStatus.COMPLETED
        assert s.output_snapshot == {"result": "ok"}
        assert s.completed_at is not None

    def test_running_to_failed(self):
        s = make_step_at(StepStatus.RUNNING)
        s.fail(error_detail={"code": "TIMEOUT"})
        assert s.step_status == StepStatus.FAILED
        assert s.error_detail == {"code": "TIMEOUT"}

    def test_running_to_cancelled(self):
        s = make_step_at(StepStatus.RUNNING)
        s.cancel()
        assert s.step_status == StepStatus.CANCELLED

    def test_waiting_approval_to_running(self):
        s = make_step_at(StepStatus.WAITING_APPROVAL)
        s.approve()
        assert s.step_status == StepStatus.RUNNING

    def test_waiting_approval_to_cancelled(self):
        s = make_step_at(StepStatus.WAITING_APPROVAL)
        s.cancel()
        assert s.step_status == StepStatus.CANCELLED

    def test_blocked_to_running(self):
        s = make_step_at(StepStatus.BLOCKED)
        s.unblock()
        assert s.step_status == StepStatus.RUNNING

    def test_blocked_to_failed(self):
        s = make_step_at(StepStatus.BLOCKED)
        s.fail(error_detail={"reason": "dependency timeout"})
        assert s.step_status == StepStatus.FAILED

    def test_blocked_to_cancelled(self):
        s = make_step_at(StepStatus.BLOCKED)
        s.cancel()
        assert s.step_status == StepStatus.CANCELLED


# ── Invalid transitions ────────────────────────────────────────

class TestStepInvalidTransitions:
    def test_pending_cannot_complete(self):
        s = make_step_at(StepStatus.PENDING)
        with pytest.raises(InvalidTransitionError):
            s.complete(output_snapshot={})

    def test_pending_cannot_fail(self):
        s = make_step_at(StepStatus.PENDING)
        with pytest.raises(InvalidTransitionError):
            s.fail()

    def test_pending_cannot_block(self):
        s = make_step_at(StepStatus.PENDING)
        with pytest.raises(InvalidTransitionError):
            s.block()

    def test_waiting_approval_cannot_complete(self):
        s = make_step_at(StepStatus.WAITING_APPROVAL)
        with pytest.raises(InvalidTransitionError):
            s.complete(output_snapshot={})

    def test_blocked_cannot_skip(self):
        s = make_step_at(StepStatus.BLOCKED)
        with pytest.raises(InvalidTransitionError):
            s.skip()


# ── Terminal states ─────────────────────────────────────────────

class TestStepTerminalStates:
    @pytest.mark.parametrize("status", [
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.CANCELLED,
    ])
    def test_terminal_cannot_transition(self, status: StepStatus):
        s = make_step_at(status)
        with pytest.raises((TerminalStateError, InvalidTransitionError)):
            s.start()

    @pytest.mark.parametrize("status", [
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.CANCELLED,
    ])
    def test_terminal_is_terminal(self, status: StepStatus):
        s = make_step_at(status)
        assert s.is_terminal is True

    def test_active_states(self):
        for status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.WAITING_APPROVAL, StepStatus.BLOCKED):
            s = make_step_at(status)
            assert s.is_active is True


# ── waiting_approval vs blocked distinction (doc 05, section 3.2) ──

class TestWaitingVsBlocked:
    def test_both_are_distinct_states(self):
        assert StepStatus.WAITING_APPROVAL != StepStatus.BLOCKED

    def test_waiting_approval_resolved_by_approve(self):
        """waiting_approval → running via human approval."""
        s = make_step_at(StepStatus.WAITING_APPROVAL)
        s.approve()
        assert s.step_status == StepStatus.RUNNING

    def test_blocked_resolved_by_unblock(self):
        """blocked → running via dependency resolution."""
        s = make_step_at(StepStatus.BLOCKED)
        s.unblock()
        assert s.step_status == StepStatus.RUNNING

    def test_waiting_cannot_unblock(self):
        """waiting_approval is not blocked — unblock must be rejected."""
        s = make_step_at(StepStatus.WAITING_APPROVAL)
        with pytest.raises(InvalidTransitionError, match="unblock only valid from blocked"):
            s.unblock()

    def test_blocked_cannot_approve(self):
        """blocked is not waiting_approval — approve must be rejected."""
        s = make_step_at(StepStatus.BLOCKED)
        with pytest.raises(InvalidTransitionError, match="approve only valid from waiting_approval"):
            s.approve()

    def test_start_only_from_pending(self):
        """start() is restricted to pending state."""
        for status in (StepStatus.WAITING_APPROVAL, StepStatus.BLOCKED, StepStatus.RUNNING):
            s = make_step_at(status)
            with pytest.raises(InvalidTransitionError, match="start only valid from pending"):
                s.start()


# ── Side effects ────────────────────────────────────────────────

class TestStepSideEffects:
    def test_start_from_pending_sets_started_at(self):
        s = make_step_at(StepStatus.PENDING)
        assert s.started_at is None
        s.start()
        assert s.started_at is not None

    def test_unblock_preserves_started_at(self):
        """Unblocking from blocked should not overwrite original started_at."""
        s = make_step_at(StepStatus.PENDING)
        s.start()
        original = s.started_at
        s.block()
        s.unblock()
        assert s.started_at == original

    def test_skip_sets_completed_at(self):
        s = make_step_at(StepStatus.PENDING)
        s.skip()
        assert s.completed_at is not None

    def test_complete_sets_output_snapshot(self):
        s = make_step_at(StepStatus.RUNNING)
        s.complete(output_snapshot={"files": ["main.py"]})
        assert s.output_snapshot == {"files": ["main.py"]}

    def test_fail_sets_error_detail(self):
        s = make_step_at(StepStatus.RUNNING)
        s.fail(error_detail={"message": "oom"})
        assert s.error_detail == {"message": "oom"}

    def test_cancel_sets_completed_at(self):
        s = make_step_at(StepStatus.RUNNING)
        s.cancel()
        assert s.completed_at is not None


# ── Full lifecycle ──────────────────────────────────────────────

class TestStepFullLifecycle:
    def test_happy_path(self):
        s = make_step()
        s.start(input_snapshot={"cmd": "run"})
        s.complete(output_snapshot={"exit_code": 0})
        assert s.step_status == StepStatus.COMPLETED

    def test_approval_gate(self):
        s = make_step(step_type=StepType.APPROVAL_GATE)
        s.start()
        s.request_approval()
        s.approve()
        s.complete(output_snapshot={"approved": True})
        assert s.step_status == StepStatus.COMPLETED

    def test_blocked_then_resolved(self):
        s = make_step()
        s.start()
        s.block()
        s.unblock()
        s.complete(output_snapshot={"result": "done"})
        assert s.step_status == StepStatus.COMPLETED

    def test_blocked_then_failed(self):
        s = make_step()
        s.start()
        s.block()
        s.fail(error_detail={"reason": "dependency failed"})
        assert s.step_status == StepStatus.FAILED

    def test_condition_skip(self):
        s = make_step(step_type=StepType.CONDITION)
        s.skip()
        assert s.step_status == StepStatus.SKIPPED
        assert s.is_terminal is True
