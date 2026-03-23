import src.resilience_bridge  # noqa: F401 — adds resilience package to sys.path

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("orchestrator")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.bootstrap import (
    configure_dispatcher,
    configure_execution_service,
    configure_uow_factory,
)
from src.application.recovery import recover_stuck_entities
from src.infrastructure.db.unit_of_work import SqlUnitOfWork
from src.infrastructure.execution_service_client import HttpExecutionServiceClient
from src.infrastructure.outbox.relay import (
    close_relay_client,
    relay_pending_events,
)
from src.infrastructure.runtime_client import HttpRuntimeClient
from src.internal_auth import bootstrap_internal_auth

logger = logging.getLogger(__name__)

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="orchestrator")

# ── Configure infrastructure ────────────────────────────────────
_db_url = os.environ.get("ORCHESTRATOR_DB_URL")
if not _db_url:
    raise RuntimeError("ORCHESTRATOR_DB_URL environment variable is required")
_engine = create_engine(_db_url, pool_pre_ping=True, pool_size=15, max_overflow=5, pool_recycle=3600)
_session_factory = sessionmaker(bind=_engine)

configure_uow_factory(
    lambda: SqlUnitOfWork(_session_factory),
    session_factory=_session_factory,
)

_runtime_url = os.environ.get("AGENT_RUNTIME_URL")
if not _runtime_url:
    raise RuntimeError("AGENT_RUNTIME_URL environment variable is required")

_runtime_client = HttpRuntimeClient(base_url=_runtime_url)
configure_dispatcher(_runtime_client)

_execution_service_url = os.environ.get("EXECUTION_SERVICE_URL")
_execution_service_client: HttpExecutionServiceClient | None = None
if _execution_service_url:
    _execution_service_client = HttpExecutionServiceClient(base_url=_execution_service_url)
    configure_execution_service(_execution_service_client)

# ── Background task config ─────────────────────────────────────────
RECOVERY_INTERVAL_SECONDS = int(os.getenv("RECOVERY_INTERVAL_SECONDS", "60"))
OUTBOX_RELAY_INTERVAL_SECONDS = int(os.getenv("OUTBOX_RELAY_INTERVAL_SECONDS", "5"))


async def _recovery_sweep_loop() -> None:
    """Periodically run the recovery sweep as a background task."""
    while True:
        try:
            uow = SqlUnitOfWork(_session_factory)
            results = await asyncio.to_thread(recover_stuck_entities, uow)
            if results:
                logger.info(
                    "Recovery sweep completed: %d actions (%d failed)",
                    len(results),
                    sum(1 for r in results if not r.success),
                )
        except Exception:
            logger.exception("Recovery sweep failed")
        await asyncio.sleep(RECOVERY_INTERVAL_SECONDS)


async def _outbox_relay_loop() -> None:
    """Periodically relay unpublished outbox events to event-store."""
    while True:
        try:
            session = _session_factory()
            try:
                relayed = await asyncio.to_thread(relay_pending_events, session)
                if relayed:
                    logger.debug("Outbox relay: forwarded %d events", relayed)
            finally:
                session.close()
        except Exception:
            logger.exception("Outbox relay cycle failed")
        await asyncio.sleep(OUTBOX_RELAY_INTERVAL_SECONDS)


# ── App ─────────────────────────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap
from src.api.approval_routes import router as approval_router  # noqa: E402
from src.api.routes_brief import router as brief_router  # noqa: E402
from src.api.routes_templates import router as templates_router  # noqa: E402
from src.api.routes_cleanup import router as cleanup_router  # noqa: E402
from src.api.tool_approval_routes import router as tool_approval_router  # noqa: E402
from src.api.comment_routes import router as comment_router  # noqa: E402

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    recovery_task = asyncio.create_task(_recovery_sweep_loop())
    relay_task = asyncio.create_task(_outbox_relay_loop())
    logger.info("Recovery sweep scheduled every %ds", RECOVERY_INTERVAL_SECONDS)
    logger.info("Outbox relay scheduled every %ds", OUTBOX_RELAY_INTERVAL_SECONDS)
    try:
        yield
    finally:
        recovery_task.cancel()
        relay_task.cancel()
        for task in (recovery_task, relay_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        _runtime_client.close()
        if _execution_service_client is not None:
            _execution_service_client.close()
        close_relay_client()


app = FastAPI(
    lifespan=_lifespan,
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="orchestrator")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
app.include_router(approval_router)
app.include_router(brief_router)
app.include_router(templates_router)
app.include_router(cleanup_router)
app.include_router(tool_approval_router)
app.include_router(comment_router)
