"""HTTP client for execution-service (sandbox + tool execution).

Implements ExecutionServicePort by calling execution-service's
internal API endpoints. Follows the same pattern as HttpRuntimeClient.

Retry policy: provision and terminate are retried on transient errors.
execute_tool is NOT retried here — the caller (execution_loop) decides
based on the ToolExecutionResult whether to retry the whole step.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from resilience import RetryPolicy, TimeoutBudget, retry_with_backoff
from resilience.retry import is_retryable_status_code
from src.application.ports import ExecutionServicePort, SandboxInfo, ToolExecutionResult
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_TIMEOUT_BUFFER_SECONDS = 10
_MIN_TIMEOUT_SECONDS = 30.0
_NIL_UUID = UUID(int=0)

_PROVISION_RETRY = RetryPolicy(max_attempts=3, base_delay_s=1.0, max_delay_s=8.0)
_TERMINATE_RETRY = RetryPolicy(max_attempts=2, base_delay_s=0.5, max_delay_s=3.0)


# ── Client exception hierarchy ────────────────────────────────


class ExecutionServiceError(RuntimeError):
    """Base class for execution-service client errors."""


class ExecutionServiceUnavailable(ExecutionServiceError):
    """Upstream service is unreachable or returned a network error."""


class ExecutionServiceProtocolError(ExecutionServiceError):
    """Upstream returned a non-JSON or malformed response."""


class ExecutionServiceRejected(ExecutionServiceError):
    """Upstream explicitly rejected the request (4xx/5xx with parseable body)."""


class HttpExecutionServiceClient(ExecutionServicePort):
    """HTTP client for execution-service."""

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

    def provision_sandbox(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        sandbox_type: str = "container",
    ) -> SandboxInfo:
        """Provision a sandbox via execution-service.

        Retries on transient network errors (timeout, connection, 429/5xx).
        """
        body: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "task_id": str(task_id),
            "run_id": str(run_id),
            "step_id": str(step_id),
            "agent_invocation_id": str(agent_invocation_id),
            "sandbox_type": sandbox_type,
        }

        def _attempt() -> SandboxInfo:
            try:
                resp = self._client.post(
                    "/internal/v1/sandboxes/provision",
                    json=body,
                    headers=get_auth_client().auth_headers("execution-service"),
                    timeout=_MIN_TIMEOUT_SECONDS,
                )
            except httpx.TimeoutException as exc:
                raise ExecutionServiceUnavailable(
                    f"Sandbox provision request timed out: {exc}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ExecutionServiceUnavailable(
                    f"Failed to provision sandbox: {exc}"
                ) from exc

            if resp.status_code not in (200, 202):
                if is_retryable_status_code(resp.status_code):
                    raise ExecutionServiceUnavailable(
                        f"Sandbox provision transient failure (HTTP {resp.status_code})"
                    )
                raise ExecutionServiceRejected(
                    f"Sandbox provision failed (HTTP {resp.status_code}): "
                    f"{resp.text[:500]}"
                )

            try:
                data = resp.json()
            except Exception as exc:
                raise ExecutionServiceProtocolError(
                    f"Sandbox provision returned non-JSON response: {resp.text[:200]}"
                ) from exc

            try:
                return SandboxInfo(
                    sandbox_id=UUID(data["sandbox_id"]),
                    sandbox_status=data.get("sandbox_status", "ready"),
                )
            except (KeyError, ValueError) as exc:
                raise ExecutionServiceProtocolError(
                    f"Sandbox provision response missing required fields: {exc}"
                ) from exc

        return retry_with_backoff(
            _attempt,
            _PROVISION_RETRY,
            is_retryable=lambda exc: isinstance(exc, ExecutionServiceUnavailable),
            operation_name="provision_sandbox",
        )

    def execute_tool(
        self,
        *,
        sandbox_id: UUID,
        tool_name: str,
        tool_input: dict[str, Any],
        attempt_index: int = 0,
        timeout_ms: int = 30_000,
        correlation_id: UUID | None = None,
    ) -> ToolExecutionResult:
        """Execute a registered tool inside a sandbox.

        No automatic retry — the caller decides based on the result.
        Timeout budget is propagated to the downstream service.
        """
        budget = TimeoutBudget(timeout_ms)
        downstream_ms = budget.remaining_for_downstream(overhead_ms=500)

        body: dict[str, Any] = {
            "sandbox_id": str(sandbox_id),
            "tool_name": tool_name,
            "tool_input": tool_input,
            "attempt_index": attempt_index,
            "timeout_ms": downstream_ms,
        }
        if correlation_id is not None:
            body["correlation_id"] = str(correlation_id)

        http_timeout = max(
            downstream_ms / 1000 + _TIMEOUT_BUFFER_SECONDS,
            _MIN_TIMEOUT_SECONDS,
        )

        try:
            resp = self._client.post(
                "/internal/v1/tool-executions",
                json=body,
                headers=get_auth_client().auth_headers("execution-service"),
                timeout=http_timeout,
            )
        except httpx.TimeoutException as exc:
            return ToolExecutionResult(
                execution_id=_NIL_UUID,
                sandbox_id=sandbox_id,
                status="timed_out",
                error_code="CLIENT_TIMEOUT",
                error_message=f"Execution request timed out: {exc}",
            )
        except httpx.HTTPError as exc:
            return ToolExecutionResult(
                execution_id=_NIL_UUID,
                sandbox_id=sandbox_id,
                status="failed",
                error_code="HTTP_ERROR",
                error_message=str(exc),
            )

        if resp.status_code not in (200, 202):
            return ToolExecutionResult(
                execution_id=_NIL_UUID,
                sandbox_id=sandbox_id,
                status="failed",
                error_code=f"HTTP_{resp.status_code}",
                error_message=resp.text[:500],
            )

        try:
            data = resp.json()
        except Exception:
            return ToolExecutionResult(
                execution_id=_NIL_UUID,
                sandbox_id=sandbox_id,
                status="failed",
                error_code="INVALID_RESPONSE",
                error_message=f"Non-JSON response: {resp.text[:200]}",
            )

        return ToolExecutionResult(
            execution_id=UUID(data["execution_id"]) if "execution_id" in data else _NIL_UUID,
            sandbox_id=UUID(data.get("sandbox_id", str(sandbox_id))),
            status=data.get("status", "failed"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code"),
            truncated=data.get("truncated", False),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
        )

    def get_execution(self, execution_id: UUID) -> dict[str, Any]:
        """Get execution attempt details."""
        try:
            resp = self._client.get(
                f"/internal/v1/tool-executions/{execution_id}",
                headers=get_auth_client().auth_headers("execution-service"),
                timeout=_MIN_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise ExecutionServiceUnavailable(
                f"Get execution request timed out: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ExecutionServiceUnavailable(
                f"Failed to get execution: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise ExecutionServiceRejected(
                f"Get execution failed (HTTP {resp.status_code}): "
                f"{resp.text[:500]}"
            )

        try:
            return resp.json()
        except Exception as exc:
            raise ExecutionServiceProtocolError(
                f"Get execution returned non-JSON response: {resp.text[:200]}"
            ) from exc

    def terminate_sandbox(
        self,
        sandbox_id: UUID,
        *,
        reason: str = "completed",
    ) -> bool:
        """Terminate a sandbox. Returns True on success, False on failure.

        Retries once on transient errors — sandbox cleanup is best-effort.
        """

        def _attempt() -> bool:
            try:
                resp = self._client.post(
                    f"/internal/v1/sandboxes/{sandbox_id}/terminate",
                    json={"reason": reason},
                    headers=get_auth_client().auth_headers("execution-service"),
                    timeout=_MIN_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError as exc:
                raise ExecutionServiceUnavailable(
                    f"Failed to terminate sandbox {sandbox_id}: {exc}"
                ) from exc

            if resp.status_code not in (200, 202):
                if is_retryable_status_code(resp.status_code):
                    raise ExecutionServiceUnavailable(
                        f"Sandbox termination transient failure (HTTP {resp.status_code})"
                    )
                logger.warning(
                    "Sandbox %s termination returned HTTP %d: %s",
                    sandbox_id, resp.status_code, resp.text[:200],
                )
                return False

            return True

        try:
            return retry_with_backoff(
                _attempt,
                _TERMINATE_RETRY,
                is_retryable=lambda exc: isinstance(exc, ExecutionServiceUnavailable),
                operation_name="terminate_sandbox",
            )
        except ExecutionServiceUnavailable as exc:
            logger.warning("Failed to terminate sandbox %s after retries: %s", sandbox_id, exc)
            return False
