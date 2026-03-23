"""Notification domain constants and validation.

Pure data — no infrastructure imports.
"""

VALID_CHANNELS = {'in_app', 'email'}
VALID_PRIORITIES = {'low', 'normal', 'high', 'urgent'}
VALID_CATEGORIES = {'task', 'run', 'approval', 'artifact', 'workspace', 'system'}


class NotificationError(Exception):
    """Base notification domain error."""


class NotificationNotFound(NotificationError):
    """Raised when a notification is not found."""

    def __init__(self, notification_id: str) -> None:
        super().__init__(f"Notification not found: {notification_id}")
        self.notification_id = notification_id
