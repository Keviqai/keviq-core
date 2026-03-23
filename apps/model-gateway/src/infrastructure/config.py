"""Provider config resolution from environment.

Provider configs are loaded from environment variables following a convention:
  MODEL_GW_PROVIDER_{NAME}_ENDPOINT  — base URL
  MODEL_GW_PROVIDER_{NAME}_API_KEY   — API key (from env, NOT from DB)
  MODEL_GW_PROVIDER_{NAME}_ENABLED   — "true"/"false" (default: true)

Model alias → provider mapping is configured via:
  MODEL_GW_ALIAS_{ALIAS}_PROVIDER    — provider name
  MODEL_GW_ALIAS_{ALIAS}_MODEL       — concrete model name at provider

Example:
  MODEL_GW_PROVIDER_OPENAI_ENDPOINT=https://api.openai.com/v1
  MODEL_GW_PROVIDER_OPENAI_API_KEY=sk-...
  MODEL_GW_ALIAS_CLAUDE_SONNET_PROVIDER=openai
  MODEL_GW_ALIAS_CLAUDE_SONNET_MODEL=gpt-4o

DB provider_configs table is reserved for Phase C when dynamic config is needed.
For now, env-based config is simpler and keeps secrets out of DB.
"""

from __future__ import annotations

import os
from typing import Any

from src.domain.errors import (
    ProviderConfigError,
    ProviderDisabledError,
    ProviderNotFoundError,
)
from src.domain.ports import ProviderConfig, ProviderConfigLoader


class EnvProviderConfigLoader(ProviderConfigLoader):
    """Load provider config from environment variables."""

    def get_provider_for_alias(self, model_alias: str) -> ProviderConfig | None:
        alias_key = model_alias.upper().replace("-", "_").replace(".", "_").replace(":", "_")

        provider_name = os.environ.get(f"MODEL_GW_ALIAS_{alias_key}_PROVIDER")
        if not provider_name:
            return None

        model_name = os.environ.get(f"MODEL_GW_ALIAS_{alias_key}_MODEL", model_alias)
        provider_key = provider_name.upper().replace("-", "_")

        endpoint_url = os.environ.get(f"MODEL_GW_PROVIDER_{provider_key}_ENDPOINT")
        if not endpoint_url:
            raise ProviderConfigError(provider_name, "endpoint_url not configured")

        api_key = os.environ.get(f"MODEL_GW_PROVIDER_{provider_key}_API_KEY", "")
        # claude_code_cli provider doesn't need an API key (uses host subscription)
        if not api_key and provider_name.lower() != "claude_code_cli":
            raise ProviderConfigError(provider_name, "api_key not configured")

        enabled = os.environ.get(f"MODEL_GW_PROVIDER_{provider_key}_ENABLED", "true")
        is_active = enabled.lower() in ("true", "1", "yes")

        return ProviderConfig(
            provider_name=provider_name.lower(),
            endpoint_url=endpoint_url,
            api_key=api_key,
            model_name=model_name,
            is_active=is_active,
        )
