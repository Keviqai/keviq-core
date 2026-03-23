"""Integration tests for the model invoke end-to-end flow.

Uses fakes at the boundary (provider HTTP, DB) but exercises the full
config-resolution → provider-call → usage-recording path through real
application service code.
"""

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from src.application.model_service import ModelExecutionService, ProviderFactory
from src.domain.contracts import (
    ExecuteModelError,
    ExecuteModelRequest,
    ExecuteModelResult,
    ModelProfile,
)
from src.domain.errors import ProviderCallError
from src.domain.ports import (
    ModelProviderPort,
    ProviderConfig,
    ProviderResponse,
    UsageRecordWriter,
)
from src.infrastructure.config import EnvProviderConfigLoader


# ── Fakes ────────────────────────────────────────────────────────

class InMemoryUsageWriter(UsageRecordWriter):
    def __init__(self):
        self.records: list[dict] = []

    def write(self, **kwargs) -> None:
        self.records.append(kwargs)


class StubProvider(ModelProviderPort):
    """Stub provider that returns a canned response."""

    def __init__(self, response: ProviderResponse):
        self._response = response

    def call(self, *, model_name: str, messages: list[dict[str, Any]],
             max_tokens: int | None = None, temperature: float | None = None,
             timeout_ms: int = 30_000) -> ProviderResponse:
        return self._response


class StubProviderFactory(ProviderFactory):
    def __init__(self, provider: ModelProviderPort):
        self._provider = provider

    def create(self, config: ProviderConfig) -> ModelProviderPort:
        return self._provider


# ── Helpers ──────────────────────────────────────────────────────

def make_request(**overrides) -> ExecuteModelRequest:
    defaults = dict(
        request_id=uuid4(),
        agent_invocation_id=uuid4(),
        workspace_id=uuid4(),
        correlation_id=uuid4(),
        model_profile=ModelProfile(model_alias="test-model"),
        messages=[{"role": "user", "content": "hello"}],
    )
    defaults.update(overrides)
    return ExecuteModelRequest(**defaults)


def make_response(**overrides) -> ProviderResponse:
    defaults = dict(
        output_text="Test response",
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        model_name="gpt-4o-2024-05-13",
    )
    defaults.update(overrides)
    return ProviderResponse(**defaults)


# ── Integration: env config → service → usage ───────────────────

class TestEnvConfigToServiceFlow:
    """Test full flow from env-based config resolution through service execution."""

    def setup_method(self):
        """Set up env vars for a test provider."""
        os.environ["MODEL_GW_PROVIDER_TESTPROV_ENDPOINT"] = "https://api.test.com/v1"
        os.environ["MODEL_GW_PROVIDER_TESTPROV_API_KEY"] = "test-key-123"
        os.environ["MODEL_GW_ALIAS_TEST_MODEL_PROVIDER"] = "testprov"
        os.environ["MODEL_GW_ALIAS_TEST_MODEL_MODEL"] = "gpt-4o"

    def teardown_method(self):
        """Clean up env vars."""
        for key in [
            "MODEL_GW_PROVIDER_TESTPROV_ENDPOINT",
            "MODEL_GW_PROVIDER_TESTPROV_API_KEY",
            "MODEL_GW_ALIAS_TEST_MODEL_PROVIDER",
            "MODEL_GW_ALIAS_TEST_MODEL_MODEL",
            "MODEL_GW_PROVIDER_TESTPROV_ENABLED",
        ]:
            os.environ.pop(key, None)

    def test_env_config_resolves_and_executes(self):
        """Full path: env config → service → result with correct provider/model."""
        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelResult)
        assert result.provider_name == "testprov"
        assert result.model_concrete == "gpt-4o-2024-05-13"
        assert result.output_text == "Test response"

    def test_env_config_records_usage(self):
        """Usage record includes correct provider and model info from env config."""
        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request()
        svc.execute(req)

        assert len(writer.records) == 1
        rec = writer.records[0]
        assert rec["provider"] == "testprov"
        assert rec["model_alias"] == "test-model"
        assert rec["model_concrete"] == "gpt-4o-2024-05-13"
        assert rec["status"] == "success"
        assert rec["prompt_tokens"] == 10
        assert rec["completion_tokens"] == 5

    def test_env_config_unknown_alias_returns_error(self):
        """Requesting an alias not configured in env returns PROVIDER_NOT_FOUND."""
        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request(model_profile=ModelProfile(model_alias="nonexistent-model"))
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "PROVIDER_NOT_FOUND"

    def test_env_config_disabled_provider_returns_error(self):
        """Disabled provider returns PROVIDER_DISABLED."""
        os.environ["MODEL_GW_PROVIDER_TESTPROV_ENABLED"] = "false"

        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "PROVIDER_DISABLED"

    def test_env_config_missing_endpoint_returns_config_error(self):
        """Missing endpoint URL returns CONFIG_ERROR."""
        del os.environ["MODEL_GW_PROVIDER_TESTPROV_ENDPOINT"]

        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "CONFIG_ERROR"

    def test_env_config_missing_api_key_returns_config_error(self):
        """Missing API key returns CONFIG_ERROR."""
        del os.environ["MODEL_GW_PROVIDER_TESTPROV_API_KEY"]

        writer = InMemoryUsageWriter()
        provider = StubProvider(make_response())
        svc = ModelExecutionService(
            config_loader=EnvProviderConfigLoader(),
            provider_factory=StubProviderFactory(provider),
            usage_writer=writer,
        )

        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "CONFIG_ERROR"


# ── Integration: error path records usage ────────────────────────

class TestErrorPathUsageRecording:
    """Verify that failed provider calls still record usage."""

    def test_provider_failure_records_error_usage(self):
        """Provider error → usage record with error status."""
        writer = InMemoryUsageWriter()

        class FailingProvider(ModelProviderPort):
            def call(self, **kwargs) -> ProviderResponse:
                raise ProviderCallError("testprov", "HTTP_500", "server error", retryable=True)

        config = ProviderConfig(
            provider_name="testprov",
            endpoint_url="https://api.test.com/v1",
            api_key="test-key",
            model_name="gpt-4o",
        )

        from tests.unit.test_model_service import FakeProviderConfigLoader, FakeProviderFactory

        svc = ModelExecutionService(
            config_loader=FakeProviderConfigLoader({"test-model": config}),
            provider_factory=FakeProviderFactory(FailingProvider()),
            usage_writer=writer,
        )

        req = make_request()
        result = svc.execute(req)

        assert isinstance(result, ExecuteModelError)
        assert result.error_code == "HTTP_500"
        assert result.retryable is True

        # Usage was still recorded
        assert len(writer.records) == 1
        assert writer.records[0]["status"] == "error"
        assert writer.records[0]["error_code"] == "HTTP_500"

    def test_timeout_records_timeout_usage(self):
        """Provider timeout → usage record with timeout status."""
        writer = InMemoryUsageWriter()

        class TimeoutProvider(ModelProviderPort):
            def call(self, **kwargs) -> ProviderResponse:
                raise ProviderCallError("testprov", "TIMEOUT", "timed out", retryable=True)

        config = ProviderConfig(
            provider_name="testprov",
            endpoint_url="https://api.test.com/v1",
            api_key="test-key",
            model_name="gpt-4o",
        )

        from tests.unit.test_model_service import FakeProviderConfigLoader, FakeProviderFactory

        svc = ModelExecutionService(
            config_loader=FakeProviderConfigLoader({"test-model": config}),
            provider_factory=FakeProviderFactory(TimeoutProvider()),
            usage_writer=writer,
        )

        req = make_request()
        svc.execute(req)

        assert writer.records[0]["status"] == "timeout"
