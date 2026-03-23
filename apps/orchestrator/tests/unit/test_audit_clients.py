"""Unit tests for audit_clients.py — fail-open behavior."""

import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

os.environ.setdefault('SERVICE_NAME', 'orchestrator')
os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')


class TestRecordAudit:
    """record_audit() — fail-open, correct payload, no AUDIT_SERVICE_URL."""

    def _call(self, **kwargs):
        from src.infrastructure.audit_clients import record_audit
        defaults = dict(
            actor_id='user-1',
            action='approval.requested',
            workspace_id=uuid4(),
        )
        defaults.update(kwargs)
        return record_audit(**defaults)

    def test_no_url_configured_returns_silently(self):
        """Fail-open: missing AUDIT_SERVICE_URL → no exception, logs warning."""
        import src.infrastructure.audit_clients as mod
        original = mod._AUDIT_SERVICE_URL
        mod._AUDIT_SERVICE_URL = ''
        try:
            self._call()  # must not raise
        finally:
            mod._AUDIT_SERVICE_URL = original

    def test_http_error_returns_silently(self):
        """Fail-open: audit-service returns non-201 → log warning, no raise."""
        import src.infrastructure.audit_clients as mod
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(mod, '_AUDIT_SERVICE_URL', 'http://audit-service:8000'), \
             patch('src.infrastructure.audit_clients.get_auth_client') as mock_auth, \
             patch('src.infrastructure.audit_clients.httpx.post', return_value=mock_resp):
            mock_auth.return_value.auth_headers.return_value = {}
            self._call()  # must not raise

    def test_connection_error_returns_silently(self):
        """Fail-open: connection refused → log error, no raise."""
        import src.infrastructure.audit_clients as mod
        import httpx

        with patch.object(mod, '_AUDIT_SERVICE_URL', 'http://audit-service:8000'), \
             patch('src.infrastructure.audit_clients.get_auth_client') as mock_auth, \
             patch('src.infrastructure.audit_clients.httpx.post', side_effect=httpx.ConnectError("refused")):
            mock_auth.return_value.auth_headers.return_value = {}
            self._call()  # must not raise

    def test_success_posts_correct_payload(self):
        """On success, POST contains required audit fields."""
        import src.infrastructure.audit_clients as mod

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        ws = uuid4()
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured['payload'] = json
            return mock_resp

        with patch.object(mod, '_AUDIT_SERVICE_URL', 'http://audit-service:8000'), \
             patch('src.infrastructure.audit_clients.get_auth_client') as mock_auth, \
             patch('src.infrastructure.audit_clients.httpx.post', side_effect=fake_post):
            mock_auth.return_value.auth_headers.return_value = {}
            self._call(
                actor_id='user-abc',
                action='approval.decided',
                workspace_id=ws,
                target_id='art-1',
                target_type='artifact',
                metadata={'decision': 'approved'},
            )

        payload = captured['payload']
        assert payload['actor_id'] == 'user-abc'
        assert payload['action'] == 'approval.decided'
        assert payload['workspace_id'] == str(ws)
        assert payload['target_id'] == 'art-1'
        assert payload['target_type'] == 'artifact'
        assert payload['metadata']['decision'] == 'approved'

    def test_posts_to_correct_endpoint(self):
        """URL is /internal/v1/audit-events."""
        import src.infrastructure.audit_clients as mod

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        captured_url = {}

        def fake_post(url, **kwargs):
            captured_url['url'] = url
            return mock_resp

        with patch.object(mod, '_AUDIT_SERVICE_URL', 'http://audit:8000'), \
             patch('src.infrastructure.audit_clients.get_auth_client') as mock_auth, \
             patch('src.infrastructure.audit_clients.httpx.post', side_effect=fake_post):
            mock_auth.return_value.auth_headers.return_value = {}
            self._call()

        assert captured_url['url'] == 'http://audit:8000/internal/v1/audit-events'
