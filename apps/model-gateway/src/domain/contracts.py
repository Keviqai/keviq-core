"""Model gateway domain contracts — typed DTOs for model execution.

Transport-agnostic: no HTTP, FastAPI, SQLAlchemy imports allowed.
These define the internal contract for model-gateway service.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class ModelCallStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Model selection profile."""
    model_alias: str
    max_tokens: int | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class ExecuteModelRequest:
    """Request to execute a model call via model-gateway."""
    request_id: UUID
    agent_invocation_id: UUID
    workspace_id: UUID
    correlation_id: UUID
    model_profile: ModelProfile
    messages: list[dict[str, Any]]
    timeout_ms: int = 30_000
    tools: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage from a model call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ExecuteModelResult:
    """Successful model execution result."""
    request_id: UUID
    provider_name: str
    model_concrete: str
    output_text: str
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    total_cost_usd: Decimal = Decimal("0")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class ExecuteModelError:
    """Failed model execution result."""
    request_id: UUID
    error_code: str
    error_message: str
    provider_name: str = ""
    retryable: bool = False
    started_at: datetime | None = None
    failed_at: datetime | None = None
