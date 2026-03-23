import src.resilience_bridge  # noqa: F401 — adds resilience package to sys.path

import os

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("artifact-service")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import configure_storage_backend, configure_uow_factory
from src.infrastructure.db.unit_of_work import SqlUnitOfWork
from src.infrastructure.storage.local import LocalStorageBackend
from src.internal_auth import bootstrap_internal_auth

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="artifact-service")

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get("ARTIFACT_DB_URL")
if not _db_url:
    raise RuntimeError("ARTIFACT_DB_URL environment variable is required")
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=15, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine)

configure_uow_factory(
    lambda: SqlUnitOfWork(_session_factory),
    session_factory=_session_factory,
)

configure_storage_backend(LocalStorageBackend(os.getenv("ARTIFACT_STORAGE_PATH")))

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap
from src.api.routes_annotations import router as annotations_router  # noqa: E402

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(**({} if _app_env == "development" else _docs_off))
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="artifact-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(annotations_router)
