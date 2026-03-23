"""Shared execution helpers used by both execution_handler and resume_handler.

Extracted to eliminate duplication of _execute_tool() and _save_with_event()
across the two handler modules.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from src.application.ports import ExecutionServicePort, InvocationUnitOfWork
from src.application.tool_helpers import (
    build_event_payload,
    check_tool_guardrails,
)
from src.domain.agent_invocation import AgentInvocation

logger = logging.getLogger(__name__)


def execute_tool(
    tool_call: dict,
    *,
    execution_service: ExecutionServicePort | None,
    sandbox_id: UUID | None,
    attempt_index: int = 0,
) -> dict:
    """Execute a single tool call via execution-service. Returns result dict.

    Shared by ExecuteInvocationHandler and ResumeInvocationHandler so that
    guardrail checks, error handling, and dispatch logic are consistent.
    """
    func = tool_call.get("function", {})
    tool_name = func.get("name", "unknown")
    try:
        tool_input = json.loads(func.get("arguments", "{}"))
    except (json.JSONDecodeError, TypeError):
        tool_input = {}

    # Guardrails
    rejection = check_tool_guardrails(tool_name, tool_input)
    if rejection:
        logger.warning("Tool '%s' rejected by guardrail: %s", tool_name, rejection)
        return {
            "status": "failed",
            "error_code": "GUARDRAIL_REJECTED",
            "error_message": rejection,
            "stdout": "",
            "stderr": "",
        }

    if not sandbox_id:
        logger.warning("No sandbox_id for tool call '%s' — returning error", tool_name)
        return {
            "status": "failed",
            "error_message": "No sandbox_id available",
            "stdout": "",
            "stderr": "",
        }

    if not execution_service:
        return {
            "status": "failed",
            "error_message": "No execution service",
            "stdout": "",
            "stderr": "",
        }

    try:
        result = execution_service.call_tool(
            sandbox_id=sandbox_id,
            tool_name=tool_name,
            tool_input=tool_input,
            attempt_index=attempt_index,
        )
        logger.info("Tool '%s' executed: status=%s", tool_name, result.get("status"))
        return result
    except Exception as exc:
        logger.error("Tool '%s' execution failed: %s", tool_name, exc)
        return {
            "status": "failed",
            "error_message": str(exc),
            "stdout": "",
            "stderr": "",
        }


def save_with_event(
    uow: InvocationUnitOfWork,
    invocation: AgentInvocation,
    event_type: str,
) -> None:
    """Save invocation state and write outbox event atomically."""
    uow.save_with_event(
        invocation=invocation,
        event_type=event_type,
        event_payload=build_event_payload(invocation),
    )
