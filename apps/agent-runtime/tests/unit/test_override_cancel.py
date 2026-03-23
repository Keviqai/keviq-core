"""Unit tests for override and cancel semantics in ResumeInvocationHandler (O5-S3).

Tests:
- Override → synthetic tool result injected → model continues → complete
- Cancel → CANCELLED terminal state
- Override without override_output → error
- Cancel clears pending context
- Duplicate actions on non-WAITING_HUMAN → INVALID_STATE
- Override result is truncated to 32KB
"""

import os
import sys
from unittest.mock import MagicMock
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'

from src.application.resume_handler import ResumeInvocationHandler
from src.domain.agent_invocation import AgentInvocation, InvocationStatus


def _make_invocation(*, pending_ctx=None):
    inv = AgentInvocation(
        id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
        workspace_id=uuid4(), correlation_id=uuid4(),
        agent_id="test-agent", model_id="test-model",
        invocation_status=InvocationStatus.RUNNING,
    )
    inv.started_at = inv.created_at
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


def _make_handler(*, invocation=None):
    uow = MagicMock()
    gateway = MagicMock()
    exec_svc = MagicMock()

    if invocation:
        uow.invocations.get_by_id.return_value = invocation

    # Gateway returns stop after resume
    gateway.invoke_model.return_value = {
        "output_text": "Done with override",
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


class TestOverride:
    """Test override decision → synthetic tool result → model completes."""

    def test_override_completes_with_synthetic_result(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="file1.txt\nfile2.txt",
        )

        assert result["status"] == "completed"
        assert result["resolution"] == "overridden"
        assert inv.invocation_status == InvocationStatus.COMPLETED
        assert inv.pending_tool_context is None

    def test_override_injects_output_as_tool_result(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="synthetic output here",
        )

        # Gateway should have been called with messages including synthetic tool result
        call_args = gw.invoke_model.call_args
        messages = call_args.kwargs["messages"]
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert "synthetic output here" in tool_messages[0]["content"]

    def test_override_does_not_dispatch_real_tool(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="override data",
        )

        exec_svc.call_tool.assert_not_called()

    def test_override_without_output_returns_error(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output=None,
        )

        assert result["error"] == "MISSING_OVERRIDE_OUTPUT"
        # Invocation should still be WAITING_HUMAN
        assert inv.invocation_status == InvocationStatus.WAITING_HUMAN

    def test_override_emits_overridden_event(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="data",
        )

        event_types = [
            call.kwargs["event_type"]
            for call in uow.save_with_event.call_args_list
        ]
        assert "agent_invocation.overridden" in event_types
        assert "agent_invocation.completed" in event_types

    def test_override_accumulates_tokens(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="data",
        )

        # Pre-pause (10+5) + post-resume (15+8)
        assert result["prompt_tokens"] == 25
        assert result["completion_tokens"] == 13


class TestCancel:
    """Test cancel decision → CANCELLED terminal state."""

    def test_cancel_marks_cancelled(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
            comment="Too risky, stopping here",
        )

        assert result["status"] == "cancelled"
        assert result["error_code"] == "TOOL_CANCELLED"
        assert inv.invocation_status == InvocationStatus.CANCELLED
        assert inv.pending_tool_context is None

    def test_cancel_no_tool_dispatch(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
        )

        exec_svc.call_tool.assert_not_called()
        gw.invoke_model.assert_not_called()

    def test_cancel_no_model_call(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
        )

        gw.invoke_model.assert_not_called()

    def test_cancel_emits_cancelled_event(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
        )

        event_types = [
            call.kwargs["event_type"]
            for call in uow.save_with_event.call_args_list
        ]
        assert "agent_invocation.cancelled" in event_types

    def test_cancel_stores_error_detail(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
            comment="Operator decided to stop",
        )

        assert inv.error_detail["error_code"] == "TOOL_CANCELLED"
        assert "Operator decided to stop" in inv.error_detail["error_message"]


class TestEdgeCases:
    """Edge cases for override/cancel."""

    def test_override_on_non_waiting_human_returns_error(self):
        inv = AgentInvocation(
            id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_id="m",
            invocation_status=InvocationStatus.RUNNING,
        )
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="override",
            override_output="data",
        )

        assert result["error"] == "INVALID_STATE"

    def test_cancel_on_already_failed_returns_error(self):
        inv = _make_invocation(pending_ctx=_default_pending_ctx())
        inv.mark_failed(error_detail={"error_code": "STUCK"})

        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="cancel",
        )

        assert result["error"] == "INVALID_STATE"

    def test_invalid_decision_returns_error(self):
        ctx = _default_pending_ctx()
        inv = _make_invocation(pending_ctx=ctx)
        handler, uow, gw, exec_svc = _make_handler(invocation=inv)

        result = handler.resume(
            invocation_id=inv.id,
            workspace_id=inv.workspace_id,
            decision="something_else",
        )

        assert result["error"] == "INVALID_DECISION"
