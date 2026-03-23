import os

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("policy-service")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import configure_policy_deps
from src.infrastructure.db.policy_repository import PolicyRepositoryAdapter

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get(
    'POLICY_DB_URL',
    'postgresql://superuser:superpassword@localhost/mona_os',
)
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

configure_policy_deps(
    policy_repo=PolicyRepositoryAdapter(),
    session_factory=_session_factory,
)

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="policy-service",
    version="0.1.0",
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="policy-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
