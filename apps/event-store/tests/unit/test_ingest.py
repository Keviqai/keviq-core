"""Unit tests for event ingest service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.application.ingest import ingest_event
from src.domain.event import StoredEvent


def _make_envelope(**overrides) -> dict:
    """Create a valid event envelope dict."""
    defaults = {
        'event_id': str(uuid4()),
        'event_type': 'task.created',
        'schema_version': '1.0',
        'workspace_id': str(uuid4()),
        'task_id': str(uuid4()),
        'run_id': None,
        'step_id': None,
        'correlation_id': str(uuid4()),
        'causation_id': None,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'emitted_by': {'service': 'orchestrator', 'instance_id': 'test'},
        'actor': {'type': 'user', 'id': 'u-1'},
        'payload': {'prompt': 'hello'},
    }
    defaults.update(overrides)
    return defaults


class TestIngestEvent:
    def test_new_event_returns_true(self):
        repo = MagicMock()
        repo.ingest.return_value = True
        envelope = _make_envelope()

        result = ingest_event(envelope, repo)

        assert result is True
        repo.ingest.assert_called_once()
        ingested = repo.ingest.call_args[0][0]
        assert isinstance(ingested, StoredEvent)
        assert str(ingested.id) == envelope['event_id']

    def test_duplicate_event_returns_false(self):
        repo = MagicMock()
        repo.ingest.return_value = False
        envelope = _make_envelope()

        result = ingest_event(envelope, repo)

        assert result is False

    def test_invalid_envelope_raises_value_error(self):
        repo = MagicMock()

        with pytest.raises(ValueError, match="Invalid event envelope"):
            ingest_event({}, repo)

    def test_missing_event_id_raises(self):
        repo = MagicMock()
        envelope = _make_envelope()
        del envelope['event_id']

        with pytest.raises(ValueError):
            ingest_event(envelope, repo)

    def test_invalid_uuid_raises(self):
        repo = MagicMock()
        envelope = _make_envelope(event_id='not-a-uuid')

        with pytest.raises(ValueError):
            ingest_event(envelope, repo)

    def test_string_occurred_at_parsed(self):
        repo = MagicMock()
        repo.ingest.return_value = True
        ts = '2026-01-15T10:30:00+00:00'
        envelope = _make_envelope(occurred_at=ts)

        ingest_event(envelope, repo)

        ingested = repo.ingest.call_args[0][0]
        assert isinstance(ingested.occurred_at, datetime)

    def test_datetime_occurred_at_preserved(self):
        repo = MagicMock()
        repo.ingest.return_value = True
        now = datetime.now(timezone.utc)
        envelope = _make_envelope(occurred_at=now)

        ingest_event(envelope, repo)

        ingested = repo.ingest.call_args[0][0]
        assert ingested.occurred_at == now

    def test_optional_fields_default_none(self):
        repo = MagicMock()
        repo.ingest.return_value = True
        envelope = _make_envelope(run_id=None, step_id=None, causation_id=None)

        ingest_event(envelope, repo)

        ingested = repo.ingest.call_args[0][0]
        assert ingested.run_id is None
        assert ingested.step_id is None
        assert ingested.causation_id is None

    def test_defaults_for_missing_optional_dicts(self):
        repo = MagicMock()
        repo.ingest.return_value = True
        envelope = _make_envelope()
        del envelope['emitted_by']
        del envelope['actor']

        ingest_event(envelope, repo)

        ingested = repo.ingest.call_args[0][0]
        assert ingested.emitted_by == {'service': 'unknown', 'instance_id': 'unknown'}
        assert ingested.actor == {'type': 'system', 'id': 'unknown'}
