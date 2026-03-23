"""Unit tests for tool execution loop in ExecuteInvocationHandler (O3-S3)."""

import os
import sys
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
# O5-S1: Disable tool approval gate for O3 backward-compat tests
os.environ['TOOL_APPROVAL_MODE'] = 'none'


def _make_handler(*, gateway_responses=None, exec_results=None, has_exec_service=True):
    """Create handler with mocked dependencies."""
    from src.application.execution_handler import ExecuteInvocationHandler

    uow = MagicMock()
    gateway = MagicMock()
    exec_service = MagicMock() if has_exec_service else None

    if gateway_responses:
        gateway.invoke_model.side_effect = gateway_responses

    if exec_results and exec_service:
        exec_service.call_tool.side_effect = exec_results

    handler = ExecuteInvocationHandler(
        unit_of_work=uow,
        gateway=gateway,
        execution_service=exec_service,
    )
    return handler, uow, gateway, exec_service


def _make_request(**overrides):
    from src.domain.execution_contracts import ExecutionRequest, ModelProfile
    defaults = dict(
        agent_invocation_id=uuid4(),
        workspace_id=uuid4(),
        task_id=uuid4(),
        run_id=uuid4(),
        step_id=uuid4(),
        correlation_id=uuid4(),
        agent_id='test-agent',
        model_profile=ModelProfile(model_alias='gpt-4'),
        instruction='Do something',
        input_payload={},
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


class TestNoToolCalls:
    """Model returns stop → no tool loop, behaves like before."""

    def test_single_model_call_returns_result(self):
        handler, uow, gw, _ = _make_handler(
            gateway_responses=[{
                'output_text': 'Hello!',
                'finish_reason': 'stop',
                'prompt_tokens': 10,
                'completion_tokens': 5,
            }],
        )
        result = handler.execute(_make_request())
        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert result.output_payload['output_text'] == 'Hello!'
        gw.invoke_model.assert_called_once()

    def test_no_execution_service_still_works(self):
        handler, _, gw, _ = _make_handler(
            gateway_responses=[{
                'output_text': 'Done',
                'finish_reason': 'stop',
            }],
            has_exec_service=False,
        )
        result = handler.execute(_make_request())
        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)


class TestToolLoop:
    """Model returns tool_calls → handler dispatches and loops."""

    def test_one_tool_call_then_stop(self):
        handler, uow, gw, exec_svc = _make_handler(
            gateway_responses=[
                # Turn 1: model wants to call a tool
                {
                    'output_text': '',
                    'finish_reason': 'tool_calls',
                    'prompt_tokens': 20,
                    'completion_tokens': 10,
                    'tool_calls': [{
                        'id': 'call_1',
                        'type': 'function',
                        'function': {'name': 'python.run_script', 'arguments': '{"code": "print(42)"}'},
                    }],
                },
                # Turn 2: model returns final answer
                {
                    'output_text': 'The answer is 42',
                    'finish_reason': 'stop',
                    'prompt_tokens': 30,
                    'completion_tokens': 8,
                },
            ],
            exec_results=[
                {'status': 'completed', 'stdout': '42\n', 'stderr': '', 'exit_code': 0},
            ],
        )
        req = _make_request(input_payload={'sandbox_id': str(uuid4())})
        result = handler.execute(req)

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert result.output_payload['output_text'] == 'The answer is 42'
        assert gw.invoke_model.call_count == 2
        exec_svc.call_tool.assert_called_once()

    def test_tokens_accumulated_across_turns(self):
        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 100, 'completion_tokens': 50,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 't', 'arguments': '{}'}}]},
                {'output_text': 'done', 'finish_reason': 'stop', 'prompt_tokens': 200, 'completion_tokens': 30},
            ],
            exec_results=[{'status': 'completed', 'stdout': 'ok', 'stderr': ''}],
        )
        result = handler.execute(_make_request(input_payload={'sandbox_id': str(uuid4())}))
        assert result.usage.prompt_tokens == 300
        assert result.usage.completion_tokens == 80

    def test_tool_calls_stored_on_invocation(self):
        handler, uow, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'run', 'arguments': '{}'}}]},
                {'output_text': 'done', 'finish_reason': 'stop', 'prompt_tokens': 10, 'completion_tokens': 5},
            ],
            exec_results=[{'status': 'completed', 'stdout': 'x', 'stderr': ''}],
        )
        handler.execute(_make_request(input_payload={'sandbox_id': str(uuid4())}))

        # Check that save_with_event was called with waiting_tool event
        event_types = [c.kwargs['event_type'] if 'event_type' in c.kwargs else c.args[1]
                       for c in uow.save_with_event.call_args_list]
        assert 'agent_invocation.waiting_tool' in event_types
        assert 'agent_invocation.completed' in event_types


class TestMaxToolTurns:
    """MAX_TOOL_TURNS prevents runaway loops."""

    def test_loop_exits_at_max_turns(self):
        from src.application.execution_handler import MAX_TOOL_TURNS

        # Create responses that always return tool_calls
        responses = [
            {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
             'tool_calls': [{'id': f'c{i}', 'function': {'name': 'loop', 'arguments': '{}'}}]}
            for i in range(MAX_TOOL_TURNS + 1)  # one extra to test it doesn't exceed
        ]
        exec_results = [{'status': 'completed', 'stdout': '', 'stderr': ''} for _ in range(MAX_TOOL_TURNS)]

        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=responses,
            exec_results=exec_results,
        )
        handler.execute(_make_request(input_payload={'sandbox_id': str(uuid4())}))

        # Should call model at most MAX_TOOL_TURNS times
        assert gw.invoke_model.call_count <= MAX_TOOL_TURNS

    def test_max_tool_turns_default_is_5(self):
        from src.application.execution_handler import MAX_TOOL_TURNS
        assert MAX_TOOL_TURNS == 5


class TestToolFailureHandling:
    """Tool execution failure marks invocation FAILED (O4-S2 integrity)."""

    def test_all_tools_fail_marks_failed(self):
        """Single tool failure → ALL_TOOLS_FAILED (O4-S2 change)."""
        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'fail_tool', 'arguments': '{}'}}]},
            ],
            exec_results=[{'status': 'failed', 'error_message': 'Command not found', 'stdout': '', 'stderr': 'err'}],
        )
        result = handler.execute(_make_request(input_payload={'sandbox_id': str(uuid4())}))

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'ALL_TOOLS_FAILED'

    def test_no_sandbox_id_marks_failed(self):
        """No sandbox_id → tool returns error → ALL_TOOLS_FAILED (O4-S2 change)."""
        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'test', 'arguments': '{}'}}]},
            ],
        )
        result = handler.execute(_make_request(input_payload={}))

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'ALL_TOOLS_FAILED'

    def test_exec_service_exception_marks_failed(self):
        """Exception from execution-service → ALL_TOOLS_FAILED (O4-S2 change)."""
        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'crash', 'arguments': '{}'}}]},
            ],
        )
        exec_svc.call_tool.side_effect = Exception("Connection refused")
        result = handler.execute(_make_request(input_payload={'sandbox_id': str(uuid4())}))

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)


class TestNoExecServiceSkipsTools:
    """When execution_service is None, tool_calls are ignored."""

    def test_tool_calls_ignored_without_exec_service(self):
        handler, _, gw, _ = _make_handler(
            gateway_responses=[
                {'output_text': 'I wanted to use tools but can\'t', 'finish_reason': 'tool_calls',
                 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'test', 'arguments': '{}'}}]},
            ],
            has_exec_service=False,
        )
        result = handler.execute(_make_request())

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        # Only one model call — loop exits because no exec service
        gw.invoke_model.assert_called_once()
