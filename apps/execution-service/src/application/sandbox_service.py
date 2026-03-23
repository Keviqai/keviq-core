"""Sandbox application service — provision, terminate, query.

Orchestrates domain entity, repository, backend, and outbox.
Does not know about FastAPI or SQLAlchemy.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from src.domain.contracts import (
    SandboxProvisionRequest,
    SandboxProvisionResult,
    SandboxTerminationRequest,
    SandboxTerminationResult,
)
from src.domain.errors import DomainError, InvalidTransitionError
from src.domain.sandbox import Sandbox, SandboxType, TerminationReason

from .events import (
    sandbox_provision_failed_event,
    sandbox_provision_requested_event,
    sandbox_provisioned_event,
    sandbox_terminated_event,
    sandbox_termination_requested_event,
)
from .ports import SandboxBackend, UnitOfWork

logger = logging.getLogger(__name__)


def provision_sandbox(
    request: SandboxProvisionRequest,
    uow: UnitOfWork,
    backend: SandboxBackend,
) -> SandboxProvisionResult:
    """Provision a new sandbox.

    1. Create Sandbox domain entity (PROVISIONING)
    2. Persist + emit provision_requested event
    3. Call backend to create real sandbox instance
    4. On success: mark_ready, persist + emit provisioned event
    5. On failure: mark_failed, persist + emit provision_failed event
    """
    sandbox_id = uuid4()
    correlation_id = uuid4()

    sandbox = Sandbox(
        id=sandbox_id,
        workspace_id=request.workspace_id,
        task_id=request.task_id,
        run_id=request.run_id,
        step_id=request.step_id,
        agent_invocation_id=request.agent_invocation_id,
        sandbox_type=SandboxType(request.sandbox_type),
        policy_snapshot=request.policy_snapshot,
        resource_limits=request.resource_limits,
        network_egress_policy=request.network_egress_policy,
    )

    # Persist initial state + emit provision_requested
    with uow:
        uow.sandboxes.save(sandbox)
        uow.outbox.write(sandbox_provision_requested_event(
            sandbox_id=sandbox_id,
            workspace_id=request.workspace_id,
            correlation_id=correlation_id,
            sandbox_type=request.sandbox_type,
        ))
        uow.commit()

    logger.info(
        "Sandbox %s provisioning started (type=%s, invocation=%s)",
        sandbox_id, request.sandbox_type, request.agent_invocation_id,
    )

    # Call backend (side effect — outside transaction)
    try:
        backend_info = backend.provision(
            sandbox_id=sandbox_id,
            sandbox_type=request.sandbox_type,
            resource_limits=request.resource_limits or None,
            labels={
                "sandbox_id": str(sandbox_id),
                "workspace_id": str(request.workspace_id),
                "task_id": str(request.task_id),
                "run_id": str(request.run_id),
                "step_id": str(request.step_id),
                "agent_invocation_id": str(request.agent_invocation_id),
            },
        )
    except Exception as exc:
        logger.error("Sandbox %s provision failed: %s", sandbox_id, exc)
        error_detail: dict[str, Any] = {
            "code": "PROVISION_ERROR",
            "message": str(exc),
        }
        sandbox.mark_failed(error_detail)
        with uow:
            uow.sandboxes.save(sandbox)
            uow.outbox.write(sandbox_provision_failed_event(
                sandbox_id=sandbox_id,
                workspace_id=request.workspace_id,
                correlation_id=correlation_id,
                error_message=str(exc),
            ))
            uow.commit()

        return SandboxProvisionResult(
            sandbox_id=sandbox_id,
            status="failed",
            error_code="PROVISION_ERROR",
            error_message=str(exc),
        )

    # Success path — persist READY state; cleanup container on commit failure
    sandbox.mark_ready()
    try:
        with uow:
            uow.sandboxes.save(sandbox)
            uow.outbox.write(sandbox_provisioned_event(
                sandbox_id=sandbox_id,
                workspace_id=request.workspace_id,
                correlation_id=correlation_id,
            ))
            uow.commit()
    except Exception:
        logger.error(
            "Sandbox %s DB commit failed after backend provision — cleaning up container",
            sandbox_id,
        )
        try:
            backend.terminate(sandbox_id)
        except Exception:
            logger.error("Sandbox %s orphan container cleanup also failed", sandbox_id)
        raise

    logger.info(
        "Sandbox %s provisioned (container=%s)",
        sandbox_id, backend_info.container_id,
    )

    return SandboxProvisionResult(
        sandbox_id=sandbox_id,
        status="ready",
    )


def terminate_sandbox(
    request: SandboxTerminationRequest,
    uow: UnitOfWork,
    backend: SandboxBackend,
) -> SandboxTerminationResult:
    """Terminate a sandbox.

    1. Load sandbox from DB
    2. Transition to TERMINATING
    3. Call backend to stop/remove real sandbox instance
    4. Transition to TERMINATED
    5. Persist + emit events
    """
    correlation_id = uuid4()

    with uow:
        sandbox = uow.sandboxes.get_by_id(request.sandbox_id)
        if sandbox is None:
            raise DomainError(f"Sandbox {request.sandbox_id} not found")

        # Map string reason to enum
        try:
            reason = TerminationReason(request.reason)
        except ValueError:
            reason = TerminationReason.MANUAL

        sandbox.mark_terminating(reason)
        uow.sandboxes.save(sandbox)
        uow.outbox.write(sandbox_termination_requested_event(
            sandbox_id=request.sandbox_id,
            workspace_id=sandbox.workspace_id,
            correlation_id=correlation_id,
            reason=request.reason,
        ))
        uow.commit()

    logger.info("Sandbox %s terminating (reason=%s)", request.sandbox_id, request.reason)

    # Cleanup backend (side effect — outside transaction)
    try:
        backend.terminate(request.sandbox_id)
    except Exception as exc:
        logger.warning(
            "Sandbox %s backend cleanup failed (proceeding): %s",
            request.sandbox_id, exc,
        )

    # Mark terminated
    sandbox.mark_terminated()
    with uow:
        uow.sandboxes.save(sandbox)
        uow.outbox.write(sandbox_terminated_event(
            sandbox_id=request.sandbox_id,
            workspace_id=sandbox.workspace_id,
            correlation_id=correlation_id,
        ))
        uow.commit()

    logger.info("Sandbox %s terminated", request.sandbox_id)

    return SandboxTerminationResult(
        sandbox_id=request.sandbox_id,
        status="terminated",
    )


def get_sandbox(
    sandbox_id: UUID,
    uow: UnitOfWork,
) -> Sandbox:
    """Get a sandbox by ID. Raises DomainError if not found."""
    with uow:
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        if sandbox is None:
            raise DomainError(f"Sandbox {sandbox_id} not found")
        return sandbox


def list_active_sandboxes(
    uow: UnitOfWork,
    limit: int = 50,
) -> list[Sandbox]:
    """List active (non-terminal) sandboxes."""
    with uow:
        return uow.sandboxes.list_active(limit=limit)
