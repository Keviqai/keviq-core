"""Domain errors for model-gateway service."""

from __future__ import annotations


class ModelGatewayError(Exception):
    """Base error for model-gateway domain."""


class ProviderNotFoundError(ModelGatewayError):
    """No provider configured for the requested model alias."""

    def __init__(self, model_alias: str):
        self.model_alias = model_alias
        super().__init__(f"No provider found for model alias {model_alias!r}")


class ProviderDisabledError(ModelGatewayError):
    """Provider exists but is disabled."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"Provider {provider_name!r} is disabled")


class ProviderConfigError(ModelGatewayError):
    """Missing or invalid provider configuration."""

    def __init__(self, provider_name: str, detail: str):
        self.provider_name = provider_name
        self.detail = detail
        super().__init__(f"Provider {provider_name!r} config error: {detail}")


class ProviderCallError(ModelGatewayError):
    """Provider call failed."""

    def __init__(self, provider_name: str, error_code: str, message: str, retryable: bool = False):
        self.provider_name = provider_name
        self.error_code = error_code
        self.retryable = retryable
        super().__init__(f"Provider {provider_name!r} call failed: [{error_code}] {message}")
