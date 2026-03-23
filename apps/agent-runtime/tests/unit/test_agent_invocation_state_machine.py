"""Unit tests for AgentInvocation domain model and state machine.

Validates all transitions from doc 05, section 4 + PR14 extensions.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from src.domain.agent_invocation import AgentInvocation, InvocationStatus
from src.domain.errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


# ── Fixtures ────────────────────────────────────────────────────

def make_invocation(**overrides) -> AgentInvocation:
    defaults = dict(
        id=uuid4(),
        step_id=uuid4(),
        run_id=uuid4(),
        task_id=uuid4(),
        workspace_id=uuid4(),
        correlation_id=uuid4(),
        agent_id="reasoning-agent-v1",
        model_id="claude-sonnet",
    )
    defaults.update(overrides)
    return AgentInvocation(**defaults)


def make_invocation_at(status: InvocationStatus) -> AgentInvocation:
    return make_invocation(invocation_status=status)


# ── Construction ────────────────────────────────────────────────

class TestAgentInvocationConstruction:
    def test_defaults(self):
        inv = make_invocation()
        assert inv.invocation_status == InvocationStatus.INITIALIZING
        assert inv.started_at is None
        assert inv.completed_at is None
        assert inv.prompt_tokens is None
        assert inv.completion_tokens is None
        assert inv.total_cost_usd is None
        assert inv.created_at is not None

    def test_blank_agent_id_rejected(self):
        with pytest.raises(DomainValidationError, match="agent_id"):
            make_invocation(agent_id="")

    def test_blank_model_id_rejected(self):
        with pytest.raises(DomainValidationError, match="model_id"):
            make_invocation(model_id="  ")

    def test_identity_by_id(self):
        shared_id = uuid4()
        a = make_invocation(id=shared_id)
        b = make_invocation(id=shared_id)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_ids_not_equal(self):
        a = make_invocation()
        b = make_invocation()
        assert a != b


# ── Happy path: initializing → starting → running → completed ──

class TestHappyPath:
    def test_full_happy_path(self):
        inv = make_invocation()
        inv.mark_starting()
        assert inv.invocation_status == InvocationStatus.STARTING

        inv.mark_running(input_messages=[{"role": "user", "content": "summarize"}])
        assert inv.invocation_status == InvocationStatus.RUNNING
        assert inv.started_at is not None
        assert inv.input_messages == [{"role": "user", "content": "summarize"}]

        inv.mark_completed(
            output_messages=[{"role": "assistant", "content": "summary"}],
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.001"),
        )
        assert inv.invocation_status == InvocationStatus.COMPLETED
        assert inv.completed_at is not None
        assert inv.prompt_tokens == 100
        assert inv.completion_tokens == 50
        assert inv.total_cost_usd == Decimal("0.001")
        assert inv.output_messages == [{"role": "assistant", "content": "summary"}]

    def test_duration_ms_computed(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running()
        inv.mark_completed()
        assert inv.duration_ms is not None
        assert inv.duration_ms >= 0


# ── Valid transitions ────────────────────────────────────────────

class TestValidTransitions:
    def test_initializing_to_starting(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        inv.mark_starting()
        assert inv.invocation_status == InvocationStatus.STARTING

    def test_initializing_to_cancelled(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        inv.mark_cancelled()
        assert inv.invocation_status == InvocationStatus.CANCELLED

    def test_initializing_to_failed(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        inv.mark_failed(error_detail={"code": "INIT_ERROR"})
        assert inv.invocation_status == InvocationStatus.FAILED

    def test_starting_to_running(self):
        inv = make_invocation_at(InvocationStatus.STARTING)
        inv.mark_running()
        assert inv.invocation_status == InvocationStatus.RUNNING

    def test_starting_to_failed(self):
        inv = make_invocation_at(InvocationStatus.STARTING)
        inv.mark_failed()
        assert inv.invocation_status == InvocationStatus.FAILED

    def test_starting_to_cancelled(self):
        inv = make_invocation_at(InvocationStatus.STARTING)
        inv.mark_cancelled()
        assert inv.invocation_status == InvocationStatus.CANCELLED

    def test_running_to_completed(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_completed()
        assert inv.invocation_status == InvocationStatus.COMPLETED

    def test_running_to_failed(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_failed(error_detail={"code": "MODEL_ERROR"})
        assert inv.invocation_status == InvocationStatus.FAILED
        assert inv.error_detail == {"code": "MODEL_ERROR"}

    def test_running_to_timed_out(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_timed_out(error_detail={"timeout_ms": 30000})
        assert inv.invocation_status == InvocationStatus.TIMED_OUT

    def test_running_to_cancelled(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_cancelled()
        assert inv.invocation_status == InvocationStatus.CANCELLED

    def test_running_to_interrupted(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_interrupted()
        assert inv.invocation_status == InvocationStatus.INTERRUPTED

    def test_running_to_waiting_human(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_waiting_human()
        assert inv.invocation_status == InvocationStatus.WAITING_HUMAN

    def test_running_to_waiting_tool(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_waiting_tool()
        assert inv.invocation_status == InvocationStatus.WAITING_TOOL

    def test_waiting_human_to_running(self):
        inv = make_invocation_at(InvocationStatus.WAITING_HUMAN)
        inv.resume_from_wait()
        assert inv.invocation_status == InvocationStatus.RUNNING

    def test_waiting_tool_to_running(self):
        inv = make_invocation_at(InvocationStatus.WAITING_TOOL)
        inv.resume_from_wait()
        assert inv.invocation_status == InvocationStatus.RUNNING

    def test_waiting_human_to_interrupted(self):
        inv = make_invocation_at(InvocationStatus.WAITING_HUMAN)
        inv.mark_interrupted()
        assert inv.invocation_status == InvocationStatus.INTERRUPTED

    def test_waiting_human_to_cancelled(self):
        inv = make_invocation_at(InvocationStatus.WAITING_HUMAN)
        inv.mark_cancelled()
        assert inv.invocation_status == InvocationStatus.CANCELLED

    def test_waiting_tool_to_failed(self):
        inv = make_invocation_at(InvocationStatus.WAITING_TOOL)
        inv.mark_failed()
        assert inv.invocation_status == InvocationStatus.FAILED

    def test_waiting_tool_to_cancelled(self):
        inv = make_invocation_at(InvocationStatus.WAITING_TOOL)
        inv.mark_cancelled()
        assert inv.invocation_status == InvocationStatus.CANCELLED

    def test_waiting_tool_to_interrupted(self):
        inv = make_invocation_at(InvocationStatus.WAITING_TOOL)
        inv.mark_interrupted()
        assert inv.invocation_status == InvocationStatus.INTERRUPTED

    def test_failed_to_compensating(self):
        inv = make_invocation_at(InvocationStatus.FAILED)
        inv.mark_compensating()
        assert inv.invocation_status == InvocationStatus.COMPENSATING

    def test_timed_out_to_compensating(self):
        inv = make_invocation_at(InvocationStatus.TIMED_OUT)
        inv.mark_compensating()
        assert inv.invocation_status == InvocationStatus.COMPENSATING

    def test_interrupted_to_compensating(self):
        inv = make_invocation_at(InvocationStatus.INTERRUPTED)
        inv.mark_compensating()
        assert inv.invocation_status == InvocationStatus.COMPENSATING

    def test_compensating_to_compensated(self):
        inv = make_invocation_at(InvocationStatus.COMPENSATING)
        inv.mark_compensated()
        assert inv.invocation_status == InvocationStatus.COMPENSATED

    def test_compensating_to_failed(self):
        inv = make_invocation_at(InvocationStatus.COMPENSATING)
        inv.mark_failed(error_detail={"code": "COMPENSATION_FAILED"})
        assert inv.invocation_status == InvocationStatus.FAILED


# ── Invalid transitions ──────────────────────────────────────────

class TestInvalidTransitions:
    def test_initializing_cannot_complete(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        with pytest.raises(InvalidTransitionError):
            inv.mark_completed()

    def test_initializing_cannot_run(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        with pytest.raises(InvalidTransitionError):
            inv.mark_running()

    def test_starting_cannot_complete(self):
        inv = make_invocation_at(InvocationStatus.STARTING)
        with pytest.raises(InvalidTransitionError):
            inv.mark_completed()

    def test_running_cannot_start(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        with pytest.raises(InvalidTransitionError):
            inv.mark_starting()

    def test_completed_cannot_fail(self):
        inv = make_invocation_at(InvocationStatus.COMPLETED)
        with pytest.raises(TerminalStateError):
            inv.mark_failed()

    def test_resume_from_wait_only_from_waiting_states(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        with pytest.raises(InvalidTransitionError, match="resume_from_wait"):
            inv.resume_from_wait()

    def test_initializing_cannot_compensate(self):
        inv = make_invocation_at(InvocationStatus.INITIALIZING)
        with pytest.raises(InvalidTransitionError):
            inv.mark_compensating()


# ── Terminal states ──────────────────────────────────────────────

class TestTerminalStates:
    @pytest.mark.parametrize("status", [
        InvocationStatus.COMPLETED,
        InvocationStatus.CANCELLED,
        InvocationStatus.COMPENSATED,
    ])
    def test_terminal_cannot_transition(self, status: InvocationStatus):
        inv = make_invocation_at(status)
        with pytest.raises((TerminalStateError, InvalidTransitionError)):
            inv.mark_starting()

    @pytest.mark.parametrize("status", [
        InvocationStatus.COMPLETED,
        InvocationStatus.CANCELLED,
        InvocationStatus.COMPENSATED,
    ])
    def test_terminal_is_terminal(self, status: InvocationStatus):
        inv = make_invocation_at(status)
        assert inv.is_terminal is True

    def test_non_terminal_failure_states(self):
        """failed/timed_out/interrupted are NOT terminal — they can compensate."""
        for status in (InvocationStatus.FAILED, InvocationStatus.TIMED_OUT, InvocationStatus.INTERRUPTED):
            inv = make_invocation_at(status)
            assert inv.is_terminal is False

    def test_active_states(self):
        for status in (
            InvocationStatus.INITIALIZING,
            InvocationStatus.STARTING,
            InvocationStatus.RUNNING,
            InvocationStatus.WAITING_HUMAN,
            InvocationStatus.WAITING_TOOL,
        ):
            inv = make_invocation_at(status)
            assert inv.is_active is True


# ── Side effects ─────────────────────────────────────────────────

class TestSideEffects:
    def test_mark_running_sets_started_at_once(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running()
        first_start = inv.started_at
        assert first_start is not None

        # Simulate wait → resume: started_at should NOT change
        inv.mark_waiting_tool()
        inv.resume_from_wait()
        assert inv.started_at == first_start

    def test_mark_completed_sets_completed_at(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        assert inv.completed_at is None
        inv.mark_completed()
        assert inv.completed_at is not None

    def test_mark_failed_sets_completed_at(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_failed()
        assert inv.completed_at is not None

    def test_mark_timed_out_sets_completed_at(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_timed_out()
        assert inv.completed_at is not None

    def test_mark_cancelled_sets_completed_at(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_cancelled()
        assert inv.completed_at is not None

    def test_mark_interrupted_sets_completed_at(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_interrupted()
        assert inv.completed_at is not None

    def test_mark_completed_records_usage(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_completed(
            prompt_tokens=200,
            completion_tokens=100,
            total_cost_usd=Decimal("0.005"),
        )
        assert inv.prompt_tokens == 200
        assert inv.completion_tokens == 100
        assert inv.total_cost_usd == Decimal("0.005")

    def test_mark_completed_records_tool_calls(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.mark_completed(tool_calls=[{"name": "search", "args": {}}])
        assert inv.tool_calls == [{"name": "search", "args": {}}]

    def test_duration_ms_none_when_incomplete(self):
        inv = make_invocation()
        assert inv.duration_ms is None

    def test_duration_ms_none_when_started_only(self):
        inv = make_invocation_at(InvocationStatus.RUNNING)
        inv.started_at = inv.created_at  # Manually set for test
        assert inv.duration_ms is None  # No completed_at


# ── Full lifecycle scenarios ─────────────────────────────────────

class TestFullLifecycle:
    def test_happy_path_with_output(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running(input_messages=[{"role": "user", "content": "classify this"}])
        inv.mark_completed(
            output_messages=[{"role": "assistant", "content": "category: A"}],
            prompt_tokens=50,
            completion_tokens=10,
        )
        assert inv.is_terminal is True
        assert not inv.is_active

    def test_failure_then_compensation(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running()
        inv.mark_failed(error_detail={"code": "PROVIDER_DOWN"})
        assert not inv.is_terminal
        inv.mark_compensating()
        inv.mark_compensated()
        assert inv.is_terminal

    def test_timeout_then_compensation(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running()
        inv.mark_timed_out(error_detail={"timeout_ms": 30000})
        inv.mark_compensating()
        inv.mark_compensated()
        assert inv.is_terminal

    def test_interruption_during_wait(self):
        inv = make_invocation()
        inv.mark_starting()
        inv.mark_running()
        inv.mark_waiting_human()
        inv.mark_interrupted()
        assert inv.invocation_status == InvocationStatus.INTERRUPTED
        assert inv.completed_at is not None

    def test_cancellation_before_start(self):
        inv = make_invocation()
        inv.mark_cancelled()
        assert inv.is_terminal
        assert inv.completed_at is not None
