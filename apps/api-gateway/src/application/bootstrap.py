"""Application bootstrap — dependency provider for api-gateway.

Infrastructure configures the providers at startup.
Application/API layer calls get_*() without importing infrastructure.
"""
from __future__ import annotations

from .ports import JwtVerifier, PolicyClient, ServiceProxy, WorkspaceClient

_jwt_verifier: JwtVerifier | None = None
_policy_client: PolicyClient | None = None
_workspace_client: WorkspaceClient | None = None
_service_proxy: ServiceProxy | None = None
_configured = False


def configure_gateway_deps(
    *,
    jwt_verifier: JwtVerifier,
    policy_client: PolicyClient,
    workspace_client: WorkspaceClient,
    service_proxy: ServiceProxy,
) -> None:
    global _jwt_verifier, _policy_client, _workspace_client, _service_proxy, _configured
    if _configured:
        raise RuntimeError("Gateway dependencies already configured")
    _jwt_verifier = jwt_verifier
    _policy_client = policy_client
    _workspace_client = workspace_client
    _service_proxy = service_proxy
    _configured = True


def get_jwt_verifier() -> JwtVerifier:
    if _jwt_verifier is None:
        raise RuntimeError("JWT verifier not configured — call configure_gateway_deps() at startup")
    return _jwt_verifier


def get_policy_client() -> PolicyClient:
    if _policy_client is None:
        raise RuntimeError("Policy client not configured — call configure_gateway_deps() at startup")
    return _policy_client


def get_workspace_client() -> WorkspaceClient:
    if _workspace_client is None:
        raise RuntimeError("Workspace client not configured — call configure_gateway_deps() at startup")
    return _workspace_client


def get_service_proxy() -> ServiceProxy:
    if _service_proxy is None:
        raise RuntimeError("Service proxy not configured — call configure_gateway_deps() at startup")
    return _service_proxy
