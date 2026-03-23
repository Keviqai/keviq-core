"""structlog configuration for Keviq Core services."""

from __future__ import annotations

import logging
import os
import sys

import structlog

from .context import get_request_id

_SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown")
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_APP_ENV = os.getenv("APP_ENV", "development")


def _add_service_name(
    logger: logging.Logger,
    method: str,
    event_dict: dict,
) -> dict:
    event_dict.setdefault("service", _SERVICE_NAME)
    return event_dict


def _add_request_id(
    logger: logging.Logger,
    method: str,
    event_dict: dict,
) -> dict:
    rid = get_request_id()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(service_name: str | None = None) -> None:
    """Configure structlog for a Keviq Core service.

    Call once at service startup, before any requests are handled.
    """
    global _SERVICE_NAME
    if service_name:
        _SERVICE_NAME = service_name
        os.environ.setdefault("SERVICE_NAME", service_name)

    log_level = getattr(logging, _LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_service_name,
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if _APP_ENV == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger(service_name or "service")
    log.info(
        "service started",
        service=_SERVICE_NAME,
        log_level=_LOG_LEVEL,
        app_env=_APP_ENV,
    )
