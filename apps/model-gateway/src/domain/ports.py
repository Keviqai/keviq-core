"""Domain-layer port interfaces for model-gateway.

Infrastructure implements these. No SQLAlchemy, no FastAPI, no httpx here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from .contracts import (
        ExecuteModelRequest,
        ExecuteModelResult,
        ModelCallStatus,
        TokenUsage,
    )


class ModelProviderPort(ABC):
    """Port for calling an LLM provider (OpenAI, Anthropic, etc.).

    Each provider adapter implements this.
    """

    @abstractmethod
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
        """Execute a model call and return normalized response.

        Raises ProviderCallError on failure.
        """
        ...


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Normalized response from any LLM provider.

    This is what provider adapters return — no raw SDK types leak out.
    """
    output_text: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: str = ""
    tool_calls: list[dict[str, Any]] | None = None


class UsageRecordWriter(ABC):
    """Port for persisting model usage records."""

    @abstractmethod
    def write(
        self,
        *,
        agent_invocation_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
        model_alias: str,
        model_concrete: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost_usd: Decimal,
        latency_ms: int | None,
        status: str,
        error_code: str | None = None,
    ) -> None:
        """Write a usage record to persistence."""
        ...


class ProviderFactoryPort(ABC):
    """Port for creating provider adapter instances from config."""

    @abstractmethod
    def create(self, config: ProviderConfig) -> ModelProviderPort:
        """Create a provider adapter from resolved config."""
        ...


class ProviderConfigLoader(ABC):
    """Port for loading provider configuration."""

    @abstractmethod
    def get_provider_for_alias(self, model_alias: str) -> ProviderConfig | None:
        """Resolve a model alias to provider config. Returns None if not found."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Resolved provider configuration."""
    provider_name: str
    endpoint_url: str
    api_key: str
    model_name: str
    is_active: bool = True
    priority: int = 0
    extra_config: dict[str, Any] = field(default_factory=dict)
