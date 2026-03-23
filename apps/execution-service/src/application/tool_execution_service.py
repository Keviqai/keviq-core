"""Tool execution application service — execute tools inside sandboxes.

Orchestrates tool registry validation, sandbox state transitions,
backend execution, result persistence, and outbox events.
Does not know about FastAPI, SQLAlchemy, or Docker.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.domain.contracts import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from src.domain.errors import DomainError, SandboxBusyError
from src.domain.sandbox import SandboxStatus

from .events import (
    tool_execution_failed_event,
    tool_execution_requested_event,
    tool_execution_succeeded_event,
)
from .ports import ToolExecutionBackend, UnitOfWork
from .tool_registry import build_command, get_tool

logger = logging.getLogger(__name__)

# Maximum output size before truncation (bytes).
_MAX_OUTPUT_SIZE = 1_000_000  # 1 MB


def execute_tool(
    request: ToolExecutionRequest,
    uow: UnitOfWork,
    execution_backend: ToolExecutionBackend,
) -> ToolExecutionResult:
    """Execute a registered tool inside an active sandbox.

    1. Validate tool name in registry
    2. Load sandbox, verify active
    3. Transition sandbox to EXECUTING, create attempt record
    4. Call backend to execute command in container
    5. Record result, transition sandbox to IDLE
    6. Emit outbox events
    """
    correlation_id = uuid4()
    execution_id = uuid4()
    now = datetime.now(timezone.utc)

    # 1. Validate tool in registry (raises ValueError if unknown)
    tool = get_tool(request.tool_name)

    # 2. Build safe command argv (raises ValueError on bad input)
    command = build_command(request.tool_name, request.tool_input)

    # Validate timeout_ms is positive
    if request.timeout_ms <= 0:
        raise ValueError(f"timeout_ms must be positive, got {request.timeout_ms}")

    # 3. Claim sandbox atomically, then validate type
    with uow:
        # Claim sandbox atomically — SELECT FOR UPDATE + transition to EXECUTING.
        # Raises SandboxBusyError if another caller already claimed it.
        # Raises DomainError if sandbox not found.
        sandbox = uow.sandboxes.claim_for_execution(request.sandbox_id)

        # Capture workspace_id early so we don't lose it between UoW blocks
        workspace_id = sandbox.workspace_id

        # Validate tool compatibility with sandbox type (after lock, no TOCTOU)
        if sandbox.sandbox_type.value not in tool.allowed_sandbox_types:
            # Roll back the claim — mark idle again
            sandbox.mark_idle()
            uow.sandboxes.save(sandbox)
            raise DomainError(
                f"Tool {request.tool_name!r} not allowed on "
                f"sandbox type {sandbox.sandbox_type.value!r}"
            )

        # Create attempt record (running)
        uow.attempts.save({
            "id": str(execution_id),
            "sandbox_id": str(request.sandbox_id),
            "attempt_index": request.attempt_index,
            "tool_name": request.tool_name,
            "tool_input": request.tool_input,
            "status": "running",
            "started_at": now,
        })

        uow.outbox.write(tool_execution_requested_event(
            sandbox_id=request.sandbox_id,
            workspace_id=sandbox.workspace_id,
            correlation_id=correlation_id,
            execution_id=execution_id,
            tool_name=request.tool_name,
            attempt_index=request.attempt_index,
        ))
        uow.commit()

    logger.info(
        "Tool execution %s started (sandbox=%s, tool=%s, attempt=%d)",
        execution_id, request.sandbox_id, request.tool_name, request.attempt_index,
    )

    # 4. Execute command in sandbox (side effect — outside transaction)
    timeout_s = max(request.timeout_ms // 1000, 1)
    import time as _time
    _exec_start = _time.monotonic()
    try:
        exec_result = execution_backend.exec_in_sandbox(
            sandbox_id=request.sandbox_id,
            command=command,
            timeout_s=timeout_s,
        )
    except TimeoutError:
        _fail_duration = int((_time.monotonic() - _exec_start) * 1000)
        return _record_failure(
            uow=uow,
            execution_id=execution_id,
            request=request,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            status=ToolExecutionStatus.TIMED_OUT,
            error_code="EXECUTION_TIMEOUT",
            error_message=f"Tool execution timed out after {timeout_s}s",
            duration_ms=_fail_duration,
        )
    except Exception as exc:
        _fail_duration = int((_time.monotonic() - _exec_start) * 1000)
        logger.error(
            "Tool execution %s backend error: %s", execution_id, exc,
        )
        return _record_failure(
            uow=uow,
            execution_id=execution_id,
            request=request,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            status=ToolExecutionStatus.FAILED,
            error_code="EXECUTION_ERROR",
            error_message=str(exc),
            duration_ms=_fail_duration,
        )

    # 5. Determine outcome
    stdout = exec_result.stdout
    stderr = exec_result.stderr
    truncated = False

    if len(stdout) > _MAX_OUTPUT_SIZE:
        stdout = stdout[:_MAX_OUTPUT_SIZE]
        truncated = True
    if len(stderr) > _MAX_OUTPUT_SIZE:
        stderr = stderr[:_MAX_OUTPUT_SIZE]
        truncated = True

    if exec_result.exit_code == 0:
        status = ToolExecutionStatus.COMPLETED
    else:
        status = ToolExecutionStatus.FAILED

    finished_at = datetime.now(timezone.utc)
    exec_duration_ms = int((_time.monotonic() - _exec_start) * 1000)
    stdout_size_bytes = len(exec_result.stdout.encode('utf-8')) if isinstance(exec_result.stdout, str) else len(exec_result.stdout)

    # 6. Record result + transition sandbox to IDLE
    with uow:
        sandbox_now = uow.sandboxes.get_by_id(request.sandbox_id)
        if sandbox_now is not None:
            sandbox_now.mark_idle()
            uow.sandboxes.save(sandbox_now)

        uow.attempts.save({
            "id": str(execution_id),
            "sandbox_id": str(request.sandbox_id),
            "attempt_index": request.attempt_index,
            "tool_name": request.tool_name,
            "tool_input": request.tool_input,
            "status": status.value,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exec_result.exit_code,
            "truncated": truncated,
            "completed_at": finished_at,
        })

        if status == ToolExecutionStatus.COMPLETED:
            uow.outbox.write(tool_execution_succeeded_event(
                sandbox_id=request.sandbox_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                execution_id=execution_id,
                tool_name=request.tool_name,
                attempt_index=request.attempt_index,
                exit_code=exec_result.exit_code,
                duration_ms=exec_duration_ms,
                truncated=truncated,
                stdout_size_bytes=stdout_size_bytes,
            ))
        else:
            uow.outbox.write(tool_execution_failed_event(
                sandbox_id=request.sandbox_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                execution_id=execution_id,
                tool_name=request.tool_name,
                attempt_index=request.attempt_index,
                error_code="NON_ZERO_EXIT",
                error_message=f"exit_code={exec_result.exit_code}",
                duration_ms=exec_duration_ms,
                exit_code=exec_result.exit_code,
            ))

        uow.commit()

    logger.info(
        "Tool execution %s finished (status=%s, exit_code=%s)",
        execution_id, status.value, exec_result.exit_code,
    )

    result = ToolExecutionResult(
        sandbox_id=request.sandbox_id,
        attempt_index=request.attempt_index,
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exec_result.exit_code,
        truncated=truncated,
    )
    return result


def get_execution(
    execution_id: UUID,
    uow: UnitOfWork,
) -> dict[str, Any]:
    """Get an execution attempt by ID. Raises DomainError if not found."""
    with uow:
        attempt = uow.attempts.get(execution_id)
        if attempt is None:
            raise DomainError(f"Execution {execution_id} not found")
        return attempt


def _record_failure(
    *,
    uow: UnitOfWork,
    execution_id: UUID,
    request: ToolExecutionRequest,
    workspace_id: UUID,
    correlation_id: UUID,
    status: ToolExecutionStatus,
    error_code: str,
    error_message: str,
    duration_ms: int | None = None,
) -> ToolExecutionResult:
    """Record a failed execution and transition sandbox back to IDLE."""
    finished_at = datetime.now(timezone.utc)

    with uow:
        sandbox = uow.sandboxes.get_by_id(request.sandbox_id)
        if sandbox is not None:
            sandbox.mark_idle()
            uow.sandboxes.save(sandbox)

        uow.attempts.save({
            "id": str(execution_id),
            "sandbox_id": str(request.sandbox_id),
            "attempt_index": request.attempt_index,
            "tool_name": request.tool_name,
            "tool_input": request.tool_input,
            "status": status.value,
            "error_detail": {"code": error_code, "message": error_message},
            "completed_at": finished_at,
        })

        uow.outbox.write(tool_execution_failed_event(
            sandbox_id=request.sandbox_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            execution_id=execution_id,
            tool_name=request.tool_name,
            attempt_index=request.attempt_index,
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        ))
        uow.commit()

    return ToolExecutionResult(
        sandbox_id=request.sandbox_id,
        attempt_index=request.attempt_index,
        status=status,
        error_code=error_code,
        error_message=error_message,
    )
