"""Unit tests for resilience.retry module."""

from __future__ import annotations

import pytest

from resilience.retry import (
    RetryPolicy,
    is_retryable_status_code,
    retry_with_backoff,
)


# ── RetryPolicy ─────────────────────────────────────────────────


class TestRetryPolicy:
    def test_default_policy(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.base_delay_s == 0.5
        assert p.max_delay_s == 10.0
        assert p.jitter is True

    def test_min_attempts_clamped(self):
        p = RetryPolicy(max_attempts=0)
        assert p.max_attempts == 1

    def test_delay_exponential(self):
        p = RetryPolicy(base_delay_s=1.0, max_delay_s=100.0, jitter=False)
        assert p.delay_for_attempt(0) == 1.0
        assert p.delay_for_attempt(1) == 2.0
        assert p.delay_for_attempt(2) == 4.0
        assert p.delay_for_attempt(3) == 8.0

    def test_delay_capped_at_max(self):
        p = RetryPolicy(base_delay_s=1.0, max_delay_s=3.0, jitter=False)
        assert p.delay_for_attempt(5) == 3.0

    def test_delay_with_jitter_bounded(self):
        p = RetryPolicy(base_delay_s=1.0, max_delay_s=100.0, jitter=True)
        for _ in range(50):
            d = p.delay_for_attempt(0)
            assert 0.0 <= d <= 1.0


# ── is_retryable_status_code ─────────────────────────────────────


class TestRetryableStatusCode:
    @pytest.mark.parametrize("code", [429, 502, 503, 504])
    def test_transient_codes(self, code: int):
        assert is_retryable_status_code(code) is True

    @pytest.mark.parametrize("code", [200, 400, 401, 403, 404, 500])
    def test_non_transient_codes(self, code: int):
        assert is_retryable_status_code(code) is False


# ── retry_with_backoff ───────────────────────────────────────────


class TestRetryWithBackoff:
    def test_succeeds_first_try(self):
        result = retry_with_backoff(
            lambda: 42,
            RetryPolicy(max_attempts=3),
            is_retryable=lambda _: True,
            operation_name="test",
        )
        assert result == 42

    def test_retries_on_transient_then_succeeds(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "ok"

        result = retry_with_backoff(
            flaky,
            RetryPolicy(max_attempts=3, base_delay_s=0.01),
            is_retryable=lambda exc: isinstance(exc, ValueError),
            operation_name="test",
            sleep_fn=lambda _: None,
        )
        assert result == "ok"
        assert call_count == 3

    def test_raises_on_permanent_error(self):
        class PermanentError(Exception):
            pass

        class TransientError(Exception):
            pass

        with pytest.raises(PermanentError):
            retry_with_backoff(
                lambda: (_ for _ in ()).throw(PermanentError("fatal")),
                RetryPolicy(max_attempts=5),
                is_retryable=lambda exc: isinstance(exc, TransientError),
                operation_name="test",
                sleep_fn=lambda _: None,
            )

    def test_exhausted_retries_raises_last_error(self):
        call_count = 0

        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"attempt {call_count}")

        with pytest.raises(ValueError, match="attempt 3"):
            retry_with_backoff(
                always_fails,
                RetryPolicy(max_attempts=3, base_delay_s=0.01),
                is_retryable=lambda _: True,
                operation_name="test",
                sleep_fn=lambda _: None,
            )
        assert call_count == 3

    def test_sleep_fn_called_between_retries(self):
        delays: list[float] = []

        def always_fails():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            retry_with_backoff(
                always_fails,
                RetryPolicy(max_attempts=3, base_delay_s=1.0, jitter=False),
                is_retryable=lambda _: True,
                operation_name="test",
                sleep_fn=delays.append,
            )
        # 2 retries = 2 sleeps
        assert len(delays) == 2
        assert delays[0] == 1.0  # attempt 0
        assert delays[1] == 2.0  # attempt 1

    def test_single_attempt_no_retry(self):
        with pytest.raises(ValueError):
            retry_with_backoff(
                lambda: (_ for _ in ()).throw(ValueError("once")),
                RetryPolicy(max_attempts=1),
                is_retryable=lambda _: True,
                operation_name="test",
                sleep_fn=lambda _: None,
            )
