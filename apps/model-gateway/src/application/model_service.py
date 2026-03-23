"""Model execution application service.

Orchestrates: config resolution → provider call → usage recording.
This is the core use case of model-gateway.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

from src.domain.contracts import (
    ExecuteModelError,
    ExecuteModelRequest,
    ExecuteModelResult,
    ModelCallStatus,
    TokenUsage,
)
from src.domain.errors import (
    ModelGatewayError,
    ProviderCallError,
    ProviderConfigError,
    ProviderDisabledError,
    ProviderNotFoundError,
)
from src.domain.ports import (
    ModelProviderPort,
    ProviderConfig,
    ProviderConfigLoader,
    ProviderFactoryPort,
    UsageRecordWriter,
)


class ModelExecutionService:
    """Application service for executing model calls.

    Resolves provider config, calls provider, records usage.
    """

    def __init__(
        self,
        *,
        config_loader: ProviderConfigLoader,
        provider_factory: ProviderFactoryPort,
        usage_writer: UsageRecordWriter,
    ):
        self._config_loader = config_loader
        self._provider_factory = provider_factory
        self._usage_writer = usage_writer

    def execute(self, request: ExecuteModelRequest) -> ExecuteModelResult | ExecuteModelError:
        """Execute a model call. Returns result or error — never raises for provider failures."""
        started_at = datetime.now(timezone.utc)
        start_mono = time.monotonic()

        # 1. Resolve provider config (fail-fast)
        config = self._resolve_config(request.model_profile.model_alias, request.request_id)
        if isinstance(config, ExecuteModelError):
            return config

        # 2. Call provider
        provider = self._provider_factory.create(config)
        try:
            response = provider.call(
                model_name=config.model_name,
                messages=request.messages,
                max_tokens=request.model_profile.max_tokens,
                temperature=request.model_profile.temperature,
                timeout_ms=request.timeout_ms,
                tools=request.tools,
            )
        except ProviderCallError as exc:
            elapsed_ms = int((time.monotonic() - start_mono) * 1000)
            now = datetime.now(timezone.utc)

            # Record failed usage
            self._record_usage_safe(
                request=request,
                provider_name=config.provider_name,
                model_concrete=config.model_name,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=elapsed_ms,
                status=ModelCallStatus.TIMEOUT.value if exc.error_code == "TIMEOUT" else ModelCallStatus.ERROR.value,
                error_code=exc.error_code,
            )

            return ExecuteModelError(
                request_id=request.request_id,
                error_code=exc.error_code,
                error_message=str(exc),
                provider_name=config.provider_name,
                retryable=exc.retryable,
                started_at=started_at,
                failed_at=now,
            )

        # 3. Record successful usage
        completed_at = datetime.now(timezone.utc)
        elapsed_ms = int((time.monotonic() - start_mono) * 1000)

        self._record_usage_safe(
            request=request,
            provider_name=config.provider_name,
            model_concrete=response.model_name or config.model_name,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=elapsed_ms,
            status=ModelCallStatus.SUCCESS.value,
        )

        return ExecuteModelResult(
            request_id=request.request_id,
            provider_name=config.provider_name,
            model_concrete=response.model_name or config.model_name,
            output_text=response.output_text,
            finish_reason=response.finish_reason,
            usage=TokenUsage(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            ),
            started_at=started_at,
            completed_at=completed_at,
            tool_calls=response.tool_calls,
        )

    def _resolve_config(self, model_alias: str, request_id: UUID) -> ProviderConfig | ExecuteModelError:
        """Resolve provider config. Returns error DTO on failure (fail-fast)."""
        try:
            config = self._config_loader.get_provider_for_alias(model_alias)
        except ProviderConfigError as exc:
            return ExecuteModelError(
                request_id=request_id,
                error_code="CONFIG_ERROR",
                error_message=str(exc),
                provider_name=exc.provider_name,
            )

        if config is None:
            return ExecuteModelError(
                request_id=request_id,
                error_code="PROVIDER_NOT_FOUND",
                error_message=f"No provider configured for model alias {model_alias!r}",
            )

        if not config.is_active:
            return ExecuteModelError(
                request_id=request_id,
                error_code="PROVIDER_DISABLED",
                error_message=f"Provider {config.provider_name!r} is disabled",
                provider_name=config.provider_name,
            )

        return config

    def _record_usage_safe(
        self,
        *,
        request: ExecuteModelRequest,
        provider_name: str,
        model_concrete: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status: str,
        error_code: str | None = None,
    ) -> None:
        """Record usage, swallowing errors to not fail the main response."""
        try:
            self._usage_writer.write(
                agent_invocation_id=request.agent_invocation_id,
                workspace_id=request.workspace_id,
                correlation_id=request.correlation_id,
                model_alias=request.model_profile.model_alias,
                model_concrete=model_concrete,
                provider=provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost_usd=Decimal("0"),  # Cost calculation deferred to Phase C
                latency_ms=latency_ms,
                status=status,
                error_code=error_code,
            )
        except Exception:
            logger.exception("Usage recording failed — continuing without recording")




