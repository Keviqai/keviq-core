"""Orchestrator domain layer — pure domain models and state machines.

No infrastructure imports allowed (no SQLAlchemy, FastAPI, Redis, etc.).
"""

from .errors import (
    DomainError,
    DomainValidationError,
    ImmutableFieldError,
    InvalidTransitionError,
    TerminalStateError,
)
from .run import Run, RunStatus, TriggerType
from .step import Step, StepStatus, StepType
from .task import Task, TaskStatus, TaskType

__all__ = [
    # Errors
    "DomainError",
    "DomainValidationError",
    "ImmutableFieldError",
    "InvalidTransitionError",
    "TerminalStateError",
    # Task
    "Task",
    "TaskStatus",
    "TaskType",
    # Run
    "Run",
    "RunStatus",
    "TriggerType",
    # Step
    "Step",
    "StepStatus",
    "StepType",
]
