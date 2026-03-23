"""Timeout budget — tracks remaining time across service hops.

A TimeoutBudget is created at the entry point with a total budget, then
passed (or decremented) through each hop. Each service can ask the budget
for remaining time and use it for its own timeout configuration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Minimum useful timeout — below this we consider the budget exhausted.
_MIN_USEFUL_MS = 500


@dataclass(slots=True)
class TimeoutBudget:
    """Tracks remaining timeout across a multi-hop request chain.

    Created once at the edge with total_ms, then decremented as time passes
    or as overhead is deducted for each hop.

    Attributes:
        total_ms: The original budget in milliseconds.
        _start_time: Monotonic time when budget was created.
    """

    total_ms: int
    _start_time: float

    def __init__(self, total_ms: int) -> None:
        if total_ms <= 0:
            raise ValueError(f"total_ms must be positive, got {total_ms}")
        self.total_ms = total_ms
        self._start_time = time.monotonic()

    @property
    def elapsed_ms(self) -> int:
        """Milliseconds elapsed since budget was created."""
        return int((time.monotonic() - self._start_time) * 1000)

    @property
    def remaining_ms(self) -> int:
        """Milliseconds remaining in the budget (floored at 0)."""
        return max(0, self.total_ms - self.elapsed_ms)

    @property
    def is_exhausted(self) -> bool:
        """True if remaining time is below the minimum useful threshold."""
        return self.remaining_ms < _MIN_USEFUL_MS

    def remaining_for_downstream(self, overhead_ms: int = 0) -> int:
        """Calculate timeout to pass to downstream service.

        Args:
            overhead_ms: Reserved for local processing after downstream returns.

        Returns:
            Remaining ms minus overhead, floored at 0.
        """
        return max(0, self.remaining_ms - overhead_ms)

    def remaining_seconds(self, overhead_ms: int = 0) -> float:
        """Remaining budget in seconds (for httpx timeout param)."""
        return self.remaining_for_downstream(overhead_ms) / 1000

    @classmethod
    def from_remaining_ms(cls, remaining_ms: int) -> TimeoutBudget:
        """Create a budget that appears to have started with remaining_ms left.

        Useful when receiving a timeout_ms from an upstream caller —
        we don't know when they started, but we know how much time
        we have left.
        """
        budget = cls.__new__(cls)
        budget.total_ms = remaining_ms
        budget._start_time = time.monotonic()
        return budget
