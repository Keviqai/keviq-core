import os
import sys

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("auth-service")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import configure_auth_deps
from src.infrastructure.auth.jwt_handler import JwtHandlerAdapter
from src.infrastructure.auth.password_hasher import PasswordHasherAdapter
from src.infrastructure.db.user_repository import UserRepositoryAdapter

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get(
    'AUTH_DB_URL',
    'postgresql://superuser:superpassword@localhost/mona_os',
)
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=10, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

configure_auth_deps(
    user_repo=UserRepositoryAdapter(),
    password_hasher=PasswordHasherAdapter(),
    jwt_handler=JwtHandlerAdapter(),
    session_factory=_session_factory,
)

# ── Bootstrap internal auth (optional — skip if secret not configured) ──
sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'packages', 'internal-auth')
))
_internal_auth_secret = os.environ.get("INTERNAL_AUTH_SECRET")
if _internal_auth_secret:
    from internal_auth.bootstrap import bootstrap_internal_auth  # noqa: E402
    bootstrap_internal_auth(service_name=os.environ.get("SERVICE_NAME", "auth-service"))

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap
from src.api.internal_routes import router as internal_router  # noqa: E402

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="auth-service",
    version="0.1.0",
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="auth-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(internal_router)
