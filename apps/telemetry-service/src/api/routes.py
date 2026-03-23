import logging
import os

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import create_engine

from src.application.scrape_service import query_latest, scrape_all

logger = logging.getLogger(__name__)

router = APIRouter()

# ── DB engine (lazy init) ────────────────────────────────────

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("TELEMETRY_DB_URL")
        if not db_url:
            raise RuntimeError("TELEMETRY_DB_URL not configured")
        _engine = create_engine(db_url, pool_pre_ping=True, pool_size=5)
    return _engine


# ── Health ────────────────────────────────────────────────────

@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    info: dict = {"service": "telemetry-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Scrape trigger ────────────────────────────────────────────

@router.post("/internal/v1/scrape", status_code=status.HTTP_200_OK)
def trigger_scrape():
    """Trigger a scrape of /metrics from all configured targets.

    Scrapes api-gateway, orchestrator, agent-runtime /metrics endpoints,
    parses Prometheus text, persists samples to telemetry_core.metric_samples.
    """
    try:
        engine = _get_engine()
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    results = scrape_all(engine)
    total = sum(r["samples"] for r in results.values())
    errors = sum(1 for r in results.values() if r["error"])

    return {
        "status": "completed",
        "total_samples": total,
        "errors": errors,
        "details": results,
    }


# ── Query API ─────────────────────────────────────────────────

@router.get("/internal/v1/metrics")
def get_metrics(service: str | None = None):
    """Query latest metric samples, optionally filtered by service.

    Returns the most recent scrape's samples per service.
    """
    try:
        engine = _get_engine()
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    samples = query_latest(engine, service=service)
    return {"items": samples, "count": len(samples)}
