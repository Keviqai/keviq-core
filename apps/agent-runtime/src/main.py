import src.resilience_bridge  # noqa: F401 — adds resilience package to sys.path

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry
from src.internal_auth import bootstrap_internal_auth

logger = logging.getLogger(__name__)

configure_logging("agent-runtime")

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="agent-runtime")

# ── App ──────────────────────────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Shutdown: close HTTP clients held by the handler singleton
    import src.api.routes as _routes

    svc = _routes._service
    if svc is not None:
        for attr in ("gateway", "artifact_service"):
            client = getattr(svc, attr, None)
            if client is not None and hasattr(client, "close"):
                try:
                    client.close()
                except Exception as exc:
                    logger.warning("Failed to close %s client: %s", attr, exc)


app = FastAPI(
    lifespan=_lifespan,
    **({} if _app_env == "development" else _docs_off),
)
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="agent-runtime")
app.add_middleware(MetricsMiddleware, registry=_metrics)

# O8-S2: Register domain-specific operational counters
from src.application.runtime_metrics import setup_runtime_metrics  # noqa: E402
setup_runtime_metrics(_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
