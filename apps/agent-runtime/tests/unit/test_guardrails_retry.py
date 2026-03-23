"""Unit tests for execution guardrails + retry (O4-S3)."""

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


class TestToolGuardrails:
    """_check_tool_guardrails — input validation before dispatch."""

    def test_valid_shell_exec_passes(self):
        from src.application.execution_handler import _check_tool_guardrails
        assert _check_tool_guardrails('shell.exec', {'code': 'ls -la'}) is None

    def test_empty_shell_exec_rejected(self):
        from src.application.execution_handler import _check_tool_guardrails
        result = _check_tool_guardrails('shell.exec', {'code': ''})
        assert result is not None
        assert 'empty command' in result

    def test_whitespace_shell_exec_rejected(self):
        from src.application.execution_handler import _check_tool_guardrails
        result = _check_tool_guardrails('shell.exec', {'code': '   \n  '})
        assert result is not None
        assert 'empty command' in result

    def test_empty_python_script_rejected(self):
        from src.application.execution_handler import _check_tool_guardrails
        result = _check_tool_guardrails('python.run_script', {'code': ''})
        assert result is not None
        assert 'empty code' in result

    def test_valid_python_script_passes(self):
        from src.application.execution_handler import _check_tool_guardrails
        assert _check_tool_guardrails('python.run_script', {'code': 'print(1)'}) is None

    def test_oversized_input_rejected(self):
        from src.application.execution_handler import _check_tool_guardrails, MAX_TOOL_INPUT_BYTES
        big_input = {'code': 'x' * (MAX_TOOL_INPUT_BYTES + 100)}
        result = _check_tool_guardrails('shell.exec', big_input)
        assert result is not None
        assert 'too large' in result

    def test_unknown_tool_passes(self):
        from src.application.execution_handler import _check_tool_guardrails
        assert _check_tool_guardrails('custom.tool', {'data': 'hello'}) is None

    def test_guardrail_rejection_in_handler(self):
        """execute_tool returns GUARDRAIL_REJECTED for empty shell command."""
        from src.application.shared_execution import execute_tool
        result = execute_tool(
            {'id': 'c1', 'function': {'name': 'shell.exec', 'arguments': '{"code": ""}'}},
            execution_service=MagicMock(),
            sandbox_id=uuid4(), attempt_index=0,
        )
        assert result['status'] == 'failed'
        assert result['error_code'] == 'GUARDRAIL_REJECTED'


class TestOutputTruncation:
    """_truncate_tool_result — bound output before model injection."""

    def test_short_content_unchanged(self):
        from src.application.execution_handler import _truncate_tool_result
        assert _truncate_tool_result('hello') == 'hello'

    def test_large_content_truncated(self):
        from src.application.execution_handler import _truncate_tool_result, MAX_TOOL_RESULT_BYTES
        big = 'x' * (MAX_TOOL_RESULT_BYTES + 1000)
        result = _truncate_tool_result(big)
        assert len(result.encode('utf-8')) <= MAX_TOOL_RESULT_BYTES + 100  # small overhead for marker
        assert '[output truncated to 32KB]' in result

    def test_empty_content_unchanged(self):
        from src.application.execution_handler import _truncate_tool_result
        assert _truncate_tool_result('') == ''


class TestExecutionServiceRetry:
    """HttpExecutionServiceClient retry on transient errors."""

    def _make_client(self):
        from src.infrastructure.execution_service_client import HttpExecutionServiceClient
        return HttpExecutionServiceClient(base_url='http://exec:8000')

    def test_success_on_first_attempt(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {'status': 'completed', 'stdout': 'ok'}

        with patch.object(client._client, 'post', return_value=mock_resp), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as m:
            m.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'completed'

    def test_retry_on_503_then_success(self):
        import src.infrastructure.execution_service_client as mod
        client = self._make_client()

        resp_503 = MagicMock()
        resp_503.status_code = 503
        resp_503.text = 'Service Unavailable'

        resp_ok = MagicMock()
        resp_ok.status_code = 202
        resp_ok.json.return_value = {'status': 'completed', 'stdout': 'retried ok'}

        with patch.object(client._client, 'post', side_effect=[resp_503, resp_ok]), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as m, \
             patch.object(mod.time, 'sleep'):
            m.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'completed'

    def test_retry_on_connection_error_then_success(self):
        import src.infrastructure.execution_service_client as mod
        client = self._make_client()

        resp_ok = MagicMock()
        resp_ok.status_code = 202
        resp_ok.json.return_value = {'status': 'completed'}

        with patch.object(client._client, 'post',
                          side_effect=[httpx.ConnectError('refused'), resp_ok]), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as m, \
             patch.object(mod.time, 'sleep'):
            m.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'completed'

    def test_non_retryable_404_not_retried(self):
        client = self._make_client()
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = 'Sandbox not found'

        with patch.object(client._client, 'post', return_value=resp_404) as mock_post, \
             patch('src.infrastructure.execution_service_client.get_auth_client') as m:
            m.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'failed'
        assert 'HTTP_404' in result['error_code']
        mock_post.assert_called_once()  # NOT retried

    def test_all_retries_exhausted_returns_transport_error(self):
        import src.infrastructure.execution_service_client as mod
        client = self._make_client()

        with patch.object(client._client, 'post',
                          side_effect=httpx.ConnectError('refused')), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as m, \
             patch.object(mod.time, 'sleep'):
            m.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'failed'
        assert result['error_code'] == 'TRANSPORT_ERROR'


import httpx
