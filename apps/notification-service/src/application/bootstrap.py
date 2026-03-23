"""Application bootstrap — dependency provider for notification-service.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from typing import Any

from .ports import EmailDelivery, NotificationRepository

_notification_repo: NotificationRepository | None = None
_email_adapter: EmailDelivery | None = None
_session_factory: Any = None
_configured = False


def configure_notification_deps(
    *,
    notification_repo: NotificationRepository,
    session_factory: Any = None,
    email_adapter: EmailDelivery | None = None,
) -> None:
    global _notification_repo, _email_adapter, _session_factory, _configured
    if _configured:
        raise RuntimeError("Notification dependencies already configured")
    _notification_repo = notification_repo
    _email_adapter = email_adapter
    _session_factory = session_factory
    _configured = True


def get_notification_repo() -> NotificationRepository:
    if _notification_repo is None:
        raise RuntimeError("Notification repository not configured — call configure_notification_deps() at startup")
    return _notification_repo


def get_email_adapter() -> EmailDelivery | None:
    """Returns the email adapter, or None if SMTP is not configured."""
    return _email_adapter


def get_session_factory() -> Any:
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
