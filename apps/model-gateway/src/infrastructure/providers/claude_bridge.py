"""Claude Code CLI bridge provider adapter.

LOCAL-ONLY: Routes model calls through the claude-bridge service, which
invokes the locally-installed Claude Code CLI.  No API keys are used —
the bridge relies on the host's Claude Code subscription login.

Config:
  MODEL_GW_PROVIDER_CLAUDE_CODE_CLI_ENDPOINT=http://claude-bridge:8000
  MODEL_GW_PROVIDER_CLAUDE_CODE_CLI_ENABLED=true
  (api_key is not required — set to "local" as a placeholder)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.domain.ports import ModelProviderPort, ProviderResponse

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class ClaudeBridgeProvider(ModelProviderPort):
    """Provider adapter that calls the claude-bridge service."""

    def __init__(self, endpoint_url: str, provider_name: str = "claude_code_cli"):
        self._endpoint = endpoint_url.rstrip("/")
        self._provider = provider_name

    def call(
        self,
        *,
        model_name: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_ms: int = 120_000,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        """Send prompt to claude-bridge and return normalized response."""
        # Flatten messages into a single prompt (Claude CLI is text-in/text-out)
        prompt = _messages_to_prompt(messages)

        # Map model_name to bridge alias (strip provider prefix if present)
        bridge_model = model_name
        for prefix in ("claude_code_cli:", "claude-code-cli:"):
            if bridge_model.startswith(prefix):
                bridge_model = bridge_model[len(prefix):]

        payload = {
            "prompt": prompt,
            "model": bridge_model,
            "max_turns": 1,
            "timeout_s": min(timeout_ms // 1000, 600),
        }

        try:
            resp = httpx.post(
                f"{self._endpoint}/internal/v1/query",
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise _bridge_error("Bridge request timed out")
        except httpx.HTTPStatusError as exc:
            raise _bridge_error(
                f"Bridge returned {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            )
        except httpx.ConnectError:
            raise _bridge_error(
                "Cannot connect to claude-bridge service. "
                "Is it running? (CLAUDE_BRIDGE_URL)"
            )

        if data.get("is_error"):
            raise _bridge_error(data.get("error_message", "Unknown bridge error"))

        return ProviderResponse(
            output_text=data.get("output_text", ""),
            finish_reason="stop",
            model_name=data.get("model_name", bridge_model),
        )


def _messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    """Flatten chat messages into a single text prompt for CLI mode."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle structured content blocks
            content = " ".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if role == "system":
            parts.append(f"[System instruction]: {content}")
        elif role == "assistant":
            parts.append(f"[Previous response]: {content}")
        else:
            parts.append(content)
    return "\n\n".join(parts)


class BridgeProviderError(Exception):
    """Raised when the claude-bridge call fails."""


def _bridge_error(msg: str) -> BridgeProviderError:
    logger.error("claude-bridge error: %s", msg)
    return BridgeProviderError(msg)
