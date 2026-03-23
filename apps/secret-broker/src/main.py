import os

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry
from src.internal_auth import bootstrap_internal_auth
from src.application.bootstrap import configure_secret_deps
from src.infrastructure.db.secret_repository import SecretRepositoryAdapter

configure_logging("secret-broker")

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="secret-broker")

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get(
    'SECRET_DB_URL',
    'postgresql://superuser:superpassword@localhost/mona_os',
)
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

configure_secret_deps(
    secret_repo=SecretRepositoryAdapter(),
    session_factory=_session_factory,
)

# ── App (AFTER bootstrap) ─────────────────────────────────────
# Note: SECRET_ENCRYPTION_KEY is validated lazily in secret_service.py
# when create_secret() or retrieve_secret_value() is called.
# Service starts healthy even without the key — 500 only on actual secret ops.
from src.api.routes import router  # noqa: E402 — after bootstrap

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="secret-broker",
    version="0.1.0",
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="secret-broker")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
