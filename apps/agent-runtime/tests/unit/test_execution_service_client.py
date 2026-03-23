"""Unit tests for execution service client (O3-S2)."""

import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')


class TestExecutionServicePortContract:
    """ExecutionServicePort ABC has call_tool method."""

    def test_port_is_abstract(self):
        from src.application.ports import ExecutionServicePort
        with pytest.raises(TypeError):
            ExecutionServicePort()  # type: ignore

    def test_call_tool_signature(self):
        from src.application.ports import ExecutionServicePort
        import inspect
        sig = inspect.signature(ExecutionServicePort.call_tool)
        params = list(sig.parameters.keys())
        assert 'sandbox_id' in params
        assert 'tool_name' in params
        assert 'tool_input' in params


class TestHttpExecutionServiceClient:
    """HttpExecutionServiceClient HTTP behavior."""

    def _make_client(self, base_url='http://execution-service:8000'):
        from src.infrastructure.execution_service_client import HttpExecutionServiceClient
        return HttpExecutionServiceClient(base_url=base_url)

    def test_success_returns_response_dict(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {
            'status': 'completed',
            'stdout': 'hello world\n',
            'stderr': '',
            'exit_code': 0,
            'sandbox_id': str(uuid4()),
            'attempt_index': 0,
        }

        with patch.object(client._client, 'post', return_value=mock_resp), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth:
            mock_auth.return_value.auth_headers.return_value = {}
            result = client.call_tool(
                sandbox_id=uuid4(), tool_name='python.run_script',
                tool_input={'code': 'print("hello world")'},
            )

        assert result['status'] == 'completed'
        assert result['stdout'] == 'hello world\n'

    def test_non_202_returns_failed_dict(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = 'Sandbox not found'

        with patch.object(client._client, 'post', return_value=mock_resp), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth:
            mock_auth.return_value.auth_headers.return_value = {}
            result = client.call_tool(
                sandbox_id=uuid4(), tool_name='shell.exec',
                tool_input={'command': 'ls'},
            )

        assert result['status'] == 'failed'
        assert 'HTTP_404' in result['error_code']

    def test_connection_error_retries_then_returns_failed(self):
        """O4-S3: connection errors are retried, then return failed dict (not raise)."""
        import httpx
        import src.infrastructure.execution_service_client as mod
        client = self._make_client()

        with patch.object(client._client, 'post', side_effect=httpx.ConnectError('refused')), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth, \
             patch.object(mod.time, 'sleep'):
            mock_auth.return_value.auth_headers.return_value = {}
            result = client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert result['status'] == 'failed'
        assert result['error_code'] == 'TRANSPORT_ERROR'

    def test_correct_url_called(self):
        client = self._make_client('http://exec:8000')
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {'status': 'completed'}
        captured = {}

        def capture_post(url, **kwargs):
            captured['url'] = url
            captured['json'] = kwargs.get('json')
            return mock_resp

        with patch.object(client._client, 'post', side_effect=capture_post), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth:
            mock_auth.return_value.auth_headers.return_value = {}
            sid = uuid4()
            client.call_tool(
                sandbox_id=sid, tool_name='python.run_script',
                tool_input={'code': '1+1'}, attempt_index=2,
            )

        assert captured['url'] == 'http://exec:8000/internal/v1/tool-executions'
        assert captured['json']['sandbox_id'] == str(sid)
        assert captured['json']['tool_name'] == 'python.run_script'
        assert captured['json']['attempt_index'] == 2

    def test_default_attempt_index_zero(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {'status': 'completed'}
        captured = {}

        def capture_post(url, **kwargs):
            captured['json'] = kwargs.get('json')
            return mock_resp

        with patch.object(client._client, 'post', side_effect=capture_post), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth:
            mock_auth.return_value.auth_headers.return_value = {}
            client.call_tool(sandbox_id=uuid4(), tool_name='test', tool_input={})

        assert captured['json']['attempt_index'] == 0

    def test_timeout_ms_passed(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.json.return_value = {'status': 'completed'}
        captured = {}

        def capture_post(url, **kwargs):
            captured['json'] = kwargs.get('json')
            return mock_resp

        with patch.object(client._client, 'post', side_effect=capture_post), \
             patch('src.infrastructure.execution_service_client.get_auth_client') as mock_auth:
            mock_auth.return_value.auth_headers.return_value = {}
            client.call_tool(
                sandbox_id=uuid4(), tool_name='test',
                tool_input={}, timeout_ms=60_000,
            )

        assert captured['json']['timeout_ms'] == 60_000


class TestHandlerAcceptsExecutionService:
    """ExecuteInvocationHandler accepts optional execution_service."""

    def test_handler_init_without_execution_service(self):
        from src.application.execution_handler import ExecuteInvocationHandler
        handler = ExecuteInvocationHandler(
            unit_of_work=MagicMock(),
            gateway=MagicMock(),
        )
        assert handler._execution_service is None

    def test_handler_init_with_execution_service(self):
        from src.application.execution_handler import ExecuteInvocationHandler
        mock_exec = MagicMock()
        handler = ExecuteInvocationHandler(
            unit_of_work=MagicMock(),
            gateway=MagicMock(),
            execution_service=mock_exec,
        )
        assert handler._execution_service is mock_exec
