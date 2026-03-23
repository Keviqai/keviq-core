"""Application-layer port interfaces (abstractions).

Infrastructure layer implements these. Application layer depends on these only.
No SQLAlchemy, no FastAPI imports allowed here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.approval_request import ApprovalRequest
    from src.domain.run import Run
    from src.domain.step import Step
    from src.domain.task import Task

    from .events import OutboxEvent


class TaskRepository(ABC):
    @abstractmethod
    def save(self, task: Task) -> None: ...

    @abstractmethod
    def get_by_id(self, task_id: UUID) -> Task | None: ...

    @abstractmethod
    def list_pending(self, limit: int = 10) -> list[Task]: ...

    @abstractmethod
    def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, offset: int = 0,
    ) -> list[Task]: ...

    @abstractmethod
    def list_running(self, limit: int = 50) -> list[Task]:
        """Find tasks in RUNNING status."""
        ...


class RunRepository(ABC):
    @abstractmethod
    def save(self, run: Run) -> None: ...

    @abstractmethod
    def get_by_id(self, run_id: UUID) -> Run | None: ...

    @abstractmethod
    def list_active_by_task(self, task_id: UUID) -> list[Run]: ...

    @abstractmethod
    def get_latest_by_task(self, task_id: UUID) -> Run | None: ...

    @abstractmethod
    def get_by_id_for_update(self, run_id: UUID) -> Run | None:
        """Load a run with SELECT ... FOR UPDATE row lock."""
        ...

    @abstractmethod
    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Run]:
        """Find runs stuck in given statuses since before the cutoff."""
        ...

    @abstractmethod
    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Run]:
        """Find stuck runs with FOR UPDATE SKIP LOCKED to avoid double-claim."""
        ...


class StepRepository(ABC):
    @abstractmethod
    def save(self, step: Step) -> None: ...

    @abstractmethod
    def get_by_id(self, step_id: UUID) -> Step | None: ...

    @abstractmethod
    def list_active_by_run(self, run_id: UUID) -> list[Step]: ...

    @abstractmethod
    def list_by_run(self, run_id: UUID) -> list[Step]: ...

    @abstractmethod
    def get_by_id_for_update(self, step_id: UUID) -> Step | None:
        """Load a step with SELECT ... FOR UPDATE row lock."""
        ...

    @abstractmethod
    def list_stuck(
        self, *, stuck_before: datetime, statuses: list[str],
    ) -> list[Step]:
        """Find steps stuck in given statuses since before the cutoff."""
        ...

    @abstractmethod
    def list_stuck_for_update(
        self, *, stuck_before: datetime, statuses: list[str], limit: int = 100,
    ) -> list[Step]:
        """Find stuck steps with FOR UPDATE SKIP LOCKED to avoid double-claim."""
        ...


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """Typed result from a single recovery action."""

    entity: str  # "run" | "step" | "task"
    id: str
    previous_status: str
    recovery_action: str
    success: bool
    error: str | None = None


class ApprovalRepository(ABC):
    @abstractmethod
    def save(self, approval: ApprovalRequest) -> None: ...
    @abstractmethod
    def get_by_id(self, approval_id: UUID) -> ApprovalRequest | None: ...
    @abstractmethod
    def get_by_id_for_update(self, approval_id: UUID) -> ApprovalRequest | None: ...
    @abstractmethod
    def list_by_workspace(
        self, workspace_id: UUID, *, decision: str | None = None,
        reviewer_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> list[ApprovalRequest]: ...
    @abstractmethod
    def count_pending_by_workspace(self, workspace_id: UUID) -> int: ...


class OutboxWriter(ABC):
    @abstractmethod
    def write(self, event: OutboxEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeExecutionResult:
    """Result from dispatching to agent-runtime.

    Orchestrator's own type — does not import from agent-runtime.
    """

    agent_invocation_id: UUID
    status: str  # "completed" | "failed" | "timed_out"
    output_text: str = ""
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def is_success(self) -> bool:
        return self.status == "completed"

    @property
    def is_timeout(self) -> bool:
        return self.status == "timed_out"


class ExecutionDispatchPort(ABC):
    """Port for dispatching execution requests to agent-runtime.

    Synchronous call: orchestrator sends request, waits for result.
    Result is mapped back to orchestrator domain lifecycle transitions.
    """

    @abstractmethod
    def dispatch(
        self,
        *,
        agent_invocation_id: UUID,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        correlation_id: UUID,
        agent_id: str,
        model_alias: str,
        instruction: str,
        input_payload: dict[str, Any] | None = None,
        timeout_ms: int = 30_000,
    ) -> RuntimeExecutionResult:
        """Dispatch execution to agent-runtime and wait for result."""
        ...


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Result from calling execution-service to run a tool.

    Orchestrator's own type — does not import from execution-service.
    """

    execution_id: UUID
    sandbox_id: UUID
    status: str  # "completed" | "failed" | "timed_out"
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    truncated: bool = False
    error_code: str | None = None
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "completed"

    @property
    def is_timeout(self) -> bool:
        return self.status == "timed_out"


@dataclass(frozen=True, slots=True)
class SandboxInfo:
    """Result from provisioning a sandbox."""

    sandbox_id: UUID
    sandbox_status: str


class ExecutionServicePort(ABC):
    """Port for calling execution-service (sandbox + tool execution).

    Orchestrator uses this to provision sandboxes, execute tools,
    and terminate sandboxes. Never calls Docker directly.
    """

    @abstractmethod
    def provision_sandbox(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        sandbox_type: str = "container",
    ) -> SandboxInfo:
        """Provision a sandbox via execution-service."""
        ...

    @abstractmethod
    def execute_tool(
        self,
        *,
        sandbox_id: UUID,
        tool_name: str,
        tool_input: dict[str, Any],
        attempt_index: int = 0,
        timeout_ms: int = 30_000,
        correlation_id: UUID | None = None,
    ) -> ToolExecutionResult:
        """Execute a registered tool inside a sandbox."""
        ...

    @abstractmethod
    def get_execution(self, execution_id: UUID) -> dict[str, Any]:
        """Get execution attempt details."""
        ...

    @abstractmethod
    def terminate_sandbox(
        self,
        sandbox_id: UUID,
        *,
        reason: str = "completed",
    ) -> bool:
        """Terminate a sandbox. Returns True on success, False on failure."""
        ...


# Re-export for backward compatibility
from src.application.template_ports import AgentTemplateRepository, TaskTemplateRepository  # noqa: E402,F401
from src.application.unit_of_work_port import UnitOfWork  # noqa: E402,F401
