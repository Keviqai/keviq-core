"""Scrape service — fetches /metrics from configured services and persists samples.

O8-S3: Lightweight metrics collector. Fetches Prometheus text from configured
service URLs, parses, and stores in telemetry_core.metric_samples.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .metrics_parser import MetricSample, parse_prometheus_text

logger = logging.getLogger(__name__)

# Module-level reusable HTTP client (Fix 7: avoid per-scrape client creation)
_http_client = httpx.Client(timeout=10)

SCHEMA = "telemetry_core"

# Default scrape targets — internal Docker URLs for all services with /metrics
_DEFAULT_TARGETS = {
    "api-gateway": os.getenv("API_GATEWAY_METRICS_URL", "http://api-gateway:8000/metrics"),
    "orchestrator": os.getenv("ORCHESTRATOR_METRICS_URL", "http://orchestrator:8000/metrics"),
    "agent-runtime": os.getenv("AGENT_RUNTIME_METRICS_URL", "http://agent-runtime:8000/metrics"),
    "auth-service": os.getenv("AUTH_SERVICE_METRICS_URL", "http://auth-service:8000/metrics"),
    "workspace-service": os.getenv("WORKSPACE_SERVICE_METRICS_URL", "http://workspace-service:8000/metrics"),
    "policy-service": os.getenv("POLICY_SERVICE_METRICS_URL", "http://policy-service:8000/metrics"),
    "artifact-service": os.getenv("ARTIFACT_SERVICE_METRICS_URL", "http://artifact-service:8000/metrics"),
    "execution-service": os.getenv("EXECUTION_SERVICE_METRICS_URL", "http://execution-service:8000/metrics"),
    "event-store": os.getenv("EVENT_STORE_METRICS_URL", "http://event-store:8000/metrics"),
    "model-gateway": os.getenv("MODEL_GATEWAY_METRICS_URL", "http://model-gateway:8000/metrics"),
    "audit-service": os.getenv("AUDIT_SERVICE_METRICS_URL", "http://audit-service:8000/metrics"),
    "notification-service": os.getenv("NOTIFICATION_SERVICE_METRICS_URL", "http://notification-service:8000/metrics"),
    "secret-broker": os.getenv("SECRET_BROKER_METRICS_URL", "http://secret-broker:8000/metrics"),
    "telemetry-service": os.getenv("TELEMETRY_SERVICE_METRICS_URL", "http://telemetry-service:8000/metrics"),
    "sse-gateway": os.getenv("SSE_GATEWAY_METRICS_URL", "http://sse-gateway:8000/metrics"),
}


def scrape_all(engine: Engine) -> dict[str, Any]:
    """Scrape /metrics from all configured targets and persist samples.

    Returns summary: {service: {samples: N, error: None|str}}.
    """
    now = datetime.now(timezone.utc)
    results: dict[str, Any] = {}

    for service, url in _DEFAULT_TARGETS.items():
        if not url:
            results[service] = {"samples": 0, "error": "URL not configured"}
            continue

        try:
            samples = _fetch_and_parse(url)
            _persist_samples(engine, service, samples, now)
            results[service] = {"samples": len(samples), "error": None}
            logger.info("Scraped %d metrics from %s", len(samples), service)
        except Exception as exc:
            results[service] = {"samples": 0, "error": str(exc)[:200]}
            logger.warning("Failed to scrape %s: %s", service, exc)

    return results


def _fetch_and_parse(url: str) -> list[MetricSample]:
    """Fetch /metrics URL and parse Prometheus text."""
    resp = _http_client.get(url)
    resp.raise_for_status()
    return parse_prometheus_text(resp.text)


def _persist_samples(
    engine: Engine,
    service: str,
    samples: list[MetricSample],
    scraped_at: datetime,
) -> None:
    """Insert parsed samples into metric_samples table."""
    if not samples:
        return

    params = [
        {
            "scraped_at": scraped_at,
            "service": service,
            "name": s.metric_name,
            "labels": json.dumps(s.labels),
            "value": s.value,
        }
        for s in samples
    ]

    with engine.connect() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {SCHEMA}.metric_samples
                    (scraped_at, source_service, metric_name, labels, value)
                VALUES (:scraped_at, :service, :name, CAST(:labels AS jsonb), :value)
            """),
            params,
        )
        conn.commit()


def query_latest(engine: Engine, service: str | None = None) -> list[dict]:
    """Query the latest metric samples, optionally filtered by service.

    Returns the most recent scrape's samples per service.
    """
    where = ""
    params: dict[str, Any] = {}
    if service:
        where = "WHERE source_service = :service"
        params["service"] = service

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                WITH latest AS (
                    SELECT source_service, MAX(scraped_at) AS max_at
                    FROM {SCHEMA}.metric_samples
                    {where}
                    GROUP BY source_service
                )
                SELECT ms.source_service, ms.metric_name, ms.labels, ms.value, ms.scraped_at
                FROM {SCHEMA}.metric_samples ms
                JOIN latest l ON ms.source_service = l.source_service AND ms.scraped_at = l.max_at
                ORDER BY ms.source_service, ms.metric_name
            """),
            params,
        ).fetchall()

    return [
        {
            "source_service": r.source_service,
            "metric_name": r.metric_name,
            "labels": r.labels if isinstance(r.labels, dict) else json.loads(r.labels) if r.labels else {},
            "value": r.value,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
        }
        for r in rows
    ]
