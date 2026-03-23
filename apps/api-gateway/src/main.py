import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from mona_os_logger import configure_logging, RequestIdMiddleware, MetricsMiddleware, MetricsRegistry

configure_logging("api-gateway")

from src.internal_auth import bootstrap_internal_auth
from src.application.bootstrap import configure_gateway_deps
from src.infrastructure.jwt_verifier import JwtVerifierAdapter
from src.infrastructure.policy_client import PolicyClientAdapter
from src.infrastructure.workspace_client import WorkspaceClientAdapter
from src.infrastructure.service_proxy import ServiceProxyAdapter

# ── Internal auth ────────────────────────────────────────────────
_auth_client = bootstrap_internal_auth(service_name="api-gateway")

# ── Configure infrastructure ────────────────────────────────────
configure_gateway_deps(
    jwt_verifier=JwtVerifierAdapter(),
    policy_client=PolicyClientAdapter(),
    workspace_client=WorkspaceClientAdapter(),
    service_proxy=ServiceProxyAdapter(),
)

# ── App (AFTER bootstrap) ─────────────────────────────────────
from src.api.routes import router  # noqa: E402 — after bootstrap

_app_env = os.getenv("APP_ENV", "development")
_docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="api-gateway",
    version="0.1.0",
    **({} if _app_env == "development" else _docs_off),
)

# CORS for web app
_allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(RequestIdMiddleware)

# O8-S1: Metrics
_metrics = MetricsRegistry(service="api-gateway")
app.add_middleware(MetricsMiddleware, registry=_metrics)


@app.get("/metrics")
def metrics_endpoint():
    return _metrics.prometheus_response()

# Rate limiting — slowapi for auth-route decorators
from src.api.rate_limit import limiter  # noqa: E402

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Tiered rate-limit middleware (applied after CORS, before route handlers)
from src.api.rate_limit_middleware import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)

app.include_router(router)
