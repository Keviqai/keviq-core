"""HTTP client for agent-runtime execution dispatch.

Implements ExecutionDispatchPort by calling agent-runtime's
POST /internal/v1/invocations/execute endpoint.

Retry policy: transient network errors (timeout, connection) and
retryable HTTP status codes (429, 502, 503, 504) are retried with
exponential backoff. Permanent errors fail immediately.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from resilience import RetryPolicy, TimeoutBudget, retry_with_backoff
from resilience.retry import is_retryable_status_code
from src.application.ports import ExecutionDispatchPort, RuntimeExecutionResult
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

# Buffer added to runtime timeout so the HTTP client doesn't cut off
# before the runtime has a chance to respond.
_TIMEOUT_BUFFER_SECONDS = 10
_MIN_TIMEOUT_SECONDS = 30.0

# Retry policy for dispatch calls.  dispatch() wraps its result in a
# RuntimeExecutionResult even on failure, so the retry only fires on
# transient *transport* errors that prevent us from getting any response.
_DISPATCH_RETRY = RetryPolicy(max_attempts=3, base_delay_s=0.5, max_delay_s=5.0)


class _TransientDispatchError(Exception):
    """Raised internally to signal a transient transport error worth retrying."""

    def __init__(self, result: RuntimeExecutionResult):
        self.result = result
        super().__init__(result.error_message)


class HttpRuntimeClient(ExecutionDispatchPort):
    """HTTP client for agent-runtime service."""

    def __init__(self, *, base_url: str):
        if not base_url.startswith(("https://", "http://")):
            raise ValueError(f"base_url must start with https:// or http://, got: {base_url!r}")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def dispatch(
        self,
        *,
        agent_invocation_id: UUID,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        correlation_id: UUID,
        agent_id: str,
        model_alias: str,
        instruction: str,
        input_payload: dict[str, Any] | None = None,
        timeout_ms: int = 30_000,
    ) -> RuntimeExecutionResult:
        """Dispatch execution to agent-runtime and wait for result.

        Transient transport errors (connection, timeout, 429/5xx) are retried
        with exponential backoff.  The timeout_ms budget is propagated to the
        downstream service and used for the HTTP-level timeout.
        """
        budget = TimeoutBudget(timeout_ms)
        body: dict[str, Any] = {
            "agent_invocation_id": str(agent_invocation_id),
            "workspace_id": str(workspace_id),
            "task_id": str(task_id),
            "run_id": str(run_id),
            "step_id": str(step_id),
            "correlation_id": str(correlation_id),
            "agent_id": agent_id,
            "model_alias": model_alias,
            "instruction": instruction,
            "input_payload": input_payload if input_payload is not None else {},
            "timeout_ms": timeout_ms,
        }
        # Promote sandbox_id to top-level field for agent-runtime tool loop
        sandbox_id = (input_payload or {}).get("sandbox_id")
        if sandbox_id:
            body["sandbox_id"] = sandbox_id

        def _attempt() -> RuntimeExecutionResult:
            if budget.is_exhausted:
                return RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="timed_out",
                    error_code="BUDGET_EXHAUSTED",
                    error_message="Timeout budget exhausted before dispatch attempt",
                )

            # Propagate remaining budget to downstream
            downstream_ms = budget.remaining_for_downstream(overhead_ms=500)
            body["timeout_ms"] = downstream_ms
            http_timeout = max(
                downstream_ms / 1000 + _TIMEOUT_BUFFER_SECONDS,
                _MIN_TIMEOUT_SECONDS,
            )

            try:
                resp = self._client.post(
                    "/internal/v1/invocations/execute",
                    json=body,
                    headers=get_auth_client().auth_headers("agent-runtime"),
                    timeout=http_timeout,
                )
            except httpx.TimeoutException as exc:
                raise _TransientDispatchError(RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="timed_out",
                    error_code="CLIENT_TIMEOUT",
                    error_message=f"Runtime request timed out: {exc}",
                )) from exc
            except httpx.ConnectError as exc:
                raise _TransientDispatchError(RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="failed",
                    error_code="CONNECTION_ERROR",
                    error_message=f"Cannot reach agent-runtime: {exc}",
                )) from exc
            except httpx.HTTPError as exc:
                return RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="failed",
                    error_code="HTTP_ERROR",
                    error_message=str(exc),
                )

            if resp.status_code != 200:
                result = RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="failed",
                    error_code=f"HTTP_{resp.status_code}",
                    error_message=resp.text[:500],
                )
                if is_retryable_status_code(resp.status_code):
                    raise _TransientDispatchError(result)
                return result

            try:
                data = resp.json()
            except Exception:
                return RuntimeExecutionResult(
                    agent_invocation_id=agent_invocation_id,
                    status="failed",
                    error_code="INVALID_RESPONSE",
                    error_message=f"Non-JSON response from agent-runtime: {resp.text[:200]}",
                )

            return RuntimeExecutionResult(
                agent_invocation_id=agent_invocation_id,
                status=data.get("status", "failed"),
                output_text=data.get("output_text", ""),
                error_code=data.get("error_code"),
                error_message=data.get("error_message"),
                retryable=data.get("retryable", False),
                prompt_tokens=data.get("prompt_tokens", 0),
                completion_tokens=data.get("completion_tokens", 0),
            )

        try:
            return retry_with_backoff(
                _attempt,
                _DISPATCH_RETRY,
                is_retryable=lambda exc: isinstance(exc, _TransientDispatchError),
                operation_name="runtime_dispatch",
            )
        except _TransientDispatchError as exc:
            # All retries exhausted — return the last error as a result
            logger.warning(
                "Runtime dispatch exhausted %d attempts for invocation %s",
                _DISPATCH_RETRY.max_attempts, agent_invocation_id,
            )
            return exc.result
