"""Unit tests for recovery service — stuck sandbox sweep."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.application.events import OutboxEvent
from src.application.ports import (
    BackendInfo,
    ExecutionAttemptRepository,
    OutboxWriter,
    SandboxBackend,
    SandboxRepository,
    UnitOfWork,
)
from src.application.recovery_service import recover_stuck_sandboxes
from src.application.sandbox_service import provision_sandbox
from src.domain.contracts import SandboxProvisionRequest
from src.domain.errors import DomainError, SandboxBusyError
from src.domain.sandbox import Sandbox, SandboxStatus


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

    def list_stuck(self, *, stuck_before: datetime, statuses: list[str]) -> list[Sandbox]:
        return [
            s for s in self._store.values()
            if s.sandbox_status.value in statuses and s.updated_at < stuck_before
        ]


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


class FakeOutboxWriter(OutboxWriter):
    def __init__(self):
        self.events: list[OutboxEvent] = []

    def write(self, event: OutboxEvent) -> None:
        self.events.append(event)


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.sandboxes = FakeSandboxRepository()
        self.attempts = FakeExecutionAttemptRepository()
        self.outbox = FakeOutboxWriter()

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class FakeBackend(SandboxBackend):
    def __init__(self, *, should_fail_terminate: bool = False):
        self._should_fail_terminate = should_fail_terminate
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
        self.provisioned.append(sandbox_id)
        return BackendInfo(container_id="fake-container-id")

    def terminate(self, sandbox_id: uuid.UUID) -> None:
        if self._should_fail_terminate:
            raise RuntimeError("terminate failed")
        self.terminated.append(sandbox_id)

    def is_alive(self, sandbox_id: uuid.UUID) -> bool:
        return sandbox_id in self.provisioned and sandbox_id not in self.terminated


# ── Helpers ──────────────────────────────────────────────────


def _make_stuck_sandbox(
    uow: FakeUnitOfWork,
    backend: FakeBackend,
    status: SandboxStatus,
    stuck_minutes: int = 20,
) -> uuid.UUID:
    """Provision a sandbox and force it into a stuck state."""
    req = SandboxProvisionRequest(
        workspace_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        step_id=uuid.uuid4(),
        agent_invocation_id=uuid.uuid4(),
        sandbox_type="container",
    )
    result = provision_sandbox(req, uow, backend)
    sandbox = uow.sandboxes.get_by_id(result.sandbox_id)

    # Force into stuck state
    if status == SandboxStatus.PROVISIONING:
        sandbox.sandbox_status = SandboxStatus.PROVISIONING
    elif status == SandboxStatus.EXECUTING:
        sandbox.mark_executing()

    # Backdate updated_at to simulate being stuck
    sandbox.updated_at = datetime.now(timezone.utc) - timedelta(minutes=stuck_minutes)
    uow.sandboxes.save(sandbox)
    return result.sandbox_id


# ── Tests ────────────────────────────────────────────────────


class TestRecoverStuckSandboxes:
    def test_recovers_stuck_provisioning(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.PROVISIONING)

        results = recover_stuck_sandboxes(uow, backend)

        assert len(results) == 1
        assert results[0]["sandbox_id"] == str(sandbox_id)
        assert results[0]["previous_status"] == "provisioning"
        assert results[0]["recovery_action"] == "marked_failed"
        assert results[0]["success"] is True

        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.FAILED
        assert sandbox.error_detail["code"] == "RECOVERY_SWEEP"

    def test_recovers_stuck_executing(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING)

        results = recover_stuck_sandboxes(uow, backend)

        assert len(results) == 1
        assert results[0]["previous_status"] == "executing"
        assert results[0]["success"] is True

        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.FAILED

    def test_does_not_recover_recent_sandbox(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        # Only stuck for 5 minutes — below threshold
        _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING, stuck_minutes=5)

        results = recover_stuck_sandboxes(uow, backend)

        assert len(results) == 0

    def test_backend_cleanup_attempted(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING)

        recover_stuck_sandboxes(uow, backend)

        assert sandbox_id in backend.terminated

    def test_backend_cleanup_failure_still_reconciles_state(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend(should_fail_terminate=True)
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING)

        results = recover_stuck_sandboxes(uow, backend)

        # State should still be reconciled despite backend failure
        assert len(results) == 1
        assert results[0]["success"] is True

        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.FAILED
        assert sandbox.error_detail["backend_cleaned"] is False

    def test_emits_recovery_event(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        _make_stuck_sandbox(uow, backend, SandboxStatus.PROVISIONING)

        # Clear provision events
        uow.outbox.events.clear()

        recover_stuck_sandboxes(uow, backend)

        event_types = [e.event_type for e in uow.outbox.events]
        assert "sandbox.recovered" in event_types

    def test_no_stuck_sandboxes_returns_empty(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()

        results = recover_stuck_sandboxes(uow, backend)
        assert results == []

    def test_skips_sandbox_no_longer_stuck(self):
        """Sandbox moved to IDLE between list_stuck and _recover_single — must not mark FAILED.

        Simulates the TOCTOU race: list_stuck returns sandbox as EXECUTING,
        but by the time _recover_single_sandbox re-reads it, it has moved to IDLE.
        """
        from unittest.mock import patch
        from src.application.recovery_service import _recover_single_sandbox

        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING)

        # Move sandbox to IDLE (simulating normal completion during race window)
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        sandbox.mark_idle()
        uow.sandboxes.save(sandbox)

        # Call _recover_single_sandbox directly — this is what runs after list_stuck
        result = _recover_single_sandbox(
            sandbox_id, sandbox.workspace_id, SandboxStatus.EXECUTING, uow, backend,
        )

        assert result["recovery_action"] == "skipped_no_longer_stuck"
        assert result["success"] is True

        # Sandbox should still be IDLE, not FAILED
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        assert sandbox.sandbox_status == SandboxStatus.IDLE

    def test_skips_already_terminal(self):
        uow = FakeUnitOfWork()
        backend = FakeBackend()
        sandbox_id = _make_stuck_sandbox(uow, backend, SandboxStatus.EXECUTING)

        # Terminate sandbox before recovery runs
        sandbox = uow.sandboxes.get_by_id(sandbox_id)
        sandbox.mark_failed()
        sandbox.updated_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        uow.sandboxes.save(sandbox)

        results = recover_stuck_sandboxes(uow, backend)
        # Should not find it since it's no longer in EXECUTING status
        assert len(results) == 0
