"""Unit tests for MetricsRegistry and Prometheus text output (O8-S1).

Tests:
- Counter increments correctly
- Prometheus text format valid
- Route normalization (UUID → {id})
- Error counting (4xx + 5xx)
- Duration tracking
- Custom counters
- Empty registry produces valid output
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mona_os_logger.metrics import MetricsRegistry, _normalize_route


class TestRouteNormalization:
    """UUID segments replaced with {id} to prevent cardinality explosion."""

    def test_uuid_replaced(self):
        path = '/v1/tasks/550e8400-e29b-41d4-a716-446655440000'
        assert _normalize_route(path) == '/v1/tasks/{id}'

    def test_multiple_uuids(self):
        path = '/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/approvals/660e8400-e29b-41d4-a716-446655440001'
        assert _normalize_route(path) == '/v1/workspaces/{id}/approvals/{id}'

    def test_no_uuid_unchanged(self):
        assert _normalize_route('/v1/tasks') == '/v1/tasks'

    def test_trailing_slash_stripped(self):
        assert _normalize_route('/v1/tasks/') == '/v1/tasks'

    def test_root_path(self):
        assert _normalize_route('/') == '/'


class TestMetricsRegistry:
    """Core counter behavior."""

    def test_record_request_increments_total(self):
        reg = MetricsRegistry(service="test")
        reg.record_request("GET", "/v1/tasks", 200, 15.5)
        reg.record_request("GET", "/v1/tasks", 200, 20.0)

        text = reg.prometheus_text()
        assert 'mona_http_requests_total{service="test",method="GET",route="/v1/tasks",status_class="2xx"} 2' in text

    def test_different_status_classes(self):
        reg = MetricsRegistry(service="test")
        reg.record_request("GET", "/v1/tasks", 200, 10.0)
        reg.record_request("GET", "/v1/tasks", 404, 5.0)
        reg.record_request("GET", "/v1/tasks", 500, 3.0)

        text = reg.prometheus_text()
        assert 'status_class="2xx"} 1' in text
        assert 'status_class="4xx"} 1' in text
        assert 'status_class="5xx"} 1' in text

    def test_error_counter_for_4xx_and_5xx(self):
        reg = MetricsRegistry(service="test")
        reg.record_request("GET", "/v1/tasks", 200, 10.0)
        reg.record_request("GET", "/v1/tasks", 400, 5.0)
        reg.record_request("POST", "/v1/tasks", 500, 3.0)

        text = reg.prometheus_text()
        assert 'mona_http_request_errors_total' in text
        assert 'status_code="400"} 1' in text
        assert 'status_code="500"} 1' in text

    def test_200_not_in_errors(self):
        reg = MetricsRegistry(service="test")
        reg.record_request("GET", "/v1/tasks", 200, 10.0)

        text = reg.prometheus_text()
        # Should have no error lines (only HELP/TYPE headers)
        error_lines = [l for l in text.split('\n') if l.startswith('mona_http_request_errors_total{')]
        assert len(error_lines) == 0

    def test_duration_sum_and_count(self):
        reg = MetricsRegistry(service="test")
        reg.record_request("GET", "/api", 200, 10.5)
        reg.record_request("GET", "/api", 200, 20.5)

        text = reg.prometheus_text()
        assert 'mona_http_request_duration_ms_sum{service="test",method="GET",route="/api"} 31.0' in text
        assert 'mona_http_request_duration_ms_count{service="test",method="GET",route="/api"} 2' in text

    def test_empty_registry_valid_output(self):
        reg = MetricsRegistry(service="empty")
        text = reg.prometheus_text()
        assert '# HELP mona_http_requests_total' in text
        assert '# TYPE mona_http_requests_total counter' in text
        # No data lines — just headers
        data_lines = [l for l in text.split('\n') if l and not l.startswith('#')]
        assert len(data_lines) == 0

    def test_service_label_correct(self):
        reg = MetricsRegistry(service="api-gateway")
        reg.record_request("GET", "/test", 200, 5.0)
        text = reg.prometheus_text()
        assert 'service="api-gateway"' in text


class TestCustomCounters:
    """Custom counters for domain metrics (O8-S2 readiness)."""

    def test_register_and_increment(self):
        reg = MetricsRegistry(service="test")
        reg.register_counter("agent_invocations_total", ("status",))
        reg.inc_counter("agent_invocations_total", ("completed",))
        reg.inc_counter("agent_invocations_total", ("completed",))
        reg.inc_counter("agent_invocations_total", ("failed",))

        text = reg.prometheus_text()
        assert 'agent_invocations_total{status="completed"} 2' in text
        assert 'agent_invocations_total{status="failed"} 1' in text

    def test_unregistered_counter_ignored(self):
        reg = MetricsRegistry(service="test")
        reg.inc_counter("nonexistent", ("x",))  # should not raise
        text = reg.prometheus_text()
        assert 'nonexistent' not in text


class TestPrometheusFormat:
    """Output format compliance."""

    def test_help_and_type_headers(self):
        reg = MetricsRegistry(service="test")
        text = reg.prometheus_text()
        assert '# HELP mona_http_requests_total' in text
        assert '# TYPE mona_http_requests_total counter' in text
        assert '# HELP mona_http_request_duration_ms_sum' in text
        assert '# HELP mona_http_request_errors_total' in text

    def test_response_media_type(self):
        reg = MetricsRegistry(service="test")
        resp = reg.prometheus_response()
        assert resp.media_type == 'text/plain; version=0.0.4; charset=utf-8'
