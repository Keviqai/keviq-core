import os

from fastapi import FastAPI
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry
from src.api.routes import router

configure_logging("telemetry-service")

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(**({} if _app_env == "development" else _docs_off))
app.add_middleware(RequestIdMiddleware)

_metrics = MetricsRegistry(service="telemetry-service")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

app.include_router(router)
