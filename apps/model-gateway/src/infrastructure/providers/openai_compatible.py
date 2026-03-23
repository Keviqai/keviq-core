"""OpenAI-compatible provider adapter.

Calls any OpenAI API-compatible endpoint (OpenAI, Azure OpenAI, vLLM, Ollama, etc.).
Uses httpx for HTTP calls — no openai SDK dependency.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.domain.errors import ProviderCallError
from src.domain.ports import ModelProviderPort, ProviderResponse


class OpenAICompatibleProvider(ModelProviderPort):
    """Provider adapter for OpenAI-compatible chat/completions API."""

    def __init__(self, *, endpoint_url: str, api_key: str, provider_name: str = "openai"):
        # Phase A: endpoint_url comes from env vars only (operator-set).
        # Phase C (dynamic config from DB): add URL scheme/host validation here.
        if not endpoint_url.startswith(("https://", "http://")):
            raise ValueError(f"endpoint_url must start with https:// or http://, got: {endpoint_url!r}")
        self._endpoint_url = endpoint_url.rstrip("/")
        self._api_key = api_key
        self._provider_name = provider_name
        self._client = httpx.Client(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    def call(
        self,
        *,
        model_name: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_ms: int = 30_000,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        url = f"{self._endpoint_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools

        timeout_s = timeout_ms / 1000.0

        try:
            resp = self._client.post(url, json=body, headers=headers, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                self._provider_name, "TIMEOUT",
                f"Request timed out after {timeout_ms}ms",
                retryable=True,
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderCallError(
                self._provider_name, "CONNECTION_ERROR",
                f"Failed to connect to {self._endpoint_url}",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderCallError(
                self._provider_name, "HTTP_ERROR",
                str(exc),
                retryable=False,
            ) from exc

        if resp.status_code != 200:
            error_body = resp.text[:500]
            retryable = resp.status_code in (429, 500, 502, 503, 504)
            raise ProviderCallError(
                self._provider_name,
                f"HTTP_{resp.status_code}",
                error_body,
                retryable=retryable,
            )

        data = resp.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> ProviderResponse:
        """Parse OpenAI chat/completions response into normalized ProviderResponse."""
        try:
            choice = data["choices"][0]
            message = choice.get("message", {})
            usage = data.get("usage", {})
            finish_reason = choice.get("finish_reason", "stop")

            # Extract tool_calls if present (OpenAI function calling)
            raw_tool_calls = message.get("tool_calls")
            tool_calls = None
            if raw_tool_calls:
                tool_calls = [
                    {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        },
                    }
                    for tc in raw_tool_calls
                ]

            return ProviderResponse(
                output_text=message.get("content") or "",
                finish_reason=finish_reason,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                model_name=data.get("model", ""),
                tool_calls=tool_calls,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderCallError(
                self._provider_name,
                "PARSE_ERROR",
                f"Failed to parse provider response: {exc}",
                retryable=False,
            ) from exc
