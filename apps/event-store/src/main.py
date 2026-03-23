import os

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("event-store")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import configure_repo_factory
from src.infrastructure.db.repository import SqlEventRepository
from src.internal_auth import bootstrap_internal_auth

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="event-store")

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get("EVENT_STORE_DB_URL")
if not _db_url:
    raise RuntimeError("EVENT_STORE_DB_URL environment variable is required")

_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=15, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine)

configure_repo_factory(lambda: SqlEventRepository(_session_factory()))

# ── App ─────────────────────────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap
from src.api.sse import sse_router  # noqa: E402

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(**({} if _app_env == "development" else _docs_off))
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="event-store")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(sse_router)
