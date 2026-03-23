"""Unit tests for event-store query handlers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from src.application.queries import (
    get_run_events_after,
    get_run_timeline,
    get_task_timeline,
    get_workspace_events,
)
from src.domain.event import StoredEvent


def _make_event(**overrides) -> StoredEvent:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        event_type='task.created',
        schema_version='1.0',
        workspace_id=uuid4(),
        task_id=uuid4(),
        run_id=None,
        step_id=None,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=now,
        emitted_by={'service': 'orchestrator', 'instance_id': 'test'},
        actor={'type': 'user', 'id': 'u-1'},
        payload={},
        received_at=now,
    )
    defaults.update(overrides)
    return StoredEvent(**defaults)


class TestGetTaskTimeline:
    def test_delegates_to_repo(self):
        repo = MagicMock()
        events = [_make_event(), _make_event()]
        repo.list_by_task.return_value = events
        tid = uuid4()

        result = get_task_timeline(tid, repo)

        repo.list_by_task.assert_called_once_with(tid, after=None, limit=100)
        assert result == events

    def test_caps_limit_at_500(self):
        repo = MagicMock()
        repo.list_by_task.return_value = []

        get_task_timeline(uuid4(), repo, limit=999)

        _, kwargs = repo.list_by_task.call_args
        assert kwargs['limit'] == 500

    def test_passes_after_param(self):
        repo = MagicMock()
        repo.list_by_task.return_value = []
        after = datetime(2026, 1, 1, tzinfo=timezone.utc)

        get_task_timeline(uuid4(), repo, after=after)

        _, kwargs = repo.list_by_task.call_args
        assert kwargs['after'] == after


class TestGetRunTimeline:
    def test_delegates_to_repo(self):
        repo = MagicMock()
        repo.list_by_run.return_value = []
        rid = uuid4()

        get_run_timeline(rid, repo)

        repo.list_by_run.assert_called_once_with(rid, after=None, limit=100)

    def test_caps_limit_at_500(self):
        repo = MagicMock()
        repo.list_by_run.return_value = []

        get_run_timeline(uuid4(), repo, limit=1000)

        _, kwargs = repo.list_by_run.call_args
        assert kwargs['limit'] == 500


class TestGetWorkspaceEvents:
    def test_delegates_to_repo(self):
        repo = MagicMock()
        repo.list_by_workspace.return_value = []
        wsid = uuid4()

        get_workspace_events(wsid, repo)

        repo.list_by_workspace.assert_called_once_with(
            wsid, after_event_id=None, limit=100,
        )

    def test_passes_after_event_id(self):
        repo = MagicMock()
        repo.list_by_workspace.return_value = []
        after_id = uuid4()

        get_workspace_events(uuid4(), repo, after_event_id=after_id)

        _, kwargs = repo.list_by_workspace.call_args
        assert kwargs['after_event_id'] == after_id

    def test_caps_limit_at_500(self):
        repo = MagicMock()
        repo.list_by_workspace.return_value = []

        get_workspace_events(uuid4(), repo, limit=600)

        _, kwargs = repo.list_by_workspace.call_args
        assert kwargs['limit'] == 500


class TestGetRunEventsAfter:
    def test_delegates_to_repo(self):
        repo = MagicMock()
        repo.list_by_run_after_event.return_value = []
        rid = uuid4()

        get_run_events_after(rid, repo)

        repo.list_by_run_after_event.assert_called_once_with(
            rid, after_event_id=None, limit=100,
        )

    def test_caps_limit_at_500(self):
        repo = MagicMock()
        repo.list_by_run_after_event.return_value = []

        get_run_events_after(uuid4(), repo, limit=800)

        _, kwargs = repo.list_by_run_after_event.call_args
        assert kwargs['limit'] == 500
