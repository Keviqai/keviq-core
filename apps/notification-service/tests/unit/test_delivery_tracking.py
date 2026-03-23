"""Unit tests for notification delivery tracking + retry logic (O2-S3)."""

import os
import sys
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("SERVICE_NAME", "notification-service")
os.environ.setdefault("APP_ENV", "development")


def _mock_repo():
    repo = MagicMock()
    repo.insert.side_effect = lambda db, n: {**n, 'id': str(n['id'])}
    repo.update_delivery_status.return_value = None
    return repo


def _mock_adapter(success=True):
    adapter = MagicMock()
    adapter.send.return_value = success
    return adapter


class TestDeliveryStatusOnCreate:
    """create_notification sets initial delivery_status='pending'."""

    def test_non_approval_stays_pending(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=None):
            result = svc.create_notification(
                MagicMock(), uuid4(), 'user-1', 'Test', category='system',
            )
        assert result['delivery_status'] == 'pending'

    def test_approval_with_email_sent(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=True)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            result = svc.create_notification(
                MagicMock(), uuid4(), 'user-1', 'Approval',
                category='approval', recipient_email='test@example.com',
            )
        assert result['delivery_status'] == 'sent'
        assert result['delivery_attempts'] == 1

    def test_approval_no_email_skipped(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=_mock_adapter()):
            result = svc.create_notification(
                MagicMock(), uuid4(), 'user-1', 'Approval',
                category='approval', recipient_email=None,
            )
        assert result['delivery_status'] == 'skipped'

    def test_approval_no_smtp_config_skipped(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=None):
            result = svc.create_notification(
                MagicMock(), uuid4(), 'user-1', 'Approval',
                category='approval', recipient_email='test@example.com',
            )
        assert result['delivery_status'] == 'skipped'
        assert result.get('last_delivery_error') == 'SMTP not configured'


class TestRetryLogic:
    """_attempt_email_delivery_with_retry — retry on failure."""

    def test_success_on_first_attempt(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=True)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            result = svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        assert result['delivery_status'] == 'sent'
        assert result['delivery_attempts'] == 1
        adapter.send.assert_called_once()

    def test_retry_then_success_on_second_attempt(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = MagicMock()
        adapter.send.side_effect = [False, True]  # fail first, succeed second
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter), \
             patch.object(svc.time, 'sleep'):  # skip actual sleep
            result = svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        assert result['delivery_status'] == 'sent'
        assert result['delivery_attempts'] == 2
        assert adapter.send.call_count == 2

    def test_all_retries_exhausted_then_failed(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=False)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter), \
             patch.object(svc.time, 'sleep'):
            result = svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        assert result['delivery_status'] == 'failed'
        assert result['delivery_attempts'] == 3  # MAX_DELIVERY_ATTEMPTS
        assert adapter.send.call_count == 3

    def test_max_attempts_constant(self):
        import src.application.notification_service as svc
        assert svc.MAX_DELIVERY_ATTEMPTS == 3

    def test_retry_delay_between_attempts(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=False)
        sleep_calls = []
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter), \
             patch.object(svc.time, 'sleep', side_effect=lambda s: sleep_calls.append(s)):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        # Should sleep between attempts (not after last)
        assert len(sleep_calls) == 2  # 3 attempts, 2 sleeps
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 3.0


class TestDeliveryStatusUpdate:
    """_update_delivery persists status to repo."""

    def test_sent_status_persisted(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=True)
        nid = uuid4()
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=nid,
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        repo.update_delivery_status.assert_called_once()
        call_kwargs = repo.update_delivery_status.call_args
        assert call_kwargs[1]['delivery_status'] == 'sent'
        assert call_kwargs[1]['delivery_attempts'] == 1

    def test_failed_status_persisted_with_error(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=False)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter), \
             patch.object(svc.time, 'sleep'):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        last_call = repo.update_delivery_status.call_args
        assert last_call[1]['delivery_status'] == 'failed'
        assert last_call[1]['last_delivery_error'] is not None

    def test_skipped_status_when_no_recipient(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=_mock_adapter()):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email=None, title='T', body='B', link='',
            )
        repo.update_delivery_status.assert_called_once()
        assert repo.update_delivery_status.call_args[1]['delivery_status'] == 'skipped'

    def test_repo_update_failure_does_not_crash(self):
        """If update_delivery_status raises, the delivery function still returns."""
        import src.application.notification_service as svc
        repo = _mock_repo()
        repo.update_delivery_status.side_effect = Exception("DB error")
        adapter = _mock_adapter(success=True)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            result = svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T', body='B', link='',
            )
        # Should still return sent — status update failure is logged, not raised
        assert result['delivery_status'] == 'sent'


class TestEmailBodyFormat:
    """Email body includes link when provided."""

    def test_body_with_link(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=True)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T',
                body='Approval needed', link='/workspaces/123/approvals/456',
            )
        call_kwargs = adapter.send.call_args[1]
        assert 'Approval needed' in call_kwargs['body_text']
        assert '/workspaces/123/approvals/456' in call_kwargs['body_text']

    def test_body_without_link(self):
        import src.application.notification_service as svc
        repo = _mock_repo()
        adapter = _mock_adapter(success=True)
        with patch.object(svc, 'get_notification_repo', return_value=repo), \
             patch.object(svc, 'get_email_adapter', return_value=adapter):
            svc._attempt_email_delivery_with_retry(
                db=MagicMock(), notification_id=uuid4(),
                recipient_email='a@b.com', title='T',
                body='Simple body', link='',
            )
        call_kwargs = adapter.send.call_args[1]
        assert call_kwargs['body_text'] == 'Simple body'
