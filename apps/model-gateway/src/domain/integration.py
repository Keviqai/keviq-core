"""Integration domain — constants and exceptions."""

from __future__ import annotations

VALID_INTEGRATION_TYPES = frozenset({'llm_provider'})

VALID_PROVIDER_KINDS = frozenset({'openai', 'anthropic', 'azure_openai', 'custom'})


class IntegrationError(Exception):
    """Base exception for integration domain."""


class IntegrationNotFound(IntegrationError):
    """Raised when an integration does not exist."""

    def __init__(self, integration_id: str) -> None:
        super().__init__(f'Integration not found: {integration_id}')
        self.integration_id = integration_id
