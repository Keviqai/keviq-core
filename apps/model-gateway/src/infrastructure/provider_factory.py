"""Provider factory — creates provider adapters from config."""

from __future__ import annotations

from src.domain.ports import (
    ModelProviderPort,
    ProviderConfig,
    ProviderFactoryPort,
)

from .providers.openai_compatible import OpenAICompatibleProvider


class ProviderFactory(ProviderFactoryPort):
    """Creates provider adapter instances from config."""

    def create(self, config: ProviderConfig) -> ModelProviderPort:
        if config.provider_name == "claude_code_cli":
            from .providers.claude_bridge import ClaudeBridgeProvider
            return ClaudeBridgeProvider(
                endpoint_url=config.endpoint_url,
                provider_name=config.provider_name,
            )

        return OpenAICompatibleProvider(
            endpoint_url=config.endpoint_url,
            api_key=config.api_key,
            provider_name=config.provider_name,
        )
