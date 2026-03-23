"""Agent-runtime domain metrics — operational counters for invocation/tool loop.

O8-S2: Registers domain-specific counters on the shared MetricsRegistry.
All counters use low-cardinality labels only.

Usage:
    from src.application.runtime_metrics import setup_runtime_metrics, runtime_metrics

    setup_runtime_metrics(metrics_registry)
    runtime_metrics.inc_invocation("completed")
    runtime_metrics.inc_tool_call("shell.exec", "completed")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mona_os_logger.metrics import MetricsRegistry


class RuntimeMetrics:
    """Thin wrapper around MetricsRegistry for domain counter increments."""

    def __init__(self) -> None:
        self._registry: object | None = None  # MetricsRegistry, lazily typed

    def setup(self, registry: object) -> None:
        """Register all domain counters. Call once at startup."""
        self._registry = registry
        registry.register_counter("mona_agent_invocations_total", ("status",))
        registry.register_counter("mona_agent_tool_calls_total", ("status",))
        registry.register_counter("mona_agent_tool_failures_total", ("error_code",))
        registry.register_counter("mona_agent_budget_exhaustions_total", ())
        registry.register_counter("mona_agent_human_gates_total", ("decision",))

    def inc_invocation(self, status: str) -> None:
        """Increment invocation counter by terminal status."""
        if self._registry:
            self._registry.inc_counter("mona_agent_invocations_total", (status,))

    def inc_tool_call(self, status: str) -> None:
        """Increment tool call counter by outcome (completed/failed)."""
        if self._registry:
            self._registry.inc_counter("mona_agent_tool_calls_total", (status,))

    def inc_tool_failure(self, error_code: str) -> None:
        """Increment tool failure counter by error code."""
        if self._registry:
            self._registry.inc_counter("mona_agent_tool_failures_total", (error_code,))

    def inc_budget_exhaustion(self) -> None:
        """Increment budget exhaustion counter."""
        if self._registry:
            self._registry.inc_counter("mona_agent_budget_exhaustions_total", ())

    def inc_human_gate(self, decision: str) -> None:
        """Increment human gate counter by decision (approved/rejected/override/cancel)."""
        if self._registry:
            self._registry.inc_counter("mona_agent_human_gates_total", (decision,))


# Module-level singleton — safe to import anywhere in agent-runtime
runtime_metrics = RuntimeMetrics()


def setup_runtime_metrics(registry: object) -> None:
    """Register domain counters on the provided registry."""
    runtime_metrics.setup(registry)
