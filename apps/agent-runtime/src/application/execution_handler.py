"""Execution handler — the real runtime loop for AgentInvocation.

Orchestrates: create/load invocation -> lifecycle transitions -> model call
-> tool loop -> persist result -> emit events.

This is the core use case of agent-runtime. The heavy lifting is delegated to:
- tool_loop.py: model-call -> tool-dispatch cycle
- gateway_errors.py: error mapping for model gateway failures
- artifact_integration.py: best-effort artifact creation
- shared_execution.py: shared execute_tool() and save_with_event()
"""

from __future__ import annotations

import logging
from uuid import UUID

from src.application.artifact_integration import create_artifact_best_effort
from src.application.ports import (
    ArtifactServicePort,
    ExecutionServicePort,
    InvocationUnitOfWork,
    ModelGatewayPort,
    ToolApprovalServicePort,
)
from src.application.shared_execution import save_with_event
from src.application.tool_helpers import (
    build_event_payload as _event_payload,
    build_invocation_summary,
)
from src.application.tool_loop import run_tool_loop
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation
from src.domain.execution_contracts import (
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    UsageMetadata,
)

logger = logging.getLogger(__name__)


class ExecuteInvocationHandler:
    """Application service for executing an agent invocation.

    Receives ExecutionRequest, runs lifecycle, calls model-gateway, persists result.
    """

    def __init__(
        self,
        *,
        unit_of_work: InvocationUnitOfWork,
        gateway: ModelGatewayPort,
        artifact_service: ArtifactServicePort | None = None,
        execution_service: ExecutionServicePort | None = None,
        tool_approval_service: ToolApprovalServicePort | None = None,
    ):
        self._uow = unit_of_work
        self._gateway = gateway
        self._artifact_service = artifact_service
        self._execution_service = execution_service
        self._tool_approval_service = tool_approval_service

    def execute(self, request: ExecutionRequest) -> ExecutionResult | ExecutionFailure:
        """Run a single invocation end-to-end.

        Returns ExecutionResult on success, ExecutionFailure on error.
        Never raises for expected failures — only for infrastructure bugs.
        """
        # 1. Create invocation entity from request
        invocation = self._create_invocation(request)

        # 2. Transition: initializing -> starting -> running
        try:
            invocation.mark_starting()
            invocation.mark_running(
                input_messages=[{"role": "user", "content": request.instruction}]
                if request.instruction else None
            )
        except Exception as exc:
            logger.exception("Failed to start invocation %s", invocation.id)
            invocation.mark_failed(error_detail={"error": str(exc)})
            save_with_event(self._uow, invocation, "agent_invocation.failed")
            return self._to_failure(invocation, "STARTUP_ERROR", str(exc))

        # Save running state + emit started event
        save_with_event(self._uow, invocation, "agent_invocation.started")
        runtime_metrics.inc_invocation("started")

        # 3. Tool loop: call model -> check for tool_calls -> dispatch -> repeat
        loop_result = run_tool_loop(
            invocation=invocation,
            request=request,
            uow=self._uow,
            gateway=self._gateway,
            execution_service=self._execution_service,
            tool_approval_service=self._tool_approval_service,
        )

        if loop_result.early_exit is not None:
            return loop_result.early_exit

        # 4. Mark completed with final result
        output_text = loop_result.output_text

        invocation.mark_completed(
            output_messages=[{"role": "assistant", "content": output_text}],
            tool_calls=loop_result.all_tool_calls or None,
            prompt_tokens=loop_result.total_prompt_tokens,
            completion_tokens=loop_result.total_completion_tokens,
        )

        # O6-S2: Emit completed event with invocation summary
        completed_payload = _event_payload(invocation)
        completed_payload["invocation_summary"] = build_invocation_summary(
            total_turns=loop_result.completed_turns,
            total_tools_called=loop_result.total_tools_called,
            total_tool_failures=loop_result.total_tool_failures,
            total_model_latency_ms=loop_result.total_model_latency_ms,
            total_tool_latency_ms=loop_result.total_tool_latency_ms,
        )
        self._uow.save_with_event(
            invocation=invocation,
            event_type="agent_invocation.completed",
            event_payload=completed_payload,
        )
        runtime_metrics.inc_invocation("completed")

        # 5. Best-effort artifact creation
        artifact_id = create_artifact_best_effort(
            artifact_service=self._artifact_service,
            request=request,
            output_text=output_text,
            gw_response=loop_result.last_gw_response,
        )

        return ExecutionResult(
            agent_invocation_id=invocation.id,
            status=ExecutionStatus.COMPLETED,
            output_payload={"output_text": output_text},
            usage=UsageMetadata(
                prompt_tokens=loop_result.total_prompt_tokens,
                completion_tokens=loop_result.total_completion_tokens,
                model_concrete=loop_result.last_gw_response.get("model_concrete"),
            ),
            started_at=invocation.started_at,
            completed_at=invocation.completed_at,
            artifact_id=artifact_id,
        )

    def _create_invocation(self, request: ExecutionRequest) -> AgentInvocation:
        """Create AgentInvocation from ExecutionRequest."""
        return AgentInvocation(
            id=request.agent_invocation_id,
            step_id=request.step_id,
            run_id=request.run_id,
            task_id=request.task_id,
            workspace_id=request.workspace_id,
            correlation_id=request.correlation_id,
            agent_id=request.agent_id,
            model_id=request.model_profile.model_alias,
        )

    def _to_failure(
        self,
        invocation: AgentInvocation,
        error_code: str,
        error_message: str,
    ) -> ExecutionFailure:
        return ExecutionFailure(
            agent_invocation_id=invocation.id,
            status=ExecutionStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            failed_at=invocation.completed_at,
        )


# ── Backward-compatible re-exports for test imports ──────────────
# Tests import these from execution_handler; keep them working.
from src.application.tool_helpers import (  # noqa: E402, F401
    MAX_TOOL_INPUT_BYTES,
    MAX_TOOL_RESULT_BYTES,
    MAX_TOOL_TURNS,
    INVOCATION_BUDGET_MS,
    check_tool_guardrails as _check_tool_guardrails,
    truncate_tool_result as _truncate_tool_result,
    validate_tool_calls as _validate_tool_calls,
)
