"""Unit tests for Task domain model and state machine.

Validates all transitions from doc 05, section 1.
"""

import pytest
from uuid import uuid4

from src.domain.task import Task, TaskStatus, TaskType
from src.domain.errors import (
    DomainValidationError,
    InvalidTransitionError,
    TerminalStateError,
)


# ── Fixtures ────────────────────────────────────────────────────

def make_task(**overrides) -> Task:
    defaults = dict(
        workspace_id=uuid4(),
        title="Test task",
        task_type=TaskType.CODING,
        created_by_id=uuid4(),
    )
    defaults.update(overrides)
    return Task(**defaults)


def make_task_at(status: TaskStatus) -> Task:
    """Create a task reconstituted at a given status."""
    return make_task(task_status=status)


# ── Construction ────────────────────────────────────────────────

class TestTaskConstruction:
    def test_defaults(self):
        t = make_task()
        assert t.task_status == TaskStatus.DRAFT
        assert t.input_config == {}
        assert t.id is not None
        assert t.created_at is not None

    def test_blank_title_rejected(self):
        with pytest.raises(DomainValidationError, match="title"):
            make_task(title="")

    def test_whitespace_title_rejected(self):
        with pytest.raises(DomainValidationError, match="title"):
            make_task(title="   ")

    def test_reconstitution(self):
        tid = uuid4()
        t = make_task(id=tid, task_status=TaskStatus.RUNNING)
        assert t.id == tid
        assert t.task_status == TaskStatus.RUNNING


# ── Valid transitions (doc 05, section 1.3) ─────────────────────

class TestTaskValidTransitions:
    def test_draft_to_pending(self):
        t = make_task_at(TaskStatus.DRAFT)
        prev = t.submit()
        assert prev == TaskStatus.DRAFT
        assert t.task_status == TaskStatus.PENDING

    def test_draft_to_cancelled(self):
        t = make_task_at(TaskStatus.DRAFT)
        t.cancel()
        assert t.task_status == TaskStatus.CANCELLED

    def test_pending_to_running(self):
        t = make_task_at(TaskStatus.PENDING)
        t.start()
        assert t.task_status == TaskStatus.RUNNING

    def test_pending_to_cancelled(self):
        t = make_task_at(TaskStatus.PENDING)
        t.cancel()
        assert t.task_status == TaskStatus.CANCELLED

    def test_running_to_waiting_approval(self):
        t = make_task_at(TaskStatus.RUNNING)
        t.request_approval()
        assert t.task_status == TaskStatus.WAITING_APPROVAL

    def test_running_to_completed(self):
        t = make_task_at(TaskStatus.RUNNING)
        t.complete()
        assert t.task_status == TaskStatus.COMPLETED

    def test_running_to_failed(self):
        t = make_task_at(TaskStatus.RUNNING)
        t.fail()
        assert t.task_status == TaskStatus.FAILED

    def test_running_to_cancelled(self):
        t = make_task_at(TaskStatus.RUNNING)
        t.cancel()
        assert t.task_status == TaskStatus.CANCELLED

    def test_waiting_approval_to_running(self):
        t = make_task_at(TaskStatus.WAITING_APPROVAL)
        t.approve()
        assert t.task_status == TaskStatus.RUNNING

    def test_waiting_approval_to_cancelled(self):
        t = make_task_at(TaskStatus.WAITING_APPROVAL)
        t.cancel()
        assert t.task_status == TaskStatus.CANCELLED

    def test_completed_to_archived(self):
        t = make_task_at(TaskStatus.COMPLETED)
        t.archive()
        assert t.task_status == TaskStatus.ARCHIVED

    def test_failed_to_pending_retry(self):
        t = make_task_at(TaskStatus.FAILED)
        t.retry()
        assert t.task_status == TaskStatus.PENDING

    def test_failed_to_archived(self):
        t = make_task_at(TaskStatus.FAILED)
        t.archive()
        assert t.task_status == TaskStatus.ARCHIVED

    def test_cancelled_to_archived(self):
        t = make_task_at(TaskStatus.CANCELLED)
        t.archive()
        assert t.task_status == TaskStatus.ARCHIVED


# ── Invalid transitions ────────────────────────────────────────

class TestTaskInvalidTransitions:
    def test_draft_cannot_start(self):
        t = make_task_at(TaskStatus.DRAFT)
        with pytest.raises(InvalidTransitionError):
            t.start()

    def test_pending_cannot_complete(self):
        t = make_task_at(TaskStatus.PENDING)
        with pytest.raises(InvalidTransitionError):
            t.complete()

    def test_completed_cannot_fail(self):
        t = make_task_at(TaskStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            t.fail()

    def test_failed_cannot_resume_via_start(self):
        """Run failed has no resume path — only retry (creates new Run)."""
        t = make_task_at(TaskStatus.FAILED)
        with pytest.raises(InvalidTransitionError):
            t.start()

    def test_cancelled_cannot_retry(self):
        t = make_task_at(TaskStatus.CANCELLED)
        with pytest.raises(InvalidTransitionError):
            t.retry()


# ── Terminal state (archived) ───────────────────────────────────

class TestTaskTerminalState:
    def test_archived_raises_terminal_error(self):
        t = make_task_at(TaskStatus.ARCHIVED)
        with pytest.raises(TerminalStateError):
            t.submit()

    def test_archived_cannot_cancel(self):
        t = make_task_at(TaskStatus.ARCHIVED)
        with pytest.raises(TerminalStateError):
            t.cancel()

    def test_archived_is_terminal(self):
        t = make_task_at(TaskStatus.ARCHIVED)
        assert t.is_terminal is True

    def test_running_is_not_terminal(self):
        t = make_task_at(TaskStatus.RUNNING)
        assert t.is_terminal is False


# ── Side effects ────────────────────────────────────────────────

class TestTaskSideEffects:
    def test_transition_updates_updated_at(self):
        t = make_task_at(TaskStatus.DRAFT)
        old = t.updated_at
        t.submit()
        assert t.updated_at >= old

    def test_is_active(self):
        for status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL):
            t = make_task_at(status)
            assert t.is_active is True
        for status in (TaskStatus.DRAFT, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED):
            t = make_task_at(status)
            assert t.is_active is False


# ── Full lifecycle ──────────────────────────────────────────────

class TestTaskFullLifecycle:
    def test_happy_path(self):
        t = make_task()
        t.submit()
        t.start()
        t.complete()
        t.archive()
        assert t.task_status == TaskStatus.ARCHIVED

    def test_fail_and_retry(self):
        t = make_task()
        t.submit()
        t.start()
        t.fail()
        t.retry()  # failed → pending (new Run, no resume)
        t.start()
        t.complete()
        assert t.task_status == TaskStatus.COMPLETED

    def test_approval_flow(self):
        t = make_task()
        t.submit()
        t.start()
        t.request_approval()
        t.approve()
        t.complete()
        assert t.task_status == TaskStatus.COMPLETED

    def test_cancel_cascade(self):
        t = make_task()
        t.submit()
        t.start()
        t.cancel()
        t.archive()
        assert t.task_status == TaskStatus.ARCHIVED
