"""Retry with exponential backoff and jitter.

Provides a composable retry policy that classifies errors as transient
or permanent, then retries only transient failures with bounded backoff.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes considered transient (safe to retry).
TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Configuration for bounded retry with exponential backoff.

    Attributes:
        max_attempts: Total attempts including the first try (min 1).
        base_delay_s: Initial delay between retries in seconds.
        max_delay_s: Upper bound on delay (caps exponential growth).
        jitter: If True, add random jitter to avoid thundering herd.
    """

    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 10.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            object.__setattr__(self, "max_attempts", 1)

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay in seconds for the given attempt (0-indexed).

        Uses exponential backoff: base_delay * 2^attempt, capped at max_delay.
        When jitter is enabled, the delay is uniformly distributed in [0, delay].
        """
        delay = min(self.base_delay_s * (2 ** attempt), self.max_delay_s)
        if self.jitter:
            delay = random.uniform(0, delay)  # noqa: S311
        return delay


def is_retryable_status_code(status_code: int) -> bool:
    """Return True if the HTTP status code is transient."""
    return status_code in TRANSIENT_STATUS_CODES


def retry_with_backoff(
    fn: Callable[[], T],
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool],
    *,
    operation_name: str = "operation",
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Execute fn with retry according to policy.

    Args:
        fn: Zero-arg callable to execute. Called repeatedly on transient failure.
        policy: Retry configuration (attempts, delays, jitter).
        is_retryable: Predicate that returns True if the exception is transient.
            Permanent errors are raised immediately without retry.
        operation_name: Label for log messages.
        sleep_fn: Injectable sleep for testing (default: time.sleep).

    Returns:
        The return value of fn on success.

    Raises:
        The last exception if all attempts are exhausted, or a permanent error
        immediately.
    """
    last_exc: Exception | None = None

    for attempt in range(policy.max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc

            if not is_retryable(exc):
                logger.debug(
                    "%s: permanent error on attempt %d/%d, not retrying: %s",
                    operation_name, attempt + 1, policy.max_attempts, exc,
                )
                raise

            remaining = policy.max_attempts - attempt - 1
            if remaining <= 0:
                logger.warning(
                    "%s: exhausted %d attempts, last error: %s",
                    operation_name, policy.max_attempts, exc,
                )
                raise

            delay = policy.delay_for_attempt(attempt)
            logger.info(
                "%s: transient error on attempt %d/%d, retrying in %.2fs: %s",
                operation_name, attempt + 1, policy.max_attempts, delay, exc,
            )
            sleep_fn(delay)

    # Should not reach here, but satisfy type checker
    assert last_exc is not None  # noqa: S101
    raise last_exc
