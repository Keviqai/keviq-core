"""Unit tests for audit application service (mock repository)."""

import os
import sys
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'audit-service')
os.environ.setdefault('APP_ENV', 'development')


def _make_repo(insert_return=None):
    mock = MagicMock()
    mock.insert.return_value = insert_return or {
        'event_id': str(uuid4()),
        'actor_id': 'user-1',
        'actor_type': 'user',
        'action': 'approval.requested',
        'target_id': 'art-1',
        'target_type': 'artifact',
        'workspace_id': str(uuid4()),
        'metadata': {},
        'occurred_at': '2026-01-01T00:00:00+00:00',
    }
    mock.find_by_workspace.return_value = []
    return mock


class TestRecordAuditEvent:
    """record_audit_event() — create and persist."""

    def test_success_returns_dict(self):
        import src.application.audit_service as svc
        ws = uuid4()
        repo = _make_repo()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            result = svc.record_audit_event(
                MagicMock(),
                actor_id='user-1',
                action='approval.requested',
                workspace_id=ws,
                target_id='art-1',
                target_type='artifact',
            )

        assert repo.insert.called
        assert result['action'] == 'approval.requested'

    def test_insert_called_once(self):
        import src.application.audit_service as svc
        repo = _make_repo()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            svc.record_audit_event(
                MagicMock(),
                actor_id='u', action='a', workspace_id=uuid4(),
            )

        repo.insert.assert_called_once()

    def test_domain_entity_passed_to_repo(self):
        import src.application.audit_service as svc
        from src.domain.audit_event import AuditEvent
        repo = _make_repo()
        ws = uuid4()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            svc.record_audit_event(
                MagicMock(),
                actor_id='user-1',
                action='approval.decided',
                workspace_id=ws,
            )

        call_args = repo.insert.call_args
        entity = call_args[0][1]  # second positional arg
        assert isinstance(entity, AuditEvent)
        assert entity.actor_id == 'user-1'
        assert entity.action == 'approval.decided'
        assert entity.workspace_id == ws

    def test_invalid_action_raises_value_error(self):
        import src.application.audit_service as svc
        repo = _make_repo()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            with pytest.raises(ValueError):
                svc.record_audit_event(
                    MagicMock(),
                    actor_id='u', action='', workspace_id=uuid4(),
                )


class TestListAuditEvents:
    """list_audit_events() — query with filters."""

    def test_returns_list(self):
        import src.application.audit_service as svc
        repo = _make_repo()
        ws = uuid4()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            result = svc.list_audit_events(MagicMock(), ws)

        assert isinstance(result, list)
        repo.find_by_workspace.assert_called_once()

    def test_action_filter_passed_to_repo(self):
        import src.application.audit_service as svc
        repo = _make_repo()
        ws = uuid4()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            svc.list_audit_events(MagicMock(), ws, action='approval.requested')

        _, kwargs = repo.find_by_workspace.call_args
        assert kwargs['action'] == 'approval.requested'

    def test_limit_capped_at_max(self):
        import src.application.audit_service as svc
        repo = _make_repo()
        ws = uuid4()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            svc.list_audit_events(MagicMock(), ws, limit=9999)

        _, kwargs = repo.find_by_workspace.call_args
        assert kwargs['limit'] <= 200

    def test_offset_non_negative(self):
        import src.application.audit_service as svc
        repo = _make_repo()
        ws = uuid4()

        with __import__('unittest.mock', fromlist=['patch']).patch.object(
            svc, 'get_audit_repo', return_value=repo,
        ):
            svc.list_audit_events(MagicMock(), ws, offset=-5)

        _, kwargs = repo.find_by_workspace.call_args
        assert kwargs['offset'] == 0
