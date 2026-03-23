"""Execution service HTTP client.

Implements ExecutionServicePort by calling execution-service's
POST /internal/v1/tool-executions endpoint.

Retry policy: transient errors (connection, timeout, 503) retried up to 2 times
with 1s backoff. Non-retryable errors (4xx, explicit failure) returned immediately.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

import httpx

from src.application.ports import ExecutionServicePort
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_TIMEOUT = 35.0  # slightly above the default 30s tool timeout
_MAX_RETRY_ATTEMPTS = 2
_RETRY_DELAY_S = 1.0
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class HttpExecutionServiceClient(ExecutionServicePort):
    """HTTP client for execution-service tool execution with retry."""

    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip('/')
        self._client = httpx.Client(timeout=_TIMEOUT)

    def call_tool(
        self,
        *,
        sandbox_id: UUID,
        tool_name: str,
        tool_input: dict,
        attempt_index: int = 0,
        timeout_ms: int = 30_000,
    ) -> dict:
        """Execute a tool in a sandbox via execution-service.

        Retries on transient errors (connection, timeout, 503).
        Returns the result dict with status, stdout, stderr, exit_code.
        """
        url = f"{self._base_url}/internal/v1/tool-executions"
        headers = get_auth_client().auth_headers("execution-service")

        payload = {
            "sandbox_id": str(sandbox_id),
            "attempt_index": attempt_index,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "timeout_ms": timeout_ms,
        }

        last_error: str = ""
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            try:
                resp = self._client.post(url, json=payload, headers=headers)

                if resp.status_code == 202:
                    return resp.json()

                # Retryable HTTP status → retry
                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRY_ATTEMPTS:
                    last_error = f"HTTP_{resp.status_code}: {resp.text[:200]}"
                    logger.warning(
                        "execution-service returned %d for tool '%s' (attempt %d/%d) — retrying",
                        resp.status_code, tool_name, attempt, _MAX_RETRY_ATTEMPTS,
                    )
                    time.sleep(_RETRY_DELAY_S)
                    continue

                # Non-retryable HTTP error or last attempt
                logger.warning(
                    "execution-service returned %d for tool '%s' in sandbox %s",
                    resp.status_code, tool_name, sandbox_id,
                )
                return {
                    "status": "failed",
                    "error_code": f"HTTP_{resp.status_code}",
                    "error_message": resp.text[:500],
                    "stdout": "",
                    "stderr": "",
                    "sandbox_id": str(sandbox_id),
                    "attempt_index": attempt_index,
                }

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = str(exc)
                if attempt < _MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        "execution-service transient error for tool '%s' (attempt %d/%d): %s — retrying",
                        tool_name, attempt, _MAX_RETRY_ATTEMPTS, exc,
                    )
                    time.sleep(_RETRY_DELAY_S)
                    continue
                # Last attempt — propagate as failed dict
                logger.error("execution-service failed after %d attempts for tool '%s': %s",
                             _MAX_RETRY_ATTEMPTS, tool_name, exc)
                return {
                    "status": "failed",
                    "error_code": "TRANSPORT_ERROR",
                    "error_message": f"execution-service unreachable after {_MAX_RETRY_ATTEMPTS} attempts: {exc}",
                    "stdout": "",
                    "stderr": "",
                    "sandbox_id": str(sandbox_id),
                    "attempt_index": attempt_index,
                }

        # Should not reach here, but safety fallback
        return {
            "status": "failed",
            "error_code": "RETRY_EXHAUSTED",
            "error_message": last_error,
            "stdout": "",
            "stderr": "",
        }
