"""Execution contracts — typed DTOs for Orchestrator ↔ Agent Runtime boundary.

Transport-agnostic: no HTTP, FastAPI, SQLAlchemy, or httpx imports allowed.
These are value objects that define the interface contract between services.

Orchestrator creates ExecutionRequest → Agent Runtime returns ExecutionResult or ExecutionFailure.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class ExecutionStatus(str, enum.Enum):
    """Terminal status of an execution."""
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    WAITING_HUMAN = "waiting_human"


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Model selection profile — tells runtime which model to request via model-gateway."""
    model_alias: str
    max_tokens: int | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class UsageMetadata:
    """Token and cost usage from an execution."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: Decimal = Decimal("0")
    model_concrete: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Request from Orchestrator to Agent Runtime to execute an agent invocation.

    Orchestrator assigns the agent_invocation_id.
    Agent Runtime owns the lifecycle from this point forward.
    """
    agent_invocation_id: UUID
    workspace_id: UUID
    task_id: UUID
    run_id: UUID
    step_id: UUID
    correlation_id: UUID
    agent_id: str
    model_profile: ModelProfile
    instruction: str
    input_payload: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30_000
    causation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Successful execution result from Agent Runtime back to Orchestrator."""
    agent_invocation_id: UUID
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    output_payload: dict[str, Any] = field(default_factory=dict)
    usage: UsageMetadata = field(default_factory=UsageMetadata)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifact_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    """Failed execution result from Agent Runtime back to Orchestrator."""
    agent_invocation_id: UUID
    status: ExecutionStatus = ExecutionStatus.FAILED
    error_code: str = "UNKNOWN"
    error_message: str = ""
    retryable: bool = False
    failed_at: datetime | None = None
    usage: UsageMetadata | None = None
