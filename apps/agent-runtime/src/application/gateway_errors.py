"""Gateway error handling — maps model-gateway exceptions to invocation failures.

Extracted from execution_handler.py to keep file sizes under 300 lines.
"""

from __future__ import annotations

import logging

from src.application.ports import InvocationUnitOfWork
from src.application.shared_execution import save_with_event
from src.application.runtime_metrics import runtime_metrics
from src.domain.agent_invocation import AgentInvocation
from src.domain.execution_contracts import (
    ExecutionFailure,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)


def handle_gateway_error(
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    exc: Exception,
) -> ExecutionFailure:
    """Map gateway error to invocation failure with user-friendly messages."""
    error_code = "GATEWAY_ERROR"
    error_message = str(exc)
    retryable = False

    # Duck-type check for ModelGatewayError attributes
    if hasattr(exc, "error_code"):
        error_code = exc.error_code
    if hasattr(exc, "retryable"):
        retryable = exc.retryable

    error_message = _friendly_error_message(error_code, error_message)

    # Map to domain state
    if error_code == "TIMEOUT":
        invocation.mark_timed_out(error_detail={
            "error_code": error_code,
            "error_message": error_message,
        })
        event_type = "agent_invocation.timed_out"
        status = ExecutionStatus.TIMED_OUT
    else:
        invocation.mark_failed(error_detail={
            "error_code": error_code,
            "error_message": error_message,
        })
        event_type = "agent_invocation.failed"
        status = ExecutionStatus.FAILED

    save_with_event(uow, invocation, event_type)
    runtime_metrics.inc_invocation(
        "timed_out" if status == ExecutionStatus.TIMED_OUT else "failed",
    )

    return ExecutionFailure(
        agent_invocation_id=invocation.id,
        status=status,
        error_code=error_code,
        error_message=error_message,
        retryable=retryable,
        failed_at=invocation.completed_at,
    )


def _friendly_error_message(error_code: str, raw_message: str) -> str:
    """Produce user-friendly error message for common gateway failures."""
    raw = raw_message.lower()
    code = error_code.upper() if error_code else ""

    if code == "PROVIDER_NOT_FOUND" or "no provider configured" in raw:
        return (
            "No AI model provider is configured for this task. "
            "Please check your model provider settings and ensure "
            "the Claude Bridge or another provider is set up correctly."
        )
    if code == "MODEL_NOT_FOUND" or "model not found" in raw:
        return (
            "The requested AI model could not be found. "
            "Please verify the model configuration in your environment."
        )
    if "connection" in raw or "connect" in raw or "unreachable" in raw:
        return (
            "Could not reach the AI model provider. "
            "The model service may be offline or misconfigured. "
            "Please check that the model provider is running and try again."
        )
    if "timed out" in raw or "timeout" in raw:
        return (
            "The AI model took too long to respond. "
            "This may be a temporary issue — try again or use a simpler prompt."
        )
    if "422" in raw or "unprocessable" in raw:
        return (
            "The model configuration could not be processed. "
            "The model alias may be misconfigured. "
            "Please check DEFAULT_MODEL_ALIAS in the environment."
        )
    if "bridge" in raw and ("cannot connect" in raw or "not running" in raw):
        return (
            "The Claude Bridge service is not reachable. "
            "Please ensure the bridge is running and accessible."
        )
    if code.startswith("HTTP_") and code != "HTTP_ERROR":
        status_num = code.replace("HTTP_", "")
        return (
            f"The model provider returned an error (HTTP {status_num}). "
            "This may be a temporary issue. Please try again."
        )

    return raw_message
