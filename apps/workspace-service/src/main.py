import os
import sys

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("workspace-service")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import configure_workspace_deps
from src.infrastructure.db.workspace_repository import WorkspaceRepositoryAdapter
from src.infrastructure.outbox.outbox_repository import OutboxWriterAdapter
from src.infrastructure.auth_client import AuthServiceMemberEnricher

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get(
    'WORKSPACE_DB_URL',
    'postgresql://superuser:superpassword@localhost/mona_os',
)
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

configure_workspace_deps(
    workspace_repo=WorkspaceRepositoryAdapter(),
    outbox_writer=OutboxWriterAdapter(),
    member_enricher=AuthServiceMemberEnricher(),
    session_factory=_session_factory,
)

# ── Bootstrap internal auth (optional — skip if secret not configured) ──
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'packages', 'internal-auth')
))
_internal_auth_secret = os.environ.get("INTERNAL_AUTH_SECRET")
if _internal_auth_secret:
    from internal_auth.bootstrap import bootstrap_internal_auth  # noqa: E402
    bootstrap_internal_auth(service_name=os.environ.get("SERVICE_NAME", "workspace-service"))

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="workspace-service",
    version="0.1.0",
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="workspace-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
