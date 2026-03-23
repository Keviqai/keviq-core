import os

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry
from src.internal_auth import bootstrap_internal_auth

configure_logging("model-gateway")

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="model-gateway")

# ── Configure infrastructure ────────────────────────────────────
from src.application.model_service import ModelExecutionService
from src.infrastructure.config import EnvProviderConfigLoader
from src.infrastructure.db.usage_writer import DbUsageRecordWriter
from src.infrastructure.provider_factory import ProviderFactory

_db_url = os.environ.get("MODEL_GW_DB_URL")
if not _db_url:
    raise RuntimeError("MODEL_GW_DB_URL environment variable is required")
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

# ── Integration config management ────────────────────────────
from src.application.integration_bootstrap import configure_integration_deps
from src.infrastructure.db.integration_repository import IntegrationRepositoryAdapter

configure_integration_deps(
    integration_repo=IntegrationRepositoryAdapter(),
    session_factory=_session_factory,
)

_model_service = ModelExecutionService(
    config_loader=EnvProviderConfigLoader(),
    provider_factory=ProviderFactory(),
    usage_writer=DbUsageRecordWriter(_engine),
)

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import configure_service, router  # noqa: E402 — after bootstrap
from src.api.integration_routes import integration_router  # noqa: E402

configure_service(_model_service)

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(**({} if _app_env == "development" else _docs_off))
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="model-gateway")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(integration_router)
