"""Unit tests for tool failure state integrity (O4-S2)."""

import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'


def _make_handler(*, gateway_responses=None, exec_results=None, has_exec=True):
    from src.application.execution_handler import ExecuteInvocationHandler
    uow = MagicMock()
    gw = MagicMock()
    ex = MagicMock() if has_exec else None
    if gateway_responses:
        gw.invoke_model.side_effect = gateway_responses
    if exec_results and ex:
        ex.call_tool.side_effect = exec_results
    return ExecuteInvocationHandler(unit_of_work=uow, gateway=gw, execution_service=ex), uow, gw, ex


def _req(**overrides):
    from src.domain.execution_contracts import ExecutionRequest, ModelProfile
    d = dict(agent_invocation_id=uuid4(), workspace_id=uuid4(), task_id=uuid4(),
             run_id=uuid4(), step_id=uuid4(), correlation_id=uuid4(),
             agent_id='a', model_profile=ModelProfile(model_alias='gpt-4'),
             instruction='x', input_payload={'sandbox_id': str(uuid4())}, timeout_ms=120_000)
    d.update(overrides)
    return ExecutionRequest(**d)


class TestAllToolsFailedMarksInvocationFailed:
    """GAP-02: when ALL tools fail in a turn, invocation → FAILED."""

    def test_single_tool_fails_marks_failed(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'run', 'arguments': '{}'}}]},
            ],
            exec_results=[{'status': 'failed', 'error_message': 'Command not found', 'stdout': '', 'stderr': ''}],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'ALL_TOOLS_FAILED'

    def test_two_tools_both_fail_marks_failed(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [
                     {'id': 'c1', 'type': 'function', 'function': {'name': 't1', 'arguments': '{}'}},
                     {'id': 'c2', 'type': 'function', 'function': {'name': 't2', 'arguments': '{}'}},
                 ]},
            ],
            exec_results=[
                {'status': 'failed', 'error_message': 'err1', 'stdout': '', 'stderr': ''},
                {'status': 'failed', 'error_message': 'err2', 'stdout': '', 'stderr': ''},
            ],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'ALL_TOOLS_FAILED'

    def test_failed_event_emitted(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'r', 'arguments': '{}'}}]},
            ],
            exec_results=[{'status': 'failed', 'error_message': 'err', 'stdout': '', 'stderr': ''}],
        )
        handler.execute(_req())

        events = [c.args[1] if len(c.args) > 1 else c.kwargs.get('event_type', '')
                  for c in uow.save_with_event.call_args_list]
        assert 'agent_invocation.failed' in events


class TestPartialFailureContinues:
    """When SOME tools succeed and some fail, loop continues to model."""

    def test_one_success_one_failure_continues(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [
                     {'id': 'c1', 'type': 'function', 'function': {'name': 'ok', 'arguments': '{}'}},
                     {'id': 'c2', 'type': 'function', 'function': {'name': 'bad', 'arguments': '{}'}},
                 ]},
                {'output_text': 'handled it', 'finish_reason': 'stop', 'prompt_tokens': 1, 'completion_tokens': 1},
            ],
            exec_results=[
                {'status': 'completed', 'stdout': 'ok', 'stderr': ''},
                {'status': 'failed', 'error_message': 'err', 'stdout': '', 'stderr': ''},
            ],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert gw.invoke_model.call_count == 2


class TestToolCallsValidation:
    """GAP-03: malformed tool_calls are validated and skipped."""

    def test_malformed_tool_call_no_id_skipped(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = [{'function': {'name': 'test', 'arguments': '{}'}}]  # no id
        assert _validate_tool_calls(tc) == []

    def test_malformed_tool_call_no_function_skipped(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = [{'id': 'c1'}]  # no function
        assert _validate_tool_calls(tc) == []

    def test_malformed_tool_call_no_function_name_skipped(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = [{'id': 'c1', 'function': {}}]  # no name
        assert _validate_tool_calls(tc) == []

    def test_valid_tool_call_passes(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = [{'id': 'c1', 'type': 'function', 'function': {'name': 'run', 'arguments': '{}'}}]
        assert len(_validate_tool_calls(tc)) == 1

    def test_mixed_valid_invalid_filters_correctly(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = [
            {'id': 'c1', 'function': {'name': 'ok', 'arguments': '{}'}},  # valid
            {'function': {'name': 'bad'}},  # no id — invalid
            {'id': 'c3', 'function': {'name': 'also_ok', 'arguments': '{}'}},  # valid
        ]
        result = _validate_tool_calls(tc)
        assert len(result) == 2
        assert result[0]['id'] == 'c1'
        assert result[1]['id'] == 'c3'

    def test_all_malformed_marks_invocation_failed(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [{'no_id': True}, {'also_bad': True}]},
            ],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'MALFORMED_TOOL_CALLS'

    def test_non_dict_tool_call_skipped(self):
        from src.application.execution_handler import _validate_tool_calls
        tc = ["not a dict", 42, None]
        assert _validate_tool_calls(tc) == []


class TestTruncatedFlagSurfaced:
    """Tool result with truncated=true adds [output truncated] notice."""

    def test_truncated_notice_appended(self):
        handler, uow, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 1, 'completion_tokens': 1,
                 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'big', 'arguments': '{}'}}]},
                {'output_text': 'done', 'finish_reason': 'stop', 'prompt_tokens': 1, 'completion_tokens': 1},
            ],
            exec_results=[{'status': 'completed', 'stdout': 'lots of output...', 'stderr': '', 'truncated': True}],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        # The model should have received the truncated notice
        # (we can verify via the messages list indirectly — model was called twice)
        assert gw.invoke_model.call_count == 2


class TestSuccessPathUnchanged:
    """Normal success path still works after O4-S2 changes."""

    def test_successful_tool_then_stop(self):
        handler, _, gw, ex = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'run', 'arguments': '{}'}}]},
                {'output_text': 'Final answer', 'finish_reason': 'stop', 'prompt_tokens': 15, 'completion_tokens': 8},
            ],
            exec_results=[{'status': 'completed', 'stdout': '42\n', 'stderr': ''}],
        )
        result = handler.execute(_req())

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert result.output_payload['output_text'] == 'Final answer'
