"""Unit tests for notification-service SMTP delivery."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("SERVICE_NAME", "notification-service")
os.environ.setdefault("APP_ENV", "development")


class TestSmtpConfig:
    """get_smtp_config() returns config only when SMTP_HOST is set."""

    def _get(self, env_overrides: dict):
        from src.infrastructure.email.smtp_config import get_smtp_config
        with patch.dict(os.environ, env_overrides, clear=False):
            # Remove SMTP_HOST if not in overrides to test missing case
            env = {**os.environ, **env_overrides}
            if "SMTP_HOST" not in env_overrides:
                env.pop("SMTP_HOST", None)
            with patch.dict(os.environ, env, clear=True):
                return get_smtp_config()

    def test_no_smtp_host_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            # Temporarily remove SMTP_HOST
            saved = os.environ.pop("SMTP_HOST", None)
            try:
                from src.infrastructure.email.smtp_config import get_smtp_config
                result = get_smtp_config()
                assert result is None
            finally:
                if saved:
                    os.environ["SMTP_HOST"] = saved

    def test_smtp_host_set_returns_config(self):
        from src.infrastructure.email.smtp_config import get_smtp_config, SmtpConfig
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user@example.com",
            "SMTP_PASSWORD": "secret",
            "SMTP_FROM_EMAIL": "noreply@example.com",
            "SMTP_USE_TLS": "true",
        }):
            cfg = get_smtp_config()
        assert cfg is not None
        assert isinstance(cfg, SmtpConfig)
        assert cfg.host == "smtp.example.com"
        assert cfg.port == 587
        assert cfg.from_email == "noreply@example.com"
        assert cfg.use_tls is True

    def test_default_port_is_587(self):
        from src.infrastructure.email.smtp_config import get_smtp_config
        with patch.dict(os.environ, {"SMTP_HOST": "mail.example.com"}):
            cfg = get_smtp_config()
        assert cfg.port == 587

    def test_default_from_email(self):
        from src.infrastructure.email.smtp_config import get_smtp_config
        with patch.dict(os.environ, {"SMTP_HOST": "mail.example.com"}):
            cfg = get_smtp_config()
        assert cfg.from_email == "noreply@keviq.app"

    def test_use_tls_false_string(self):
        from src.infrastructure.email.smtp_config import get_smtp_config
        with patch.dict(os.environ, {"SMTP_HOST": "mail.example.com", "SMTP_USE_TLS": "false"}):
            cfg = get_smtp_config()
        assert cfg.use_tls is False

    def test_use_tls_zero_string(self):
        from src.infrastructure.email.smtp_config import get_smtp_config
        with patch.dict(os.environ, {"SMTP_HOST": "mail.example.com", "SMTP_USE_TLS": "0"}):
            cfg = get_smtp_config()
        assert cfg.use_tls is False


class TestSmtpEmailAdapter:
    """SmtpEmailAdapter.send() — success, failure, auth paths."""

    def _make_config(self, **kwargs):
        from src.infrastructure.email.smtp_config import SmtpConfig
        defaults = dict(
            host="smtp.example.com", port=587, username="u", password="p",
            from_email="noreply@example.com", use_tls=True,
        )
        defaults.update(kwargs)
        return SmtpConfig(**defaults)

    def test_send_success_returns_true(self):
        from src.infrastructure.email.smtp_adapter import SmtpEmailAdapter
        adapter = SmtpEmailAdapter(self._make_config())
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP", return_value=mock_smtp):
            result = adapter.send(
                to_email="user@example.com",
                subject="Test subject",
                body_text="Hello",
            )

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("u", "p")
        mock_smtp.sendmail.assert_called_once()

    def test_send_failure_returns_false(self):
        from src.infrastructure.email.smtp_adapter import SmtpEmailAdapter
        import smtplib
        adapter = SmtpEmailAdapter(self._make_config())

        with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP") as mock_cls:
            mock_cls.side_effect = smtplib.SMTPConnectError(111, "Connection refused")
            result = adapter.send(
                to_email="user@example.com",
                subject="Test",
                body_text="Body",
            )

        assert result is False

    def test_ssl_port_465_uses_smtp_ssl(self):
        from src.infrastructure.email.smtp_adapter import SmtpEmailAdapter
        adapter = SmtpEmailAdapter(self._make_config(port=465))
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP_SSL", return_value=mock_smtp) as mock_ssl:
            with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP") as mock_plain:
                adapter.send(to_email="x@x.com", subject="s", body_text="b")
                mock_ssl.assert_called_once()
                mock_plain.assert_not_called()

    def test_no_credentials_skips_login(self):
        from src.infrastructure.email.smtp_adapter import SmtpEmailAdapter
        adapter = SmtpEmailAdapter(self._make_config(username="", password=""))
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP", return_value=mock_smtp):
            adapter.send(to_email="x@x.com", subject="s", body_text="b")

        mock_smtp.login.assert_not_called()

    def test_send_correct_recipient(self):
        from src.infrastructure.email.smtp_adapter import SmtpEmailAdapter
        adapter = SmtpEmailAdapter(self._make_config())
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("src.infrastructure.email.smtp_adapter.smtplib.SMTP", return_value=mock_smtp):
            adapter.send(to_email="recipient@example.com", subject="s", body_text="b")

        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][1] == ["recipient@example.com"]


class TestCreateNotificationEmailIntegration:
    """create_notification() triggers email for approval category."""

    def _make_repo(self):
        mock_repo = MagicMock()
        mock_repo.insert.return_value = {
            "id": "uuid-1", "workspace_id": "ws-1", "user_id": "user-1",
            "title": "T", "body": "", "category": "approval", "priority": "high",
            "link": "", "is_read": False, "created_at": "2026-01-01T00:00:00Z", "read_at": None,
        }
        return mock_repo

    def test_approval_with_email_triggers_delivery(self):
        import src.application.notification_service as svc
        import uuid

        mock_repo = self._make_repo()
        mock_adapter = MagicMock()
        mock_adapter.send.return_value = True

        with patch.object(svc, "get_notification_repo", return_value=mock_repo), \
             patch.object(svc, "get_email_adapter", return_value=mock_adapter):
            svc.create_notification(
                db=MagicMock(),
                workspace_id=uuid.uuid4(),
                user_id="user-1",
                title="Approval requested",
                category="approval",
                recipient_email="user@example.com",
            )

        mock_adapter.send.assert_called_once()

    def test_non_approval_category_no_email(self):
        import src.application.notification_service as svc
        import uuid

        mock_repo = self._make_repo()
        mock_repo.insert.return_value["category"] = "task"
        mock_adapter = MagicMock()

        with patch.object(svc, "get_notification_repo", return_value=mock_repo), \
             patch.object(svc, "get_email_adapter", return_value=mock_adapter):
            svc.create_notification(
                db=MagicMock(),
                workspace_id=uuid.uuid4(),
                user_id="user-1",
                title="Task update",
                category="task",
                recipient_email="user@example.com",
            )

        mock_adapter.send.assert_not_called()

    def test_approval_row_created_even_if_email_fails(self):
        import src.application.notification_service as svc
        import uuid

        mock_repo = self._make_repo()
        mock_adapter = MagicMock()
        mock_adapter.send.return_value = False  # delivery fails

        with patch.object(svc, "get_notification_repo", return_value=mock_repo), \
             patch.object(svc, "get_email_adapter", return_value=mock_adapter), \
             patch.object(svc.time, "sleep"):
            result = svc.create_notification(
                db=MagicMock(),
                workspace_id=uuid.uuid4(),
                user_id="user-1",
                title="Approval",
                category="approval",
                recipient_email="user@example.com",
            )

        # Row was returned regardless of email result
        assert result is not None
        mock_repo.insert.assert_called_once()
