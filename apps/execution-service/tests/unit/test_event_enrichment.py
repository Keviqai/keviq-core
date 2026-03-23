"""Unit tests for O6-S1 tool execution event enrichment.

Tests that event factories correctly include duration_ms, exit_code,
truncated, and stdout_size_bytes fields when provided.
"""

import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from application.events import (
    tool_execution_succeeded_event,
    tool_execution_failed_event,
)


class TestSucceededEventEnrichment:
    """sandbox.tool_execution.succeeded event payload enrichment."""

    def test_includes_duration(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0, duration_ms=1234,
        )
        assert evt.payload["duration_ms"] == 1234

    def test_includes_truncated(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0, truncated=True,
        )
        assert evt.payload["truncated"] is True

    def test_includes_stdout_size_bytes(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0, stdout_size_bytes=5000,
        )
        assert evt.payload["stdout_size_bytes"] == 5000

    def test_all_enriched_fields(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="python.run_script", attempt_index=1,
            exit_code=0, duration_ms=567, truncated=True, stdout_size_bytes=32768,
        )
        assert evt.payload["duration_ms"] == 567
        assert evt.payload["truncated"] is True
        assert evt.payload["stdout_size_bytes"] == 32768
        assert evt.payload["exit_code"] == 0

    def test_optional_fields_absent_when_not_provided(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0,
        )
        assert "duration_ms" not in evt.payload
        assert "truncated" not in evt.payload
        assert "stdout_size_bytes" not in evt.payload
        # exit_code is always present (required param)
        assert evt.payload["exit_code"] == 0

    def test_truncated_false_not_included(self):
        """truncated=False should not be in payload (additive schema)."""
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0, truncated=False,
        )
        assert "truncated" not in evt.payload

    def test_backward_compat_existing_fields(self):
        evt = tool_execution_succeeded_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            exit_code=0,
        )
        assert "tool_name" in evt.payload
        assert "attempt_index" in evt.payload
        assert "execution_id" in evt.payload
        assert evt.event_type == "sandbox.tool_execution.succeeded"


class TestFailedEventEnrichment:
    """sandbox.tool_execution.failed event payload enrichment."""

    def test_includes_duration_and_exit_code(self):
        evt = tool_execution_failed_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="python.run_script", attempt_index=1,
            error_code="NON_ZERO_EXIT", error_message="exit_code=1",
            duration_ms=5678, exit_code=1,
        )
        assert evt.payload["duration_ms"] == 5678
        assert evt.payload["exit_code"] == 1

    def test_optional_fields_absent_when_not_provided(self):
        evt = tool_execution_failed_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            error_code="EXECUTION_TIMEOUT", error_message="timed out",
        )
        assert "duration_ms" not in evt.payload
        assert "exit_code" not in evt.payload

    def test_error_fields_present(self):
        evt = tool_execution_failed_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
            error_code="EXECUTION_ERROR", error_message="connection reset",
            duration_ms=100,
        )
        assert evt.payload["error_code"] == "EXECUTION_ERROR"
        assert evt.payload["error_message"] == "connection reset"
        assert evt.payload["duration_ms"] == 100

    def test_backward_compat_existing_fields(self):
        evt = tool_execution_failed_event(
            sandbox_id=uuid4(), workspace_id=uuid4(), correlation_id=uuid4(),
            execution_id=uuid4(), tool_name="shell.exec", attempt_index=0,
        )
        assert "tool_name" in evt.payload
        assert "attempt_index" in evt.payload
        assert evt.event_type == "sandbox.tool_execution.failed"
