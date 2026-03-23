"""Unit tests for sandbox application service."""

from __future__ import annotations

import uuid
from typing import Any
import pytest

from src.application.events import OutboxEvent
from src.application.ports import (
    BackendInfo,
    ExecutionAttemptRepository,
    OutboxWriter,
    SandboxBackend,
    SandboxRepository,
    UnitOfWork,
)
from src.application.sandbox_service import (
    get_sandbox,
    provision_sandbox,
    terminate_sandbox,
)
from src.domain.contracts import SandboxProvisionRequest, SandboxTerminationRequest
from src.domain.errors import DomainError, InvalidTransitionError, SandboxBusyError
from src.domain.sandbox import Sandbox, SandboxStatus, SandboxType


# ── Fakes ────────────────────────────────────────────────────


class FakeSandboxRepository(SandboxRepository):
    def __init__(self):
        self._store: dict[str, Sandbox] = {}

    def save(self, sandbox: Sandbox) -> None:
        self._store[str(sandbox.id)] = sandbox

    def get_by_id(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        return self._store.get(str(sandbox_id))

    def get_by_invocation(self, agent_invocation_id: uuid.UUID) -> Sandbox | None:
        for s in self._store.values():
            if s.agent_invocation_id == agent_invocation_id:
                return s
        return None

    def list_active(self, limit: int = 50) -> list[Sandbox]:
        return [
            s for s in self._store.values()
            if s.sandbox_status not in (SandboxStatus.TERMINATED, SandboxStatus.FAILED)
        ][:limit]

    def get_by_id_for_update(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        return self.get_by_id(sandbox_id)

    def claim_for_execution(self, sandbox_id: uuid.UUID) -> Sandbox:
        sandbox = self.get_by_id(sandbox_id)
        if sandbox is None:
            raise DomainError(f"Sandbox {sandbox_id} not found")
        if sandbox.sandbox_status not in (SandboxStatus.READY, SandboxStatus.IDLE):
            raise SandboxBusyError(str(sandbox_id), sandbox.sandbox_status.value)
        sandbox.mark_executing()
        self.save(sandbox)
        return sandbox

    def list_stuck(self, *, stuck_before, statuses: list[str]) -> list[Sandbox]:
        return [
            s for s in self._store.values()
            if s.sandbox_status.value in statuses and s.updated_at < stuck_before
        ]


class FakeOutboxWriter(OutboxWriter):
    def __init__(self):
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FakeExecutionAttemptRepository(ExecutionAttemptRepository):
    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def save(self, attempt_data: dict[str, Any]) -> None:
        self._store[attempt_data["id"]] = attempt_data

    def get(self, attempt_id: uuid.UUID) -> dict[str, Any] | None:
        return self._store.get(str(attempt_id))

    def get_by_sandbox_and_index(
        self, sandbox_id: uuid.UUID, attempt_index: int,
    ) -> dict[str, Any] | None:
        for a in self._store.values():
            if str(a["sandbox_id"]) == str(sandbox_id) and a["attempt_index"] == attempt_index:
                return a
        return None


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.sandboxes = FakeSandboxRepository()
        self.attempts = FakeExecutionAttemptRepository()
        self.outbox = FakeOutboxWriter()
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeBackend(SandboxBackend):
    def __init__(self, *, should_fail: bool = False):
        self._should_fail = should_fail
        self.provisioned: list[uuid.UUID] = []
        self.terminated: list[uuid.UUID] = []

    def provision(
        self,
        *,
        sandbox_id: uuid.UUID,
        sandbox_type: str,
        resource_limits: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> BackendInfo:
        if self._should_fail:
            raise RuntimeError("Docker pull failed")
        self.provisioned.append(sandbox_id)
        return BackendInfo(container_id="fake-container-id")

    def terminate(self, sandbox_id: uuid.UUID) -> None:
        self.terminated.append(sandbox_id)

    def is_alive(self, sandbox_id: uuid.UUID) -> bool:
        return sandbox_id in self.provisioned and sandbox_id not in self.terminated


def _make_provision_request(**overrides) -> SandboxProvisionRequest:
    defaults = {
        "workspace_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "step_id": uuid.uuid4(),
        "agent_invocation_id": uuid.uuid4(),
        "sandbox_type": "container",
    }
    defaults.update(overrides)
    return SandboxProvisionRequest(**defaults)


# ── Provision Tests ──────────────────────────────────────────


class TestProvisionSandbox:
    def test_provision_success(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request()

        result = provision_sandbox(req, uow, backend)

        assert result.success
        assert result.status == "ready"
        assert result.sandbox_id is not None
        assert len(backend.provisioned) == 1

        # Sandbox persisted with READY status
        sandbox = uow.sandboxes.get_by_id(result.sandbox_id)
        assert sandbox is not None
        assert sandbox.sandbox_status == SandboxStatus.READY
        assert sandbox.started_at is not None

    def test_provision_failure(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend(should_fail=True)
        req = _make_provision_request()

        result = provision_sandbox(req, uow, backend)

        assert not result.success
        assert result.status == "failed"
        assert result.error_code == "PROVISION_ERROR"
        assert "Docker pull failed" in result.error_message

        # Sandbox persisted with FAILED status
        sandbox = uow.sandboxes.get_by_id(result.sandbox_id)
        assert sandbox is not None
        assert sandbox.sandbox_status == SandboxStatus.FAILED
        assert sandbox.error_detail is not None
        assert sandbox.error_detail["code"] == "PROVISION_ERROR"

    def test_provision_emits_events(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request()

        provision_sandbox(req, uow, backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.provision_requested" in event_types
        assert "sandbox.provisioned" in event_types

    def test_provision_failure_emits_failed_event(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend(should_fail=True)
        req = _make_provision_request()

        provision_sandbox(req, uow, backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.provision_requested" in event_types
        assert "sandbox.provision_failed" in event_types

    def test_provision_creates_correct_sandbox_type(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request(sandbox_type="subprocess")

        result = provision_sandbox(req, uow, backend)

        sandbox = uow.sandboxes.get_by_id(result.sandbox_id)
        assert sandbox.sandbox_type == SandboxType.SUBPROCESS

    def test_provision_preserves_identity_fields(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request()

        result = provision_sandbox(req, uow, backend)

        sandbox = uow.sandboxes.get_by_id(result.sandbox_id)
        assert sandbox.workspace_id == req.workspace_id
        assert sandbox.task_id == req.task_id
        assert sandbox.run_id == req.run_id
        assert sandbox.step_id == req.step_id
        assert sandbox.agent_invocation_id == req.agent_invocation_id


# ── Terminate Tests ──────────────────────────────────────────


class TestTerminateSandbox:
    def _provision_and_get_id(self, uow, backend):
        req = _make_provision_request()
        result = provision_sandbox(req, uow, backend)
        return result.sandbox_id

    def test_terminate_success(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = self._provision_and_get_id(uow, backend)

        req = SandboxTerminationRequest(sandbox_id=sandbox_id, reason="completed")
        result = terminate_sandbox(req, uow, backend)

        assert result.success
        assert result.status == "terminated"
        assert sandbox_id in backend.terminated

        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.TERMINATED
        assert sandbox.terminated_at is not None

    def test_terminate_emits_events(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = self._provision_and_get_id(uow, backend)

        # Clear provision events
        uow.outbox.events.clear()

        req = SandboxTerminationRequest(sandbox_id=sandbox_id, reason="manual")
        terminate_sandbox(req, uow, backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.termination_requested" in event_types
        assert "sandbox.terminated" in event_types

    def test_terminate_not_found(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()

        req = SandboxTerminationRequest(sandbox_id=uuid.uuid4())
        with pytest.raises(DomainError, match="not found"):
            terminate_sandbox(req, uow, backend)

    def test_terminate_invalid_transition(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = self._provision_and_get_id(uow, backend)

        # Terminate once
        req = SandboxTerminationRequest(sandbox_id=sandbox_id)
        terminate_sandbox(req, uow, backend)

        # Terminate again — should fail (already terminated)
        req2 = SandboxTerminationRequest(sandbox_id=sandbox_id)
        with pytest.raises((InvalidTransitionError, DomainError)):
            terminate_sandbox(req2, uow, backend)

    def test_terminate_with_timeout_reason(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = self._provision_and_get_id(uow, backend)

        req = SandboxTerminationRequest(sandbox_id=sandbox_id, reason="timeout")
        result = terminate_sandbox(req, uow, backend)

        assert result.success
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.termination_reason.value == "timeout"


# ── Get Sandbox Tests ────────────────────────────────────────


class TestGetSandbox:
    def test_get_existing(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request()
        result = provision_sandbox(req, uow, backend)

        sandbox = get_sandbox(result.sandbox_id, uow)
        assert sandbox.id == result.sandbox_id

    def test_get_not_found(self):
        uow = FakeUnitOfWork()
        with pytest.raises(DomainError, match="not found"):
            get_sandbox(uuid.uuid4(), uow)


# ── Profile Validation Tests ─────────────────────────────────


class TestProfileValidation:
    def test_invalid_sandbox_type_rejected(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        req = _make_provision_request(sandbox_type="invalid_type")

        with pytest.raises(ValueError):
            provision_sandbox(req, uow, backend)
