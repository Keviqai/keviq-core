"""SMTP email delivery adapter."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from src.application.ports import EmailDelivery
from .smtp_config import SmtpConfig

log = structlog.get_logger("notification.email")


class SmtpEmailAdapter(EmailDelivery):
    """Sends email via SMTP. Logs success/failure; never raises."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    def send(self, *, to_email: str, subject: str, body_text: str) -> bool:
        """Send a plain-text email. Returns True on success, False on failure."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._config.from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body_text, "plain"))

        try:
            if self._config.use_tls and self._config.port == 465:
                smtp_cls = smtplib.SMTP_SSL
            else:
                smtp_cls = smtplib.SMTP

            with smtp_cls(self._config.host, self._config.port, timeout=10) as server:
                if self._config.use_tls and self._config.port != 465:
                    server.starttls()
                if self._config.username:
                    server.login(self._config.username, self._config.password)
                server.sendmail(self._config.from_email, [to_email], msg.as_string())

            log.info("email delivered", to=to_email, subject=subject)
            return True

        except Exception as exc:
            log.error("email delivery failed", to=to_email, subject=subject, error=str(exc))
            return False
