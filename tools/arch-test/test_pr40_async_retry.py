"""PR40 — Async execution model + retry/backoff foundation architecture gate tests.

Hard gates:
  C40-G1: Retries are bounded and classified
  C40-G2: Timeout budget is propagated consistently
  C40-G3: Async/background path does not break authority boundaries
  C40-G4: Duplicate work remains prevented
  C40-G5: Failure remains observable
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORCH_DIR = ROOT / "apps" / "orchestrator"
RUNTIME_DIR = ROOT / "apps" / "agent-runtime"
EXEC_DIR = ROOT / "apps" / "execution-service"
RESILIENCE_DIR = ROOT / "packages" / "resilience"


# ── C40-G1: Retries are bounded and classified ──────────────────


class TestRetriesBoundedAndClassified:
    """Retry logic must use RetryPolicy with bounded attempts, not unbounded loops."""

    def test_resilience_package_exists(self):
        """packages/resilience must exist with retry module."""
        assert (RESILIENCE_DIR / "resilience" / "retry.py").exists()
        assert (RESILIENCE_DIR / "resilience" / "timeout_budget.py").exists()

    def test_retry_policy_has_max_attempts(self):
        """RetryPolicy must define max_attempts."""
        content = (RESILIENCE_DIR / "resilience" / "retry.py").read_text()
        assert "max_attempts" in content

    def test_retry_policy_has_exponential_backoff(self):
        """RetryPolicy must implement exponential backoff."""
        content = (RESILIENCE_DIR / "resilience" / "retry.py").read_text()
        assert "base_delay_s" in content
        assert "max_delay_s" in content

    def test_runtime_client_uses_retry(self):
        """HttpRuntimeClient must use retry_with_backoff."""
        content = (ORCH_DIR / "src" / "infrastructure" / "runtime_client.py").read_text()
        assert "retry_with_backoff" in content
        assert "RetryPolicy" in content

    def test_execution_service_client_uses_retry(self):
        """HttpExecutionServiceClient must use retry for provision/terminate."""
        content = (ORCH_DIR / "src" / "infrastructure" / "execution_service_client.py").read_text()
        assert "retry_with_backoff" in content
        assert "_PROVISION_RETRY" in content

    def test_gateway_client_uses_retry(self):
        """ModelGatewayClient must use retry_with_backoff."""
        content = (RUNTIME_DIR / "src" / "infrastructure" / "gateway_client.py").read_text()
        assert "retry_with_backoff" in content

    def test_artifact_client_uses_retry(self):
        """ArtifactServiceClient must use retry_with_backoff."""
        content = (RUNTIME_DIR / "src" / "infrastructure" / "artifact_client.py").read_text()
        assert "retry_with_backoff" in content

    def test_retry_classifies_transient_errors(self):
        """is_retryable must be used to classify errors."""
        content = (RESILIENCE_DIR / "resilience" / "retry.py").read_text()
        assert "TRANSIENT_STATUS_CODES" in content
        assert "is_retryable_status_code" in content

    def test_no_unbounded_retry_loops(self):
        """No while True retry loops in infrastructure clients."""
        for path in [
            ORCH_DIR / "src" / "infrastructure" / "runtime_client.py",
            ORCH_DIR / "src" / "infrastructure" / "execution_service_client.py",
            RUNTIME_DIR / "src" / "infrastructure" / "gateway_client.py",
            RUNTIME_DIR / "src" / "infrastructure" / "artifact_client.py",
        ]:
            content = path.read_text()
            # Check no while True retry loops (recovery sweep is fine — it's not a retry)
            lines = content.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("while True") or stripped.startswith("while 1"):
                    pytest.fail(
                        f"Unbounded retry loop found in {path.name}:{i+1}"
                    )


# ── C40-G2: Timeout budget is propagated consistently ───────────


class TestTimeoutBudgetPropagated:
    """Timeout budget must flow through the call chain, not be invented per-hop."""

    def test_timeout_budget_module_exists(self):
        """TimeoutBudget must be defined in resilience package."""
        content = (RESILIENCE_DIR / "resilience" / "timeout_budget.py").read_text()
        assert "class TimeoutBudget" in content

    def test_runtime_client_uses_timeout_budget(self):
        """HttpRuntimeClient must create TimeoutBudget from timeout_ms."""
        content = (ORCH_DIR / "src" / "infrastructure" / "runtime_client.py").read_text()
        assert "TimeoutBudget" in content

    def test_execution_client_uses_timeout_budget(self):
        """execute_tool must use TimeoutBudget for downstream propagation."""
        content = (ORCH_DIR / "src" / "infrastructure" / "execution_service_client.py").read_text()
        assert "TimeoutBudget" in content

    def test_gateway_client_uses_timeout_budget(self):
        """ModelGatewayClient must use TimeoutBudget."""
        content = (RUNTIME_DIR / "src" / "infrastructure" / "gateway_client.py").read_text()
        assert "TimeoutBudget" in content

    def test_timeout_budget_has_remaining_for_downstream(self):
        """TimeoutBudget must support downstream overhead deduction."""
        content = (RESILIENCE_DIR / "resilience" / "timeout_budget.py").read_text()
        assert "remaining_for_downstream" in content
        assert "overhead_ms" in content


# ── C40-G3: Background path does not break authority ────────────


class TestBackgroundPathAuthority:
    """Background workers must not bypass domain state transitions."""

    def test_outbox_relay_does_not_mutate_domain(self):
        """Outbox relay must only update outbox rows, not domain entities."""
        relay_path = ORCH_DIR / "src" / "infrastructure" / "outbox" / "relay.py"
        content = relay_path.read_text()
        # Relay should not import domain entities
        assert "from src.domain" not in content

    def test_recovery_uses_domain_transitions(self):
        """Recovery sweep must use domain methods, not raw SQL updates."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()
        # Must use domain transitions
        assert "run.fail(" in content or "run.complete(" in content
        # Must not use raw SQL
        assert "session.execute" not in content
        assert "UPDATE " not in content

    def test_retry_logic_not_in_domain_layer(self):
        """Domain layer must not contain retry logic."""
        domain_dir = ORCH_DIR / "src" / "domain"
        for py_file in domain_dir.glob("*.py"):
            content = py_file.read_text()
            assert "retry_with_backoff" not in content, (
                f"retry logic found in domain file: {py_file.name}"
            )
            assert "RetryPolicy" not in content, (
                f"RetryPolicy found in domain file: {py_file.name}"
            )


# ── C40-G4: Duplicate work remains prevented ───────────────────


class TestDuplicateWorkPrevented:
    """Retry/backoff must not create duplicate processing."""

    def test_recovery_still_uses_skip_locked(self):
        """Recovery must still use FOR UPDATE SKIP LOCKED."""
        repo_path = ORCH_DIR / "src" / "infrastructure" / "db" / "repositories.py"
        content = repo_path.read_text()
        assert "with_for_update(skip_locked=True)" in content

    def test_recovery_still_has_idempotency_guards(self):
        """Recovery must still check is_terminal and status changes."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()
        assert "is_terminal" in content
        assert "skipped_no_longer_stuck" in content

    def test_execute_tool_not_auto_retried(self):
        """execute_tool must NOT be auto-retried (caller decides)."""
        content = (ORCH_DIR / "src" / "infrastructure" / "execution_service_client.py").read_text()
        # Find the execute_tool method and verify no retry_with_backoff in it
        lines = content.split("\n")
        in_execute_tool = False
        in_next_method = False
        execute_tool_body = []
        for line in lines:
            if "def execute_tool(" in line:
                in_execute_tool = True
                continue
            if in_execute_tool and line.strip().startswith("def "):
                break
            if in_execute_tool:
                execute_tool_body.append(line)
        body = "\n".join(execute_tool_body)
        assert "retry_with_backoff" not in body, (
            "execute_tool must not auto-retry — caller decides"
        )


# ── C40-G5: Failure remains observable ──────────────────────────


class TestFailureObservable:
    """Retry, timeout, exhausted attempts must be logged/observable."""

    def test_retry_module_logs_retries(self):
        """retry_with_backoff must log transient errors and exhaustion."""
        content = (RESILIENCE_DIR / "resilience" / "retry.py").read_text()
        assert "logger.info" in content or "logger.warning" in content

    def test_recovery_sweep_logs_results(self):
        """Recovery sweep loop must log sweep results."""
        content = (ORCH_DIR / "src" / "main.py").read_text()
        assert "logger" in content
        # Check recovery loop logs
        assert "Recovery sweep" in content

    def test_outbox_relay_logs_failures(self):
        """Outbox relay must log relay failures."""
        content = (ORCH_DIR / "src" / "infrastructure" / "outbox" / "relay.py").read_text()
        assert "logger.error" in content or "logger.warning" in content

    def test_outbox_relay_backgrounded(self):
        """Outbox relay must run as a background task."""
        content = (ORCH_DIR / "src" / "main.py").read_text()
        assert "_outbox_relay_loop" in content
        assert "relay_task" in content


# ── C40-G6: Connection reuse and lifecycle ──────────────────────


class TestConnectionLifecycle:
    """HTTP clients must be reused, not created per-request."""

    def test_outbox_relay_uses_shared_client(self):
        """Outbox relay must not create a new httpx.Client per call."""
        content = (ORCH_DIR / "src" / "infrastructure" / "outbox" / "relay.py").read_text()
        assert "get_relay_client" in content
        assert "close_relay_client" in content
        # Must not have "with httpx.Client" (per-call client creation)
        assert "with httpx.Client" not in content

    def test_orchestrator_lifespan_closes_clients(self):
        """Orchestrator lifespan must close all clients on shutdown."""
        content = (ORCH_DIR / "src" / "main.py").read_text()
        assert "close_relay_client" in content
        assert "_runtime_client.close()" in content

    def test_execution_service_uses_lifespan(self):
        """Execution-service must use lifespan, not deprecated on_event."""
        content = (EXEC_DIR / "src" / "main.py").read_text()
        assert "lifespan" in content
        assert "@app.on_event" not in content
