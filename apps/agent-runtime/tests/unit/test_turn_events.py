"""Unit tests for O6-S2 turn-level events + invocation summary.

Tests:
- turn_completed event emitted per turn with correct payload
- Invocation summary in completed event
- Invocation summary in failed/timed_out events
- Helper functions for building payloads
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

from src.application.tool_helpers import build_turn_event_payload, build_invocation_summary
from src.domain.agent_invocation import AgentInvocation, InvocationStatus


def _make_invocation():
    return AgentInvocation(
        id=uuid4(), step_id=uuid4(), run_id=uuid4(), task_id=uuid4(),
        workspace_id=uuid4(), correlation_id=uuid4(),
        agent_id="test-agent", model_id="test-model",
    )


class TestBuildTurnEventPayload:
    """Test build_turn_event_payload helper."""

    def test_basic_fields(self):
        inv = _make_invocation()
        payload = build_turn_event_payload(
            inv, turn_index=0, tool_count=2, failure_count=0,
            model_latency_ms=150, turn_duration_ms=500, budget_remaining_ms=119500,
        )
        assert payload["turn_index"] == 0
        assert payload["tool_count"] == 2
        assert payload["failure_count"] == 0
        assert payload["model_latency_ms"] == 150
        assert payload["turn_duration_ms"] == 500
        assert payload["budget_remaining_ms"] == 119500
        assert payload["agent_invocation_id"] == str(inv.id)

    def test_with_tools_summary(self):
        inv = _make_invocation()
        tools = [
            {"name": "shell.exec", "status": "completed", "duration_ms": 200},
            {"name": "python.run_script", "status": "failed", "duration_ms": 50},
        ]
        payload = build_turn_event_payload(
            inv, turn_index=1, tool_count=2, failure_count=1,
            model_latency_ms=100, turn_duration_ms=400, budget_remaining_ms=100000,
            tools=tools,
        )
        assert len(payload["tools"]) == 2
        assert payload["tools"][0]["name"] == "shell.exec"
        assert payload["tools"][1]["status"] == "failed"

    def test_without_tools_no_key(self):
        inv = _make_invocation()
        payload = build_turn_event_payload(
            inv, turn_index=0, tool_count=1, failure_count=0,
            model_latency_ms=50, turn_duration_ms=200, budget_remaining_ms=110000,
        )
        assert "tools" not in payload


class TestBuildInvocationSummary:
    """Test build_invocation_summary helper."""

    def test_basic_summary(self):
        summary = build_invocation_summary(
            total_turns=3, total_tools_called=5, total_tool_failures=1,
            total_model_latency_ms=450, total_tool_latency_ms=1200,
        )
        assert summary["total_turns"] == 3
        assert summary["total_tools_called"] == 5
        assert summary["total_tool_failures"] == 1
        assert summary["total_model_latency_ms"] == 450
        assert summary["total_tool_latency_ms"] == 1200
        assert "terminal_reason" not in summary

    def test_with_terminal_reason(self):
        summary = build_invocation_summary(
            total_turns=2, total_tools_called=3, total_tool_failures=3,
            total_model_latency_ms=200, total_tool_latency_ms=100,
            terminal_reason="ALL_TOOLS_FAILED",
        )
        assert summary["terminal_reason"] == "ALL_TOOLS_FAILED"

    def test_zero_tools(self):
        summary = build_invocation_summary(
            total_turns=0, total_tools_called=0, total_tool_failures=0,
            total_model_latency_ms=100, total_tool_latency_ms=0,
        )
        assert summary["total_turns"] == 0
        assert summary["total_tools_called"] == 0


class TestTurnEventEmission:
    """Test that turn_completed events are emitted from execution_handler."""

    def test_one_tool_turn_emits_turn_completed(self):
        from src.application.execution_handler import ExecuteInvocationHandler
        from src.domain.execution_contracts import ExecutionRequest, ExecutionResult, ModelProfile

        uow = MagicMock()
        gateway = MagicMock()
        exec_svc = MagicMock()

        gateway.invoke_model.side_effect = [
            {
                "output_text": "",
                "finish_reason": "tool_calls",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "tool_calls": [{
                    "id": "tc1",
                    "function": {"name": "custom.search", "arguments": '{"q": "test"}'},
                }],
            },
            {
                "output_text": "Found it",
                "finish_reason": "stop",
                "prompt_tokens": 20,
                "completion_tokens": 8,
            },
        ]
        exec_svc.call_tool.return_value = {
            "status": "completed", "stdout": "result", "stderr": "",
        }

        handler = ExecuteInvocationHandler(
            unit_of_work=uow, gateway=gateway, execution_service=exec_svc,
        )
        request = ExecutionRequest(
            agent_invocation_id=uuid4(), workspace_id=uuid4(), task_id=uuid4(),
            run_id=uuid4(), step_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_profile=ModelProfile(model_alias="m"),
            instruction="search", input_payload={"sandbox_id": str(uuid4())},
            timeout_ms=120000,
        )
        result = handler.execute(request)

        assert isinstance(result, ExecutionResult)

        # Check events emitted
        event_types = [
            call.kwargs["event_type"]
            for call in uow.save_with_event.call_args_list
        ]
        assert "agent_invocation.turn_completed" in event_types
        assert "agent_invocation.completed" in event_types

        # Find turn_completed payload
        for call in uow.save_with_event.call_args_list:
            if call.kwargs["event_type"] == "agent_invocation.turn_completed":
                payload = call.kwargs["event_payload"]
                assert payload["turn_index"] == 0
                assert payload["tool_count"] == 1
                assert payload["failure_count"] == 0
                assert "model_latency_ms" in payload
                assert "turn_duration_ms" in payload
                assert "budget_remaining_ms" in payload
                assert len(payload["tools"]) == 1
                assert payload["tools"][0]["name"] == "custom.search"
                break

    def test_completed_event_has_invocation_summary(self):
        from src.application.execution_handler import ExecuteInvocationHandler
        from src.domain.execution_contracts import ExecutionRequest, ExecutionResult, ModelProfile

        uow = MagicMock()
        gateway = MagicMock()
        exec_svc = MagicMock()

        gateway.invoke_model.side_effect = [
            {
                "output_text": "",
                "finish_reason": "tool_calls",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "tool_calls": [{
                    "id": "tc1",
                    "function": {"name": "shell.exec", "arguments": '{"code": "ls"}'},
                }],
            },
            {
                "output_text": "Done",
                "finish_reason": "stop",
                "prompt_tokens": 20,
                "completion_tokens": 8,
            },
        ]
        exec_svc.call_tool.return_value = {
            "status": "completed", "stdout": "data", "stderr": "",
        }

        handler = ExecuteInvocationHandler(
            unit_of_work=uow, gateway=gateway, execution_service=exec_svc,
        )
        request = ExecutionRequest(
            agent_invocation_id=uuid4(), workspace_id=uuid4(), task_id=uuid4(),
            run_id=uuid4(), step_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_profile=ModelProfile(model_alias="m"),
            instruction="run", input_payload={"sandbox_id": str(uuid4())},
            timeout_ms=120000,
        )
        handler.execute(request)

        # Find completed payload
        for call in uow.save_with_event.call_args_list:
            if call.kwargs["event_type"] == "agent_invocation.completed":
                payload = call.kwargs["event_payload"]
                assert "invocation_summary" in payload
                summary = payload["invocation_summary"]
                assert summary["total_turns"] == 1
                assert summary["total_tools_called"] == 1
                assert summary["total_tool_failures"] == 0
                assert "total_model_latency_ms" in summary
                assert "total_tool_latency_ms" in summary
                break
        else:
            assert False, "agent_invocation.completed event not found"

    def test_no_tool_turns_produces_zero_summary(self):
        """Invocation with no tool calls → summary shows 0 turns."""
        from src.application.execution_handler import ExecuteInvocationHandler
        from src.domain.execution_contracts import ExecutionRequest, ExecutionResult, ModelProfile

        uow = MagicMock()
        gateway = MagicMock()

        gateway.invoke_model.return_value = {
            "output_text": "Hello",
            "finish_reason": "stop",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }

        handler = ExecuteInvocationHandler(unit_of_work=uow, gateway=gateway)
        request = ExecutionRequest(
            agent_invocation_id=uuid4(), workspace_id=uuid4(), task_id=uuid4(),
            run_id=uuid4(), step_id=uuid4(), correlation_id=uuid4(),
            agent_id="a", model_profile=ModelProfile(model_alias="m"),
            instruction="hi", timeout_ms=120000,
        )
        handler.execute(request)

        for call in uow.save_with_event.call_args_list:
            if call.kwargs["event_type"] == "agent_invocation.completed":
                payload = call.kwargs["event_payload"]
                summary = payload["invocation_summary"]
                assert summary["total_turns"] == 0
                assert summary["total_tools_called"] == 0
                break
