"""Unit tests for Prometheus text parser (O8-S3)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from application.metrics_parser import MetricSample, parse_prometheus_text


class TestParsePrometheusText:
    """Parse Prometheus text format from MetricsRegistry output."""

    def test_counter_with_labels(self):
        text = 'mona_http_requests_total{service="gw",method="GET",route="/v1/tasks",status_class="2xx"} 42'
        samples = parse_prometheus_text(text)
        assert len(samples) == 1
        assert samples[0].metric_name == "mona_http_requests_total"
        assert samples[0].labels == {"service": "gw", "method": "GET", "route": "/v1/tasks", "status_class": "2xx"}
        assert samples[0].value == 42.0

    def test_counter_without_labels(self):
        text = 'mona_agent_budget_exhaustions_total 5'
        samples = parse_prometheus_text(text)
        assert len(samples) == 1
        assert samples[0].metric_name == "mona_agent_budget_exhaustions_total"
        assert samples[0].labels == {}
        assert samples[0].value == 5.0

    def test_float_value(self):
        text = 'mona_http_request_duration_ms_sum{service="orch",method="POST",route="/v1/tasks"} 1234.5'
        samples = parse_prometheus_text(text)
        assert len(samples) == 1
        assert samples[0].value == 1234.5

    def test_skip_comments(self):
        text = """# HELP mona_http_requests_total Total HTTP requests
# TYPE mona_http_requests_total counter
mona_http_requests_total{service="gw",method="GET",route="/test",status_class="2xx"} 10"""
        samples = parse_prometheus_text(text)
        assert len(samples) == 1
        assert samples[0].value == 10.0

    def test_skip_blank_lines(self):
        text = """

mona_test_counter 1

mona_test_counter2 2

"""
        samples = parse_prometheus_text(text)
        assert len(samples) == 2

    def test_empty_input(self):
        assert parse_prometheus_text("") == []
        assert parse_prometheus_text("# only comments\n# here") == []

    def test_multiple_metrics(self):
        text = """# TYPE mona_http_requests_total counter
mona_http_requests_total{service="gw",method="GET",route="/a",status_class="2xx"} 10
mona_http_requests_total{service="gw",method="POST",route="/b",status_class="5xx"} 3
mona_agent_invocations_total{status="completed"} 7
mona_agent_budget_exhaustions_total 1"""
        samples = parse_prometheus_text(text)
        assert len(samples) == 4
        names = [s.metric_name for s in samples]
        assert "mona_http_requests_total" in names
        assert "mona_agent_invocations_total" in names
        assert "mona_agent_budget_exhaustions_total" in names

    def test_invalid_line_skipped(self):
        text = """mona_valid_counter 5
this is not a metric line
mona_valid_counter2 10"""
        samples = parse_prometheus_text(text)
        assert len(samples) == 2
