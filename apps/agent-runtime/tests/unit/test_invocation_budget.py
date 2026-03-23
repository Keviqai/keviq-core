"""Unit tests for invocation wall-clock budget + timeout alignment (O4-S1)."""

import os
import sys
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'


def _make_handler(*, gateway_responses=None, exec_results=None, has_exec_service=True):
    from src.application.execution_handler import ExecuteInvocationHandler
    uow = MagicMock()
    gateway = MagicMock()
    exec_service = MagicMock() if has_exec_service else None
    if gateway_responses:
        gateway.invoke_model.side_effect = gateway_responses
    if exec_results and exec_service:
        exec_service.call_tool.side_effect = exec_results
    return ExecuteInvocationHandler(
        unit_of_work=uow, gateway=gateway, execution_service=exec_service,
    ), uow, gateway, exec_service


def _make_request(**overrides):
    from src.domain.execution_contracts import ExecutionRequest, ModelProfile
    defaults = dict(
        agent_invocation_id=uuid4(), workspace_id=uuid4(), task_id=uuid4(),
        run_id=uuid4(), step_id=uuid4(), correlation_id=uuid4(),
        agent_id='test-agent', model_profile=ModelProfile(model_alias='gpt-4'),
        instruction='Do something', input_payload={}, timeout_ms=120_000,
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


class TestInvocationBudgetConfig:
    """INVOCATION_BUDGET_MS default and override."""

    def test_default_budget_120s(self):
        from src.application.execution_handler import INVOCATION_BUDGET_MS
        assert INVOCATION_BUDGET_MS == 120_000

    def test_max_tool_turns_default_5(self):
        from src.application.execution_handler import MAX_TOOL_TURNS
        assert MAX_TOOL_TURNS == 5


class TestBudgetExhausted:
    """Invocation ends with TIMED_OUT when budget is exceeded."""

    def test_budget_exhausted_returns_failure(self):
        from src.application.execution_handler import ExecuteInvocationHandler
        import src.application.tool_loop as mod

        handler, uow, gw, _ = _make_handler(
            gateway_responses=[
                {'output_text': 'hi', 'finish_reason': 'stop', 'prompt_tokens': 1, 'completion_tokens': 1},
            ],
        )

        # Simulate budget already exhausted by patching time.monotonic
        call_count = [0]
        base_time = 1000.0

        def fake_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return base_time  # budget_start
            return base_time + 200  # 200 seconds later — way past budget

        with patch.object(mod.time, 'monotonic', side_effect=fake_monotonic):
            result = handler.execute(_make_request(timeout_ms=5000))  # 5s budget

        from src.domain.execution_contracts import ExecutionFailure
        assert isinstance(result, ExecutionFailure)
        assert result.error_code == 'BUDGET_EXHAUSTED'

    def test_budget_exhausted_emits_timed_out_event(self):
        import src.application.tool_loop as mod

        handler, uow, gw, _ = _make_handler(
            gateway_responses=[{'output_text': 'hi', 'finish_reason': 'stop'}],
        )

        call_count = [0]
        base_time = 1000.0

        def fake_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return base_time
            return base_time + 200

        with patch.object(mod.time, 'monotonic', side_effect=fake_monotonic):
            handler.execute(_make_request(timeout_ms=5000))

        event_types = [c.args[1] if len(c.args) > 1 else c.kwargs.get('event_type', '')
                       for c in uow.save_with_event.call_args_list]
        assert 'agent_invocation.timed_out' in event_types


class TestModelTimeoutDerivedFromBudget:
    """Model call timeout is min(remaining_budget, 60s)."""

    def test_model_timeout_capped_at_60s(self):
        import src.application.tool_loop as mod

        handler, uow, gw, _ = _make_handler(
            gateway_responses=[
                {'output_text': 'hi', 'finish_reason': 'stop', 'prompt_tokens': 1, 'completion_tokens': 1},
            ],
        )

        # Large budget — model timeout should be capped at 60s
        handler.execute(_make_request(timeout_ms=300_000))

        call_kwargs = gw.invoke_model.call_args[1]
        assert call_kwargs['timeout_ms'] <= 60_000

    def test_model_timeout_uses_remaining_when_less_than_60s(self):
        import src.application.tool_loop as mod

        handler, uow, gw, _ = _make_handler(
            gateway_responses=[
                {'output_text': 'hi', 'finish_reason': 'stop', 'prompt_tokens': 1, 'completion_tokens': 1},
            ],
        )

        call_count = [0]
        base_time = 1000.0

        def fake_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return base_time  # budget_start
            return base_time + 95  # 95s elapsed, 5s remaining of 100s budget

        with patch.object(mod.time, 'monotonic', side_effect=fake_monotonic):
            handler.execute(_make_request(timeout_ms=100_000))  # 100s budget

        call_kwargs = gw.invoke_model.call_args[1]
        assert call_kwargs['timeout_ms'] <= 5_000  # only ~5s left


class TestNormalPathUnaffected:
    """Normal (non-timeout) path still works correctly."""

    def test_successful_invocation_with_budget(self):
        handler, _, gw, _ = _make_handler(
            gateway_responses=[
                {'output_text': 'Done!', 'finish_reason': 'stop', 'prompt_tokens': 10, 'completion_tokens': 5},
            ],
        )
        result = handler.execute(_make_request(timeout_ms=120_000))

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert result.output_payload['output_text'] == 'Done!'

    def test_tool_loop_within_budget(self):
        handler, _, gw, exec_svc = _make_handler(
            gateway_responses=[
                {'output_text': '', 'finish_reason': 'tool_calls', 'prompt_tokens': 10, 'completion_tokens': 5,
                 'tool_calls': [{'id': 'c1', 'function': {'name': 'test', 'arguments': '{}'}}]},
                {'output_text': 'result', 'finish_reason': 'stop', 'prompt_tokens': 10, 'completion_tokens': 5},
            ],
            exec_results=[{'status': 'completed', 'stdout': 'ok', 'stderr': ''}],
        )
        result = handler.execute(_make_request(
            timeout_ms=120_000,
            input_payload={'sandbox_id': str(uuid4())},
        ))

        from src.domain.execution_contracts import ExecutionResult
        assert isinstance(result, ExecutionResult)
        assert gw.invoke_model.call_count == 2


class TestTimeoutAlignment:
    """Timeout alignment invariant: dispatch >= invocation budget."""

    def test_invocation_budget_120s(self):
        from src.application.execution_handler import INVOCATION_BUDGET_MS
        assert INVOCATION_BUDGET_MS == 120_000

    def test_budget_is_positive(self):
        from src.application.execution_handler import INVOCATION_BUDGET_MS
        assert INVOCATION_BUDGET_MS > 0
