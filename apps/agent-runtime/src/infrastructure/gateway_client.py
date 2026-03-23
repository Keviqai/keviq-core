"""Model gateway HTTP client.

Implements ModelGatewayPort by calling model-gateway's POST /v1/models/invoke.
Only this file uses httpx — domain/application layers stay transport-agnostic.

Retry policy: transient errors (timeout, connection, 429/5xx) are retried
with exponential backoff.  Permanent errors (4xx, protocol) fail immediately.
Timeout budget from caller is respected and propagated.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

import httpx

from resilience import RetryPolicy, TimeoutBudget, retry_with_backoff
from src.application.ports import ModelGatewayPort
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_GATEWAY_RETRY = RetryPolicy(max_attempts=3, base_delay_s=1.0, max_delay_s=8.0)

# Default timeout for model invocations (60s).
_DEFAULT_MODEL_TIMEOUT_MS = 60_000


class ModelGatewayError(Exception):
    """Error from model-gateway service call."""

    def __init__(self, error_code: str, message: str, retryable: bool = False):
        self.error_code = error_code
        self.retryable = retryable
        super().__init__(message)


class ModelGatewayClient(ModelGatewayPort):
    """HTTP client for model-gateway service."""

    def __init__(self, *, base_url: str):
        if not base_url.startswith(("https://", "http://")):
            raise ValueError(f"base_url must start with https:// or http://, got: {base_url!r}")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

    def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        self._client.close()

    def invoke_model(
        self,
        *,
        agent_invocation_id: UUID,
        model_alias: str,
        messages: list[dict],
        workspace_id: UUID,
        correlation_id: UUID,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict] | None = None,
        timeout_ms: int = _DEFAULT_MODEL_TIMEOUT_MS,
    ) -> dict:
        """Call model-gateway POST /v1/models/invoke.

        Retries on transient errors.  timeout_ms is used as the budget
        for this call (default 60s).
        """
        budget = TimeoutBudget(timeout_ms)

        body: dict[str, Any] = {
            "request_id": str(uuid4()),
            "agent_invocation_id": str(agent_invocation_id),
            "workspace_id": str(workspace_id),
            "correlation_id": str(correlation_id),
            "model_alias": model_alias,
            "messages": messages,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools

        def _attempt() -> dict:
            if budget.is_exhausted:
                raise ModelGatewayError(
                    "BUDGET_EXHAUSTED",
                    "Timeout budget exhausted before gateway attempt",
                    retryable=False,
                )

            http_timeout = max(budget.remaining_seconds(overhead_ms=500), 5.0)

            try:
                resp = self._client.post(
                    "/v1/models/invoke",
                    json=body,
                    headers=get_auth_client().auth_headers("model-gateway"),
                    timeout=http_timeout,
                )
            except httpx.TimeoutException as exc:
                raise ModelGatewayError("TIMEOUT", f"Gateway timed out: {exc}", retryable=True) from exc
            except httpx.ConnectError as exc:
                raise ModelGatewayError("CONNECTION_ERROR", f"Cannot reach gateway: {exc}", retryable=True) from exc
            except httpx.HTTPError as exc:
                raise ModelGatewayError("HTTP_ERROR", str(exc), retryable=False) from exc

            if resp.status_code != 200:
                detail: dict = {}
                if resp.headers.get("content-type", "").startswith("application/json"):
                    try:
                        detail = resp.json().get("detail", {})
                    except (ValueError, KeyError):
                        detail = {}
                error_code = detail.get("error_code", f"HTTP_{resp.status_code}") if isinstance(detail, dict) else f"HTTP_{resp.status_code}"
                error_message = detail.get("error_message", resp.text[:500]) if isinstance(detail, dict) else resp.text[:500]
                retryable = detail.get("retryable", resp.status_code in (429, 502, 503, 504)) if isinstance(detail, dict) else resp.status_code in (429, 502, 503, 504)
                raise ModelGatewayError(error_code, error_message, retryable=retryable)

            return resp.json()

        return retry_with_backoff(
            _attempt,
            _GATEWAY_RETRY,
            is_retryable=lambda exc: isinstance(exc, ModelGatewayError) and exc.retryable,
            operation_name="model_gateway_invoke",
        )
