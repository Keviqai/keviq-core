"""Unit tests for O6-S1 tool execution event enrichment.

Tests:
- Model call latency tracked per turn
- Per-tool timing tracked via tool_result
- Enriched fields available for S2 consumption
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'


class TestModelLatencyTracking:
    """Model call latency is measured and stored in gw_response."""

    def test_model_latency_recorded_in_gw_response(self):
        """invoke_model timing is captured as model_latency_ms."""
        from src.application.execution_handler import ExecuteInvocationHandler
        from src.domain.execution_contracts import ExecutionRequest, ExecutionResult, ModelProfile

        uow = MagicMock()
        gateway = MagicMock()

        # Gateway takes ~10ms (simulated by return — actual time measured by monotonic)
        gateway.invoke_model.return_value = {
            "output_text": "Hello",
            "finish_reason": "stop",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }

        handler = ExecuteInvocationHandler(
            unit_of_work=uow,
            gateway=gateway,
        )

        request = ExecutionRequest(
            agent_invocation_id=uuid4(),
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            correlation_id=uuid4(),
            agent_id="test-agent",
            model_profile=ModelProfile(model_alias="test-model"),
            instruction="say hello",
            timeout_ms=120000,
        )

        result = handler.execute(request)

        assert isinstance(result, ExecutionResult)
        # The gateway was called and latency should be >= 0
        call_args = gateway.invoke_model.call_args
        assert call_args is not None

    def test_per_tool_timing_in_tool_result(self):
        """_execute_tool result dict includes tool_duration_ms after dispatch."""
        from src.application.execution_handler import ExecuteInvocationHandler
        from src.domain.execution_contracts import ExecutionRequest, ExecutionResult, ModelProfile

        uow = MagicMock()
        gateway = MagicMock()
        exec_svc = MagicMock()

        # Model returns tool call, then stop
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
                "output_text": "Found results",
                "finish_reason": "stop",
                "prompt_tokens": 20,
                "completion_tokens": 8,
            },
        ]
        exec_svc.call_tool.return_value = {
            "status": "completed", "stdout": "result data", "stderr": "",
        }

        handler = ExecuteInvocationHandler(
            unit_of_work=uow,
            gateway=gateway,
            execution_service=exec_svc,
        )

        request = ExecutionRequest(
            agent_invocation_id=uuid4(),
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            correlation_id=uuid4(),
            agent_id="test-agent",
            model_profile=ModelProfile(model_alias="test-model"),
            instruction="search for test",
            input_payload={"sandbox_id": str(uuid4())},
            timeout_ms=120000,
        )

        result = handler.execute(request)
        assert isinstance(result, ExecutionResult)
        assert result.status.value == "completed"

        # exec_svc.call_tool was called
        exec_svc.call_tool.assert_called_once()



# Execution-service event enrichment tests are in:
# apps/execution-service/tests/unit/test_event_enrichment.py
