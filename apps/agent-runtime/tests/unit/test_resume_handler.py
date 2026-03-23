"""Unit tests for ResumeInvocationHandler (O5-S2).

Tests:
- Approved → resume tool execution → complete
- Rejected → FAILED with TOOL_REJECTED
- Missing pending context → FAILED with MISSING_PENDING_CONTEXT
- Wrong invocation state → INVALID_STATE
- Invocation not found → INVOCATION_NOT_FOUND
- Duplicate resume (already FAILED) → INVALID_STATE
- Budget respected after resume
"""

import os
import sys
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'

from src.application.resume_handler import ResumeInvocationHandler
from src.domain.agent_invocation import AgentInvocation, InvocationStatus


def _make_invocation(*, status=InvocationStatus.WAITING_HUMAN, pending_ctx=None):
    inv = AgentInvocation(
        id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
        workspace_id=uuid4(), correlation_id=uuid4(),
        agent_id="test-agent", model_id="test-model",
        invocation_status=InvocationStatus.RUNNING,
    )
    inv.started_at = inv.created_at
    if status == InvocationStatus.WAITING_HUMAN:
        inv.mark_waiting_human(pending_tool_context=pending_ctx)
    return inv


def _default_pending_ctx():
    return {
        "tool_calls": [{
            "id": "tc1",
            "function": {"name": "shell.exec", "arguments": '{"code": "ls -la"}'},
        }],
        "messages": [{"role": "user", "content": "list files"}],
        "gw_response": {"output_text": "", "prompt_tokens": 10, "completion_tokens": 5},
        "sandbox_id": str(uuid4()),
        "gated_tool_name": "shell.exec",
        "gate_reason": "shell.exec requires approval",
    }


def _make_handler(*, invocation=None, exec_result=None):
    uow = MagicMock()
    gateway = MagicMock()
    exec_svc = MagicMock()

    if invocation:
        uow.invocations.get_by_id.return_value = invocation

    if exec_result:
        exec_svc.call_tool.return_value = exec_result

    # Gateway returns stop after resume
    gateway.invoke_model.return_value = {
        "output_text": "Done after resume",
        "finish_reason": "stop",
        "prompt_tokens": 15,
        "completion_tokens": 8,
    }

    handler = ResumeInvocationHandler(
        unit_of_work=uow,
        gateway=gateway,
        execution_service=exec_svc,
    )
    return handler, uow, gateway, exec_svc


class TestResumeApproved:
    """Test approved decision → tool executes → model completes."""

    def test_approved_resumes_and_completes(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(
            invocation=inv,
            exec_result={"status": "completed", "stdout": "file.txt\n", "stderr": ""},
        )

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        assert result["status"] == "completed"
        assert result["invocation_id"] == str(inv.id)
        assert inv.invocation_status == InvocationStatus.COMPLETED
        assert inv.pending_tool_context is None  # consumed

    def test_approved_dispatches_tool(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(
            invocation=inv,
            exec_result={"status": "completed", "stdout": "ok", "stderr": ""},
        )

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        exec_svc.call_tool.assert_called_once()
        call_kwargs = exec_svc.call_tool.call_args
        assert call_kwargs.kwargs["tool_name"] == "shell.exec"

    def test_approved_accumulates_tokens(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(
            invocation=inv,
            exec_result={"status": "completed", "stdout": "ok", "stderr": ""},
        )

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        # Pre-pause tokens (10+5) + post-resume tokens (15+8)
        assert result["prompt_tokens"] == 25
        assert result["completion_tokens"] == 13


class TestResumeRejected:
    """Test rejected decision → FAILED with TOOL_REJECTED."""

    def test_rejected_marks_failed(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="rejected",
            comment="Too risky",
        )

        assert result["status"] == "failed"
        assert result["error_code"] == "TOOL_REJECTED"
        assert inv.invocation_status == InvocationStatus.FAILED
        assert inv.error_detail["error_code"] == "TOOL_REJECTED"
        assert "Too risky" in inv.error_detail["error_message"]
        assert inv.pending_tool_context is None  # consumed

    def test_rejected_no_tool_dispatch(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="rejected",
        )

        exec_svc.call_tool.assert_not_called()
        gw.invoke_model.assert_not_called()


class TestResumeEdgeCases:
    """Test edge cases and error handling."""

    def test_not_found_returns_error(self):
        uow = MagicMock()
        uow.invocations.get_by_id.return_value = None
        handler = ResumeInvocationHandler(
            unit_of_work=uow, gateway=MagicMock(),
        )

        result = handler.resume(
            invocation_id=uuid4(),
            workspace_id=uuid4(),
            decision="approved",
        )

        assert result["error"] == "INVOCATION_NOT_FOUND"

    def test_wrong_state_returns_error(self):
        inv = AgentInvocation(
            id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            agent_id="test-agent", model_id="test-model",
            invocation_status=InvocationStatus.RUNNING,
        )
        uow = MagicMock()
        uow.invocations.get_by_id.return_value = inv
        handler = ResumeInvocationHandler(
            unit_of_work=uow, gateway=MagicMock(),
        )

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        assert result["error"] == "INVALID_STATE"
        assert "running" in result["current_status"]

    def test_missing_pending_context_fails(self):
        inv = _make_invocation(pending_ctx=None)
        # Force WAITING_HUMAN without context (edge case)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        assert result["error"] == "MISSING_PENDING_CONTEXT"
        assert inv.invocation_status == InvocationStatus.FAILED

    def test_already_failed_returns_invalid_state(self):
        inv = _make_invocation(pending_ctx=_default_pending_ctx())
        # Simulate already resolved (mark failed externally)
        inv.mark_failed(error_detail={"error_code": "STUCK_WAITING_HUMAN"})

        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        assert result["error"] == "INVALID_STATE"
        assert "failed" in result["current_status"]

    def test_tool_failure_after_approve_marks_failed(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(
            invocation=inv,
            exec_result={"status": "failed", "error_message": "sandbox crashed", "stdout": "", "stderr": ""},
        )

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        assert result["status"] == "failed"
        assert result["error_code"] == "ALL_TOOLS_FAILED"

    def test_events_emitted_on_resume(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(
            invocation=inv,
            exec_result={"status": "completed", "stdout": "ok", "stderr": ""},
        )

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="approved",
        )

        # Should have emitted: resumed, waiting_tool, completed
        event_types = [
            call.kwargs["event_type"]
            for call in uow.save_with_event.call_args_list
        ]
        assert "agent_invocation.resumed" in event_types
        assert "agent_invocation.waiting_tool" in event_types
        assert "agent_invocation.completed" in event_types
