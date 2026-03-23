import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry
from src.application.bootstrap import (
    configure_execution_backend,
    configure_sandbox_backend,
    configure_uow_factory,
)
from src.infrastructure.db.unit_of_work import SqlUnitOfWork
from src.internal_auth import bootstrap_internal_auth

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="execution-service")

# ── Logging ────────────────────────────────────────────────────
configure_logging("execution-service")

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get("EXECUTION_DB_URL")
if not _db_url:
    raise RuntimeError("EXECUTION_DB_URL environment variable is required")
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=15, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine)

configure_uow_factory(
    lambda: SqlUnitOfWork(_session_factory),
    session_factory=_session_factory,
)

_execution_backend_type = os.getenv("EXECUTION_BACKEND", "docker-local")
_docker_client = None

if _execution_backend_type == "docker-local":
    import docker as _docker_lib  # noqa: E402
    from src.infrastructure.sandbox.docker_backend import DockerSandboxBackend  # noqa: E402
    from src.infrastructure.sandbox.docker_execution_backend import DockerExecutionBackend  # noqa: E402
    _docker_client = _docker_lib.from_env()
    _sandbox_backend = DockerSandboxBackend(docker_client=_docker_client)
    _exec_backend = DockerExecutionBackend(docker_client=_docker_client)
elif _execution_backend_type == "noop":
    from src.infrastructure.sandbox.noop_backend import NoopExecutionBackend, NoopSandboxBackend
    _sandbox_backend = NoopSandboxBackend()
    _exec_backend = NoopExecutionBackend()
else:
    raise RuntimeError(
        f"Unknown EXECUTION_BACKEND: {_execution_backend_type!r}. "
        f"Valid values: docker-local, noop"
    )

configure_sandbox_backend(_sandbox_backend)
configure_execution_backend(_exec_backend)

# ── App ─────────────────────────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap
from src.api.terminal_routes import router as terminal_router  # noqa: E402

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    if _docker_client is not None:
        _docker_client.close()


app = FastAPI(
    lifespan=_lifespan,
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="execution-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(terminal_router)
