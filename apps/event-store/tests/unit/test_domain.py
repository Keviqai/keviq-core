"""Unit tests for event-store domain model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.event import StoredEvent, event_to_dict


def _make_event(**overrides) -> StoredEvent:
    """Create a StoredEvent with sensible defaults."""
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
        payload={'prompt': 'hello'},
        received_at=now,
    )
    defaults.update(overrides)
    return StoredEvent(**defaults)


class TestStoredEvent:
    def test_frozen(self):
        event = _make_event()
        try:
            event.event_type = 'task.updated'  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass

    def test_fields(self):
        eid = uuid4()
        wsid = uuid4()
        event = _make_event(id=eid, workspace_id=wsid, event_type='run.started')
        assert event.id == eid
        assert event.workspace_id == wsid
        assert event.event_type == 'run.started'


class TestEventToDict:
    def test_required_fields_present(self):
        event = _make_event()
        d = event_to_dict(event)
        assert d['event_id'] == str(event.id)
        assert d['event_type'] == 'task.created'
        assert d['schema_version'] == '1.0'
        assert d['workspace_id'] == str(event.workspace_id)
        assert d['correlation_id'] == str(event.correlation_id)
        assert 'occurred_at' in d
        assert 'received_at' in d
        assert d['emitted_by'] == event.emitted_by
        assert d['actor'] == event.actor
        assert d['payload'] == event.payload

    def test_optional_fields_included_when_set(self):
        tid = uuid4()
        rid = uuid4()
        sid = uuid4()
        cid = uuid4()
        event = _make_event(task_id=tid, run_id=rid, step_id=sid, causation_id=cid)
        d = event_to_dict(event)
        assert d['task_id'] == str(tid)
        assert d['run_id'] == str(rid)
        assert d['step_id'] == str(sid)
        assert d['causation_id'] == str(cid)

    def test_optional_fields_omitted_when_none(self):
        event = _make_event(task_id=None, run_id=None, step_id=None, causation_id=None)
        d = event_to_dict(event)
        assert 'task_id' not in d
        assert 'run_id' not in d
        assert 'step_id' not in d
        assert 'causation_id' not in d

    def test_datetime_serialized_as_isoformat(self):
        now = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        event = _make_event(occurred_at=now, received_at=now)
        d = event_to_dict(event)
        assert d['occurred_at'] == '2026-01-15T10:30:00+00:00'
        assert d['received_at'] == '2026-01-15T10:30:00+00:00'
