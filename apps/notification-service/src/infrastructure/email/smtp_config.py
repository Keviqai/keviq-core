"""SMTP configuration from environment variables."""

from __future__ import annotations

import dataclasses
import os


@dataclasses.dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool


def get_smtp_config() -> SmtpConfig | None:
    """Read SMTP config from env. Returns None if SMTP_HOST not set (delivery disabled)."""
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    return SmtpConfig(
        host=host,
        port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        from_email=os.getenv("SMTP_FROM_EMAIL", "noreply@keviq.app"),
        use_tls=os.getenv("SMTP_USE_TLS", "true").lower() not in ("false", "0", "no"),
    )
