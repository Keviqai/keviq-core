"""Unit tests for tool approval gate in ExecuteInvocationHandler (O5-S1).

Tests:
- Gated tool → invocation enters WAITING_HUMAN
- Allowed tool → normal execution (no regression)
- Mode=none → no gate check (backward compat)
- Pending tool context persisted
- Approval service called for gated tools
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.application.approval_gate import check_tool_approval_gate
from src.domain.agent_invocation import AgentInvocation, InvocationStatus
from src.domain.execution_contracts import ExecutionRequest, ExecutionStatus, ModelProfile


def _make_request(**overrides) -> ExecutionRequest:
    defaults = {
        "agent_invocation_id": uuid4(),
        "workspace_id": uuid4(),
        "task_id": uuid4(),
        "run_id": uuid4(),
        "step_id": uuid4(),
        "correlation_id": uuid4(),
        "agent_id": "test-agent",
        "model_profile": ModelProfile(model_alias="test-model"),
        "instruction": "test instruction",
        "input_payload": {"sandbox_id": str(uuid4())},
        "timeout_ms": 120000,
    }
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


def _make_gate_deps(*, tool_approval_service=None):
    """Return (uow, tool_approval_service) for check_tool_approval_gate calls."""
    uow = MagicMock()
    return uow, tool_approval_service


class TestToolApprovalGateInHandler(unittest.TestCase):
    """Test _check_tool_approval_gate method."""

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "gate"})
    def test_shell_exec_gated_transitions_to_waiting_human(self):
        """shell.exec in gate mode → WAITING_HUMAN."""
        approval_service = MagicMock()
        approval_service.request_tool_approval.return_value = {"id": str(uuid4())}
        uow, _ = _make_gate_deps(tool_approval_service=approval_service)
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )
        invocation.started_at = invocation.created_at

        tool_calls = [
            {"id": "tc1", "function": {"name": "shell.exec", "arguments": '{"code": "ls -la"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={"output_text": "Let me run ls"},
            tool_approval_service=approval_service,
        )

        # Should return a result (not None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, ExecutionStatus.WAITING_HUMAN)
        self.assertEqual(result.output_payload["waiting_reason"], "tool_approval_required")
        self.assertEqual(result.output_payload["gated_tool"], "shell.exec")

        # Invocation should be in WAITING_HUMAN
        self.assertEqual(invocation.invocation_status, InvocationStatus.WAITING_HUMAN)

        # Pending tool context should be set
        self.assertIsNotNone(invocation.pending_tool_context)
        self.assertEqual(invocation.pending_tool_context["gated_tool_name"], "shell.exec")
        self.assertEqual(len(invocation.pending_tool_context["tool_calls"]), 1)

        # Approval service should have been called
        approval_service.request_tool_approval.assert_called_once()

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "none"})
    def test_mode_none_allows_all_tools(self):
        """mode=none → all tools allowed, no gate check."""
        uow, _ = _make_gate_deps()
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )

        tool_calls = [
            {"id": "tc1", "function": {"name": "shell.exec", "arguments": '{"code": "rm -rf /"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={},
            tool_approval_service=None,
        )

        # Should return None (allow)
        self.assertIsNone(result)
        # Invocation should still be RUNNING
        self.assertEqual(invocation.invocation_status, InvocationStatus.RUNNING)

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "gate"})
    def test_non_gated_tool_allowed(self):
        """Non-gated tool (custom.tool) → allowed even in gate mode."""
        uow, _ = _make_gate_deps()
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )

        tool_calls = [
            {"id": "tc1", "function": {"name": "custom.search", "arguments": '{"query": "test"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={},
            tool_approval_service=None,
        )

        self.assertIsNone(result)
        self.assertEqual(invocation.invocation_status, InvocationStatus.RUNNING)

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "warn"})
    def test_warn_mode_allows_execution(self):
        """mode=warn → shell.exec warned but allowed."""
        uow, _ = _make_gate_deps()
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )

        tool_calls = [
            {"id": "tc1", "function": {"name": "shell.exec", "arguments": '{"code": "ls"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={},
            tool_approval_service=None,
        )

        self.assertIsNone(result)
        self.assertEqual(invocation.invocation_status, InvocationStatus.RUNNING)

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "gate"})
    def test_pending_context_has_required_fields(self):
        """pending_tool_context must have all fields needed for S2 resume."""
        approval_service = MagicMock()
        approval_service.request_tool_approval.return_value = {"id": str(uuid4())}
        uow, _ = _make_gate_deps(tool_approval_service=approval_service)
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )
        invocation.started_at = invocation.created_at

        tool_calls = [
            {"id": "tc1", "function": {"name": "python.run_script", "arguments": '{"code": "print(1)"}'}},
        ]

        check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[{"role": "user", "content": "do something"}],
            gw_response={"output_text": "I'll run a script", "prompt_tokens": 10, "completion_tokens": 5},
            tool_approval_service=approval_service,
        )

        ctx = invocation.pending_tool_context
        self.assertIn("tool_calls", ctx)
        self.assertIn("messages", ctx)
        self.assertIn("gw_response", ctx)
        self.assertIn("gated_tool_name", ctx)
        self.assertIn("gate_reason", ctx)
        self.assertEqual(ctx["gated_tool_name"], "python.run_script")

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "gate"})
    def test_approval_service_failure_still_pauses(self):
        """If approval service fails, invocation still enters WAITING_HUMAN."""
        approval_service = MagicMock()
        approval_service.request_tool_approval.side_effect = RuntimeError("Connection refused")
        uow, _ = _make_gate_deps(tool_approval_service=approval_service)
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )
        invocation.started_at = invocation.created_at

        tool_calls = [
            {"id": "tc1", "function": {"name": "shell.exec", "arguments": '{"code": "ls"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={},
            tool_approval_service=approval_service,
        )

        # Should still pause — approval creation is best-effort
        self.assertIsNotNone(result)
        self.assertEqual(invocation.invocation_status, InvocationStatus.WAITING_HUMAN)
        # approval_id should be None since service failed
        self.assertIsNone(result.output_payload["approval_id"])

    @patch.dict(os.environ, {"TOOL_APPROVAL_MODE": "gate"})
    def test_no_approval_service_still_pauses(self):
        """If no approval service configured, invocation still enters WAITING_HUMAN."""
        uow, _ = _make_gate_deps(tool_approval_service=None)
        request = _make_request()

        invocation = AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id="test-agent",
            model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )
        invocation.started_at = invocation.created_at

        tool_calls = [
            {"id": "tc1", "function": {"name": "shell.exec", "arguments": '{"code": "ls"}'}},
        ]

        result = check_tool_approval_gate(
            uow=uow,
            invocation=invocation,
            request=request,
            tool_calls=tool_calls,
            messages=[],
            gw_response={},
            tool_approval_service=None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(invocation.invocation_status, InvocationStatus.WAITING_HUMAN)


class TestWaitingHumanDomainTransition(unittest.TestCase):
    """Test mark_waiting_human with pending_tool_context."""

    def test_mark_waiting_human_stores_context(self):
        inv = AgentInvocation(
            id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_id="m",
            invocation_status=InvocationStatus.RUNNING,
        )
        context = {"tool_calls": [{"id": "tc1"}], "gate_reason": "shell.exec gated"}
        inv.mark_waiting_human(pending_tool_context=context)

        self.assertEqual(inv.invocation_status, InvocationStatus.WAITING_HUMAN)
        self.assertEqual(inv.pending_tool_context, context)

    def test_mark_waiting_human_without_context(self):
        inv = AgentInvocation(
            id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_id="m",
            invocation_status=InvocationStatus.RUNNING,
        )
        inv.mark_waiting_human()

        self.assertEqual(inv.invocation_status, InvocationStatus.WAITING_HUMAN)
        self.assertIsNone(inv.pending_tool_context)

    def test_resume_from_waiting_human(self):
        inv = AgentInvocation(
            id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_id="m",
            invocation_status=InvocationStatus.RUNNING,
        )
        inv.mark_waiting_human(pending_tool_context={"tool": "shell.exec"})
        inv.resume_from_wait()

        self.assertEqual(inv.invocation_status, InvocationStatus.RUNNING)
        # Context preserved for S2 to read
        self.assertIsNotNone(inv.pending_tool_context)


if __name__ == "__main__":
    unittest.main()
