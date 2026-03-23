"""Unit tests for ModelExecutionService.

Tests config resolution, provider call, usage recording, and error handling
using in-memory fakes — no real HTTP or DB.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4, UUID

from src.application.model_service import ModelExecutionService, ProviderFactory
from src.domain.contracts import (
    ExecuteModelError,
    ExecuteModelRequest,
    ExecuteModelResult,
    ModelCallStatus,
    ModelProfile,
)
from src.domain.errors import ProviderCallError, ProviderConfigError
from src.domain.ports import (
    ModelProviderPort,
    ProviderConfig,
    ProviderConfigLoader,
    ProviderResponse,
    UsageRecordWriter,
)


# ── Fakes ────────────────────────────────────────────────────────

class FakeProviderConfigLoader(ProviderConfigLoader):
    def __init__(self, configs: dict[str, ProviderConfig | None] | None = None):
        self._configs = configs or {}

    def get_provider_for_alias(self, model_alias: str) -> ProviderConfig | None:
        return self._configs.get(model_alias)


class FakeProvider(ModelProviderPort):
    def __init__(self, response: ProviderResponse | None = None, error: ProviderCallError | None = None):
        self._response = response
        self._error = error
        self.calls: list[dict] = []

    def call(self, *, model_name: str, messages: list[dict[str, Any]],
             max_tokens: int | None = None, temperature: float | None = None,
             timeout_ms: int = 30_000) -> ProviderResponse:
        self.calls.append({
            "model_name": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        if self._error:
            raise self._error
        return self._response  # type: ignore[return-value]


class FakeProviderFactory(ProviderFactory):
    def __init__(self, provider: ModelProviderPort):
        self._provider = provider

    def create(self, config: ProviderConfig) -> ModelProviderPort:
        return self._provider


class FakeUsageWriter(UsageRecordWriter):
    def __init__(self):
        self.records: list[dict] = []

    def write(self, **kwargs) -> None:
        self.records.append(kwargs)


# ── Helpers ──────────────────────────────────────────────────────

def make_config(provider_name: str = "openai", is_active: bool = True) -> ProviderConfig:
    return ProviderConfig(
        provider_name=provider_name,
        endpoint_url="https://api.example.com/v1",
        api_key="test-key",
        model_name="gpt-4o",
        is_active=is_active,
    )


def make_request(**overrides) -> ExecuteModelRequest:
    defaults = dict(
        request_id=uuid4(),
        agent_invocation_id=uuid4(),
        workspace_id=uuid4(),
        correlation_id=uuid4(),
        model_profile=ModelProfile(model_alias="claude-sonnet"),
        messages=[{"role": "user", "content": "hello"}],
    )
    defaults.update(overrides)
    return ExecuteModelRequest(**defaults)


def make_provider_response(**overrides) -> ProviderResponse:
    defaults = dict(
        output_text="Hello, world!",
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        model_name="gpt-4o",
    )
    defaults.update(overrides)
    return ProviderResponse(**defaults)


def make_service(
    configs: dict[str, ProviderConfig | None] | None = None,
    provider: FakeProvider | None = None,
    usage_writer: FakeUsageWriter | None = None,
) -> tuple[ModelExecutionService, FakeProvider, FakeUsageWriter]:
    p = provider or FakeProvider(response=make_provider_response())
    w = usage_writer or FakeUsageWriter()
    svc = ModelExecutionService(
        config_loader=FakeProviderConfigLoader(configs or {"claude-sonnet": make_config()}),
        provider_factory=FakeProviderFactory(p),
        usage_writer=w,
    )
    return svc, p, w


# ── Happy path ───────────────────────────────────────────────────

class TestHappyPath:
    def test_execute_success(self):
        svc, provider, writer = make_service()
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.request_id == req.request_id
        assert result.output_text == "Hello, world!"
        assert result.provider_name == "openai"
        assert result.model_concrete == "gpt-4o"
        assert result.usage.prompt_tokens == 10
        assert result.usage.completion_tokens == 5

    def test_provider_called_with_correct_params(self):
        svc, provider, _ = make_service()
        req = make_request(
            model_profile=ModelProfile(model_alias="claude-sonnet", max_tokens=100, temperature=0.5),
        )
        svc.execute(req)

        assert len(provider.calls) == 1
        call = provider.calls[0]
        assert call["model_name"] == "gpt-4o"
        assert call["max_tokens"] == 100
        assert call["temperature"] == 0.5

    def test_usage_recorded_on_success(self):
        svc, _, writer = make_service()
        req = make_request()
        svc.execute(req)

        assert len(writer.records) == 1
        rec = writer.records[0]
        assert rec["status"] == "success"
        assert rec["prompt_tokens"] == 10
        assert rec["completion_tokens"] == 5
        assert rec["model_alias"] == "claude-sonnet"
        assert rec["provider"] == "openai"

    def test_timestamps_set(self):
        svc, _, _ = make_service()
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at


# ── Config resolution failures (fail-fast) ───────────────────────

class TestConfigFailFast:
    def test_unknown_model_alias(self):
        svc, _, _ = make_service(configs={})
        req = make_request(model_profile=ModelProfile(model_alias="nonexistent"))
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "PROVIDER_NOT_FOUND"

    def test_disabled_provider(self):
        svc, _, _ = make_service(configs={
            "claude-sonnet": make_config(is_active=False),
        })
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "PROVIDER_DISABLED"

    def test_config_error_missing_endpoint(self):
        loader = FakeProviderConfigLoader()
        loader.get_provider_for_alias = lambda alias: (_ for _ in ()).throw(
            ProviderConfigError("openai", "endpoint_url not configured")
        )
        svc = ModelExecutionService(
            config_loader=loader,
            provider_factory=FakeProviderFactory(FakeProvider(response=make_provider_response())),
            usage_writer=FakeUsageWriter(),
        )
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "CONFIG_ERROR"


# ── Provider call failures ───────────────────────────────────────

class TestProviderFailures:
    def test_timeout_error(self):
        provider = FakeProvider(error=ProviderCallError("openai", "TIMEOUT", "timed out", retryable=True))
        svc, _, writer = make_service(provider=provider)
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "TIMEOUT"
        assert result.retryable is True
        assert result.provider_name == "openai"
        assert result.started_at is not None
        assert result.failed_at is not None

    def test_connection_error(self):
        provider = FakeProvider(error=ProviderCallError("openai", "CONNECTION_ERROR", "refused", retryable=True))
        svc, _, _ = make_service(provider=provider)
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "CONNECTION_ERROR"

    def test_http_error(self):
        provider = FakeProvider(error=ProviderCallError("openai", "HTTP_500", "server error", retryable=True))
        svc, _, _ = make_service(provider=provider)
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "HTTP_500"

    def test_usage_recorded_on_failure(self):
        provider = FakeProvider(error=ProviderCallError("openai", "HTTP_429", "rate limited", retryable=True))
        svc, _, writer = make_service(provider=provider)
        req = make_request()
        svc.execute(req)

        assert len(writer.records) == 1
        rec = writer.records[0]
        assert rec["status"] == "error"
        assert rec["error_code"] == "HTTP_429"

    def test_timeout_usage_status_is_timeout(self):
        provider = FakeProvider(error=ProviderCallError("openai", "TIMEOUT", "timed out"))
        svc, _, writer = make_service(provider=provider)
        req = make_request()
        svc.execute(req)

        assert writer.records[0]["status"] == "timeout"


# ── Usage recording resilience ───────────────────────────────────

class TestUsageResilience:
    def test_usage_write_failure_does_not_break_success(self):
        """If usage recording fails, the model result should still return."""

        class FailingWriter(UsageRecordWriter):
            def write(self, **kwargs) -> None:
                raise RuntimeError("DB down")

        svc = ModelExecutionService(
            config_loader=FakeProviderConfigLoader({"claude-sonnet": make_config()}),
            provider_factory=FakeProviderFactory(FakeProvider(response=make_provider_response())),
            usage_writer=FailingWriter(),
        )
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.output_text == "Hello, world!"


# ── Provider response normalization ──────────────────────────────

class TestResponseNormalization:
    def test_model_concrete_from_response(self):
        """model_concrete comes from provider response, not config."""
        provider = FakeProvider(response=make_provider_response(model_name="gpt-4o-2024-05-13"))
        svc, _, _ = make_service(provider=provider)
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.model_concrete == "gpt-4o-2024-05-13"

    def test_model_concrete_fallback_to_config(self):
        """If provider doesn't return model name, fall back to config."""
        provider = FakeProvider(response=make_provider_response(model_name=""))
        svc, _, _ = make_service(provider=provider)
        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.model_concrete == "gpt-4o"  # From config
