"""Unit tests for O8-S2 agent-runtime operational metrics.

Tests:
- RuntimeMetrics increments correct counters
- Counters appear in Prometheus output
- No double counting
- Uninitialized metrics don't crash
"""

import os
import sys

# Add both packages/logger and apps/agent-runtime to path for imports
_base = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.normpath(os.path.join(_base, '..', '..', 'packages', 'logger')))

os.environ.setdefault('SERVICE_NAME', 'agent-runtime')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ['TOOL_APPROVAL_MODE'] = 'none'

from mona_os_logger.metrics import MetricsRegistry

# Import RuntimeMetrics — the class under test
# Uses importlib to avoid pytest import mode conflicts
import importlib.util
_rm_path = os.path.join(_base, 'src', 'application', 'runtime_metrics.py')
_spec = importlib.util.spec_from_file_location("runtime_metrics", _rm_path,
    submodule_search_locations=[os.path.join(_base, 'src', 'application')])
_mod = importlib.util.module_from_spec(_spec)
sys.modules['src.application.runtime_metrics'] = _mod  # satisfy internal imports
_spec.loader.exec_module(_mod)
RuntimeMetrics = _mod.RuntimeMetrics


class TestRuntimeMetricsSetup:
    """Counter registration and basic increment."""

    def test_setup_registers_counters(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        text = reg.prometheus_text()
        assert 'mona_agent_invocations_total' in text
        assert 'mona_agent_tool_calls_total' in text
        assert 'mona_agent_tool_failures_total' in text
        assert 'mona_agent_budget_exhaustions_total' in text
        assert 'mona_agent_human_gates_total' in text

    def test_uninitialized_does_not_crash(self):
        rm = RuntimeMetrics()
        # Should silently do nothing — no registry set
        rm.inc_invocation("completed")
        rm.inc_tool_call("completed")
        rm.inc_tool_failure("UNKNOWN")
        rm.inc_budget_exhaustion()
        rm.inc_human_gate("approved")


class TestInvocationCounters:
    """Invocation lifecycle counters."""

    def test_invocation_started(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_invocation("started")
        rm.inc_invocation("started")
        text = reg.prometheus_text()
        assert 'mona_agent_invocations_total{status="started"} 2' in text

    def test_invocation_completed(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_invocation("completed")
        text = reg.prometheus_text()
        assert 'mona_agent_invocations_total{status="completed"} 1' in text

    def test_invocation_failed(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_invocation("failed")
        text = reg.prometheus_text()
        assert 'mona_agent_invocations_total{status="failed"} 1' in text

    def test_invocation_timed_out(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_invocation("timed_out")
        text = reg.prometheus_text()
        assert 'mona_agent_invocations_total{status="timed_out"} 1' in text

    def test_multiple_statuses(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_invocation("started")
        rm.inc_invocation("completed")
        rm.inc_invocation("started")
        rm.inc_invocation("failed")
        text = reg.prometheus_text()
        assert 'status="started"} 2' in text
        assert 'status="completed"} 1' in text
        assert 'status="failed"} 1' in text


class TestToolCounters:
    """Tool call and failure counters."""

    def test_tool_call_completed(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_tool_call("completed")
        rm.inc_tool_call("completed")
        rm.inc_tool_call("failed")
        text = reg.prometheus_text()
        assert 'mona_agent_tool_calls_total{status="completed"} 2' in text
        assert 'mona_agent_tool_calls_total{status="failed"} 1' in text

    def test_tool_failure_by_error_code(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_tool_failure("GUARDRAIL_REJECTED")
        rm.inc_tool_failure("GUARDRAIL_REJECTED")
        rm.inc_tool_failure("TRANSPORT_ERROR")
        text = reg.prometheus_text()
        assert 'error_code="GUARDRAIL_REJECTED"} 2' in text
        assert 'error_code="TRANSPORT_ERROR"} 1' in text


class TestBudgetAndHumanGate:
    """Budget exhaustion and human gate counters."""

    def test_budget_exhaustion(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_budget_exhaustion()
        rm.inc_budget_exhaustion()
        text = reg.prometheus_text()
        assert 'mona_agent_budget_exhaustions_total 2' in text

    def test_human_gate_decisions(self):
        reg = MetricsRegistry(service="test")
        rm = RuntimeMetrics()
        rm.setup(reg)
        rm.inc_human_gate("gate_entered")
        rm.inc_human_gate("approved")
        rm.inc_human_gate("rejected")
        rm.inc_human_gate("override")
        rm.inc_human_gate("cancel")
        text = reg.prometheus_text()
        assert 'decision="gate_entered"} 1' in text
        assert 'decision="approved"} 1' in text
        assert 'decision="rejected"} 1' in text
        assert 'decision="override"} 1' in text
        assert 'decision="cancel"} 1' in text
