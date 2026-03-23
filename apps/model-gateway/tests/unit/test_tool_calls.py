"""Unit tests for tool_calls support in model-gateway (O3-S1)."""

import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'model-gateway')
os.environ.setdefault('APP_ENV', 'development')


class TestProviderResponseToolCalls:
    """ProviderResponse includes tool_calls field."""

    def test_default_tool_calls_is_none(self):
        from src.domain.ports import ProviderResponse
        r = ProviderResponse(output_text='hello')
        assert r.tool_calls is None

    def test_tool_calls_set(self):
        from src.domain.ports import ProviderResponse
        tc = [{'id': 'call_1', 'type': 'function', 'function': {'name': 'run_script', 'arguments': '{}'}}]
        r = ProviderResponse(output_text='', tool_calls=tc, finish_reason='tool_calls')
        assert r.tool_calls == tc
        assert r.finish_reason == 'tool_calls'


class TestExecuteModelRequestTools:
    """ExecuteModelRequest includes tools field."""

    def test_default_tools_is_none(self):
        from src.domain.contracts import ExecuteModelRequest, ModelProfile
        req = ExecuteModelRequest(
            request_id=uuid4(), agent_invocation_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            model_profile=ModelProfile(model_alias='gpt-4'),
            messages=[{'role': 'user', 'content': 'hello'}],
        )
        assert req.tools is None

    def test_tools_set(self):
        from src.domain.contracts import ExecuteModelRequest, ModelProfile
        tools = [{'type': 'function', 'function': {'name': 'run_script', 'parameters': {}}}]
        req = ExecuteModelRequest(
            request_id=uuid4(), agent_invocation_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            model_profile=ModelProfile(model_alias='gpt-4'),
            messages=[{'role': 'user', 'content': 'hello'}],
            tools=tools,
        )
        assert req.tools == tools


class TestExecuteModelResultToolCalls:
    """ExecuteModelResult includes tool_calls field."""

    def test_default_tool_calls_none(self):
        from src.domain.contracts import ExecuteModelResult
        r = ExecuteModelResult(
            request_id=uuid4(), provider_name='openai',
            model_concrete='gpt-4', output_text='hi',
        )
        assert r.tool_calls is None

    def test_tool_calls_forwarded(self):
        from src.domain.contracts import ExecuteModelResult
        tc = [{'id': 'call_1', 'type': 'function', 'function': {'name': 'exec', 'arguments': '{}'}}]
        r = ExecuteModelResult(
            request_id=uuid4(), provider_name='openai',
            model_concrete='gpt-4', output_text='',
            finish_reason='tool_calls', tool_calls=tc,
        )
        assert r.tool_calls == tc


class TestOpenAIParseToolCalls:
    """OpenAICompatibleProvider._parse_response extracts tool_calls."""

    def _provider(self):
        from src.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            endpoint_url='https://api.openai.com/v1',
            api_key='test-key',
        )

    def test_response_without_tool_calls(self):
        p = self._provider()
        data = {
            'choices': [{'message': {'content': 'Hello!'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'model': 'gpt-4',
        }
        r = p._parse_response(data)
        assert r.output_text == 'Hello!'
        assert r.finish_reason == 'stop'
        assert r.tool_calls is None

    def test_response_with_tool_calls(self):
        p = self._provider()
        data = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [
                        {
                            'id': 'call_abc123',
                            'type': 'function',
                            'function': {
                                'name': 'run_script',
                                'arguments': '{"code": "print(1+1)"}',
                            },
                        },
                    ],
                },
                'finish_reason': 'tool_calls',
            }],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30},
            'model': 'gpt-4',
        }
        r = p._parse_response(data)
        assert r.output_text == ''
        assert r.finish_reason == 'tool_calls'
        assert r.tool_calls is not None
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0]['id'] == 'call_abc123'
        assert r.tool_calls[0]['function']['name'] == 'run_script'
        assert r.tool_calls[0]['function']['arguments'] == '{"code": "print(1+1)"}'

    def test_multiple_tool_calls(self):
        p = self._provider()
        data = {
            'choices': [{
                'message': {
                    'content': None,
                    'tool_calls': [
                        {'id': 'c1', 'type': 'function', 'function': {'name': 'tool_a', 'arguments': '{}'}},
                        {'id': 'c2', 'type': 'function', 'function': {'name': 'tool_b', 'arguments': '{"x":1}'}},
                    ],
                },
                'finish_reason': 'tool_calls',
            }],
            'usage': {},
            'model': 'gpt-4',
        }
        r = p._parse_response(data)
        assert len(r.tool_calls) == 2
        assert r.tool_calls[0]['function']['name'] == 'tool_a'
        assert r.tool_calls[1]['function']['name'] == 'tool_b'

    def test_empty_tool_calls_array_treated_as_none(self):
        p = self._provider()
        data = {
            'choices': [{'message': {'content': 'ok', 'tool_calls': []}, 'finish_reason': 'stop'}],
            'usage': {},
            'model': 'gpt-4',
        }
        r = p._parse_response(data)
        assert r.tool_calls is None
        assert r.finish_reason == 'stop'


class TestToolsPassedToProvider:
    """Tools parameter is included in request body when provided."""

    def test_tools_in_request_body(self):
        from src.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(
            endpoint_url='https://api.openai.com/v1',
            api_key='test-key',
        )
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'hi'}, 'finish_reason': 'stop'}],
            'usage': {},
            'model': 'gpt-4',
        }
        captured_body = {}

        def capture_post(url, json=None, headers=None, timeout=None):
            captured_body.update(json)
            return mock_response

        p._client.post = capture_post

        tools = [{'type': 'function', 'function': {'name': 'exec', 'parameters': {}}}]
        p.call(model_name='gpt-4', messages=[{'role': 'user', 'content': 'hi'}], tools=tools)

        assert 'tools' in captured_body
        assert captured_body['tools'] == tools

    def test_no_tools_not_in_body(self):
        from src.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
        p = OpenAICompatibleProvider(
            endpoint_url='https://api.openai.com/v1',
            api_key='test-key',
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'hi'}, 'finish_reason': 'stop'}],
            'usage': {},
            'model': 'gpt-4',
        }
        captured_body = {}

        def capture_post(url, json=None, headers=None, timeout=None):
            captured_body.update(json)
            return mock_response

        p._client.post = capture_post
        p.call(model_name='gpt-4', messages=[{'role': 'user', 'content': 'hi'}])

        assert 'tools' not in captured_body


class TestBackwardCompatibility:
    """Existing calls without tools still work."""

    def test_response_without_tools_unchanged(self):
        from src.domain.ports import ProviderResponse
        r = ProviderResponse(output_text='Hello', finish_reason='stop')
        assert r.output_text == 'Hello'
        assert r.finish_reason == 'stop'
        assert r.tool_calls is None

    def test_request_without_tools_unchanged(self):
        from src.domain.contracts import ExecuteModelRequest, ModelProfile
        req = ExecuteModelRequest(
            request_id=uuid4(), agent_invocation_id=uuid4(),
            workspace_id=uuid4(), correlation_id=uuid4(),
            model_profile=ModelProfile(model_alias='gpt-4'),
            messages=[{'role': 'user', 'content': 'hi'}],
        )
        assert req.tools is None
