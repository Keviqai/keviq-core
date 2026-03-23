"""Unit tests for Sandbox domain entity and state machine."""

from __future__ import annotations

import uuid

import pytest

from src.domain.errors import InvalidTransitionError, TerminalStateError
from src.domain.sandbox import (
    Sandbox,
    SandboxStatus,
    SandboxType,
    TerminationReason,
)


def _make_sandbox(**overrides) -> Sandbox:
    defaults = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "step_id": uuid.uuid4(),
        "agent_invocation_id": uuid.uuid4(),
        "sandbox_type": SandboxType.CONTAINER,
    }
    defaults.update(overrides)
    return Sandbox(**defaults)


# ── Construction ──────────────────────────────────────────────


class TestSandboxConstruction:
    def test_default_status_is_provisioning(self):
        s = _make_sandbox()
        assert s.sandbox_status == SandboxStatus.PROVISIONING

    def test_timestamps_populated(self):
        s = _make_sandbox()
        assert s.created_at is not None
        assert s.updated_at is not None

    def test_policy_snapshot_default_empty_dict(self):
        s = _make_sandbox()
        assert s.policy_snapshot == {}
        assert s.resource_limits == {}
        assert s.network_egress_policy == {}

    def test_no_terminal_fields_initially(self):
        s = _make_sandbox()
        assert s.started_at is None
        assert s.terminated_at is None
        assert s.termination_reason is None
        assert s.error_detail is None

    def test_equality_by_id(self):
        sid = uuid.uuid4()
        s1 = _make_sandbox(id=sid)
        s2 = _make_sandbox(id=sid)
        assert s1 == s2
        assert hash(s1) == hash(s2)

    def test_inequality_different_id(self):
        s1 = _make_sandbox()
        s2 = _make_sandbox()
        assert s1 != s2


# ── Happy path transitions ────────────────────────────────────


class TestSandboxHappyPath:
    def test_provisioning_to_ready(self):
        s = _make_sandbox()
        prev = s.mark_ready()
        assert prev == SandboxStatus.PROVISIONING
        assert s.sandbox_status == SandboxStatus.READY
        assert s.started_at is not None

    def test_ready_to_executing(self):
        s = _make_sandbox()
        s.mark_ready()
        prev = s.mark_executing()
        assert prev == SandboxStatus.READY
        assert s.sandbox_status == SandboxStatus.EXECUTING

    def test_executing_to_idle(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        prev = s.mark_idle()
        assert prev == SandboxStatus.EXECUTING
        assert s.sandbox_status == SandboxStatus.IDLE

    def test_idle_to_executing_again(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_idle()
        prev = s.mark_executing()
        assert prev == SandboxStatus.IDLE
        assert s.sandbox_status == SandboxStatus.EXECUTING

    def test_full_happy_path(self):
        """provisioning → ready → executing → idle → terminating → terminated"""
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_idle()
        s.mark_terminating(TerminationReason.COMPLETED)
        s.mark_terminated()
        assert s.sandbox_status == SandboxStatus.TERMINATED
        assert s.terminated_at is not None
        assert s.termination_reason == TerminationReason.COMPLETED
        assert s.is_terminal


# ── Failure transitions ───────────────────────────────────────


class TestSandboxFailurePaths:
    def test_provisioning_to_failed(self):
        s = _make_sandbox()
        prev = s.mark_failed({"code": "DOCKER_ERROR", "message": "pull failed"})
        assert prev == SandboxStatus.PROVISIONING
        assert s.sandbox_status == SandboxStatus.FAILED
        assert s.error_detail["code"] == "DOCKER_ERROR"

    def test_executing_to_failed(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_failed()
        assert s.sandbox_status == SandboxStatus.FAILED

    def test_failed_to_terminating(self):
        s = _make_sandbox()
        s.mark_failed()
        s.mark_terminating(TerminationReason.ERROR)
        assert s.sandbox_status == SandboxStatus.TERMINATING
        assert s.termination_reason == TerminationReason.ERROR

    def test_failed_then_terminated(self):
        s = _make_sandbox()
        s.mark_failed()
        s.mark_terminating(TerminationReason.ERROR)
        s.mark_terminated()
        assert s.sandbox_status == SandboxStatus.TERMINATED
        assert s.is_terminal


# ── Termination from various states ───────────────────────────


class TestSandboxTermination:
    def test_ready_to_terminating(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_terminating(TerminationReason.MANUAL)
        assert s.sandbox_status == SandboxStatus.TERMINATING

    def test_executing_to_terminating(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_terminating(TerminationReason.TIMEOUT)
        assert s.sandbox_status == SandboxStatus.TERMINATING

    def test_idle_to_terminating(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_idle()
        s.mark_terminating()
        assert s.sandbox_status == SandboxStatus.TERMINATING


# ── Invalid transitions ───────────────────────────────────────


class TestSandboxInvalidTransitions:
    def test_terminated_is_terminal(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_terminating()
        s.mark_terminated()
        with pytest.raises(TerminalStateError):
            s.mark_ready()

    def test_provisioning_to_executing_blocked(self):
        s = _make_sandbox()
        with pytest.raises(InvalidTransitionError):
            s.mark_executing()

    def test_provisioning_to_idle_blocked(self):
        s = _make_sandbox()
        with pytest.raises(InvalidTransitionError):
            s.mark_idle()

    def test_provisioning_to_terminating_blocked(self):
        s = _make_sandbox()
        with pytest.raises(InvalidTransitionError):
            s.mark_terminating()

    def test_ready_to_idle_blocked(self):
        s = _make_sandbox()
        s.mark_ready()
        with pytest.raises(InvalidTransitionError):
            s.mark_idle()

    def test_idle_to_failed_blocked(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_executing()
        s.mark_idle()
        with pytest.raises(InvalidTransitionError):
            s.mark_failed()

    def test_terminated_to_anything_blocked(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_terminating()
        s.mark_terminated()
        for method in [s.mark_ready, s.mark_executing, s.mark_idle]:
            with pytest.raises(TerminalStateError):
                method()


# ── Properties ────────────────────────────────────────────────


class TestSandboxProperties:
    def test_is_terminal_false_when_active(self):
        s = _make_sandbox()
        assert not s.is_terminal
        assert s.is_active

    def test_is_terminal_true_when_terminated(self):
        s = _make_sandbox()
        s.mark_ready()
        s.mark_terminating()
        s.mark_terminated()
        assert s.is_terminal
        assert not s.is_active

    def test_is_active_false_when_failed(self):
        s = _make_sandbox()
        s.mark_failed()
        assert not s.is_active
        # Failed is not in _SANDBOX_TERMINAL (can still transition to terminating)
        assert not s.is_terminal

    def test_updated_at_changes_on_transition(self):
        s = _make_sandbox()
        original = s.updated_at
        s.mark_ready()
        assert s.updated_at >= original
