"""Unit tests for SSE formatting helper."""

import json

from src.api.routes import _format_sse


class TestFormatSSE:
    def test_basic_format(self):
        data = {'event_type': 'task.created', 'task_id': 'abc'}
        result = _format_sse(data, 'evt-123')

        assert result.startswith('id:evt-123\n')
        assert 'event:task.created\n' in result
        assert result.endswith('\n\n')

    def test_data_is_json(self):
        data = {'event_type': 'run.started', 'run_id': 'r-1'}
        result = _format_sse(data, 'evt-456')

        lines = result.strip().split('\n')
        data_line = [l for l in lines if l.startswith('data:')][0]
        parsed = json.loads(data_line[len('data:'):])
        assert parsed['event_type'] == 'run.started'
        assert parsed['run_id'] == 'r-1'

    def test_event_type_fallback(self):
        data = {'some_field': 'value'}  # no event_type
        result = _format_sse(data, 'evt-789')
        assert 'event:message\n' in result

    def test_event_id_in_output(self):
        data = {'event_type': 'step.completed'}
        eid = 'abc-def-123'
        result = _format_sse(data, eid)
        assert f'id:{eid}\n' in result
