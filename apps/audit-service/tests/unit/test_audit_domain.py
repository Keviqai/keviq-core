"""Unit tests for AuditEvent domain entity."""

import os
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'audit-service')
os.environ.setdefault('APP_ENV', 'development')


class TestAuditEventCreate:
    """AuditEvent.create() — field population and validation."""

    def _ws(self):
        return uuid4()

    def test_required_fields_populated(self):
        from src.domain.audit_event import AuditEvent
        ws = self._ws()
        ev = AuditEvent.create(actor_id='user-1', action='approval.requested', workspace_id=ws)
        assert ev.actor_id == 'user-1'
        assert ev.action == 'approval.requested'
        assert ev.workspace_id == ws

    def test_event_id_is_uuid(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='task.created', workspace_id=self._ws())
        assert isinstance(ev.event_id, UUID)

    def test_event_ids_are_unique(self):
        from src.domain.audit_event import AuditEvent
        ws = self._ws()
        ev1 = AuditEvent.create(actor_id='u', action='a', workspace_id=ws)
        ev2 = AuditEvent.create(actor_id='u', action='a', workspace_id=ws)
        assert ev1.event_id != ev2.event_id

    def test_default_actor_type_is_user(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws())
        assert ev.actor_type == 'user'

    def test_system_actor_type_accepted(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='system', action='a', workspace_id=self._ws(), actor_type='system')
        assert ev.actor_type == 'system'

    def test_invalid_actor_type_raises(self):
        from src.domain.audit_event import AuditEvent
        with pytest.raises(ValueError, match='actor_type'):
            AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws(), actor_type='robot')

    def test_empty_actor_id_raises(self):
        from src.domain.audit_event import AuditEvent
        with pytest.raises(ValueError, match='actor_id'):
            AuditEvent.create(actor_id='', action='a', workspace_id=self._ws())

    def test_empty_action_raises(self):
        from src.domain.audit_event import AuditEvent
        with pytest.raises(ValueError, match='action'):
            AuditEvent.create(actor_id='u', action='', workspace_id=self._ws())

    def test_target_fields_optional(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws())
        assert ev.target_id is None
        assert ev.target_type is None

    def test_target_fields_set(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(
            actor_id='u', action='a', workspace_id=self._ws(),
            target_id='artifact-1', target_type='artifact',
        )
        assert ev.target_id == 'artifact-1'
        assert ev.target_type == 'artifact'

    def test_metadata_defaults_to_empty_dict(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws())
        assert ev.metadata == {}

    def test_metadata_stored(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(
            actor_id='u', action='a', workspace_id=self._ws(),
            metadata={'approval_id': 'abc', 'decision': 'approved'},
        )
        assert ev.metadata['decision'] == 'approved'

    def test_occurred_at_is_utc(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws())
        assert ev.occurred_at.tzinfo is not None

    def test_custom_occurred_at_accepted(self):
        from src.domain.audit_event import AuditEvent
        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws(), occurred_at=ts)
        assert ev.occurred_at == ts

    def test_immutable(self):
        from src.domain.audit_event import AuditEvent
        ev = AuditEvent.create(actor_id='u', action='a', workspace_id=self._ws())
        with pytest.raises(Exception):
            ev.actor_id = 'other'  # type: ignore[misc]
