"""API Gateway routes — proxy with auth + permission enforcement."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from src.application.auth_middleware import (
    check_permission_or_fail,
    extract_auth_context,
    match_permission,
)
from src.application.proxy import forward_to_service
from src.api.rate_limit import limiter
from src.api.routing import (
    artifact_query_params,
    rewrite_internal_path,
    route_to_service,
)
from src.api.permissions import (
    resolve_event_store_permission,
    resolve_orchestrator_permission,
)
from src.api.post_fetch import post_fetch_authz, post_fetch_authz_timeline

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info() -> dict[str, str]:
    import os
    info: dict = {"service": "api-gateway"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


# ── Rate-limited auth routes ──────────────────────────────────
# These specific routes match before the catch-all gateway_proxy.


@router.post("/v1/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request):
    """Rate-limited proxy for login."""
    return await forward_to_service('auth', '/v1/auth/login', request)


@router.post("/v1/auth/register")
@limiter.limit("5/minute")
async def auth_register(request: Request):
    """Rate-limited proxy for registration."""
    return await forward_to_service('auth', '/v1/auth/register', request)


@router.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
)
async def gateway_proxy(request: Request, path: str) -> Response:
    full_path = f'/v1/{path}'

    # Step 1: Authentication
    auth_ctx = extract_auth_context(request)
    user_id = auth_ctx.get('sub') if auth_ctx else None

    # If authenticated but JWT has no 'sub' claim, reject
    if auth_ctx and not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token missing sub claim',
        )

    # Step 2: Pre-proxy permission check (for routes where workspace_id is known)
    permission, workspace_id = match_permission(request.method, full_path)

    # For POST /v1/tasks or /v1/tasks/draft, workspace_id is in the request body
    if request.method == 'POST' and full_path.rstrip('/') in ('/v1/tasks', '/v1/tasks/draft'):
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )
        try:
            body = await request.body()
            body_json = json.loads(body) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON body',
            )
        ws_id = body_json.get('workspace_id')
        if not ws_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='workspace_id is required',
            )
        await check_permission_or_fail(user_id, ws_id, 'task:create')
    elif request.method == 'GET' and full_path.rstrip('/') == '/v1/tasks':
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )
        ws_id = request.query_params.get('workspace_id')
        if not ws_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='workspace_id query parameter is required',
            )
        await check_permission_or_fail(user_id, ws_id, 'task:view')
    elif permission and workspace_id:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )
        await check_permission_or_fail(user_id, workspace_id, permission)

    # Terminal session routes require authentication
    if full_path.startswith('/v1/terminal/'):
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )
        # POST /v1/terminal/sessions -> needs workspace_id from body for perm check
        if request.method == 'POST' and full_path.rstrip('/') == '/v1/terminal/sessions':
            try:
                body = await request.body()
                body_json = json.loads(body) if body else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Invalid JSON body',
                )
            ws_id = body_json.get('workspace_id')
            if not ws_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='workspace_id is required',
                )
            await check_permission_or_fail(user_id, ws_id, 'run:terminal')

    # O7: Tool execution + sandbox detail routes require auth
    if full_path.startswith('/v1/tool-executions/') or full_path.startswith('/v1/sandboxes/'):
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )

    # Step 3: Route to backend service
    service = route_to_service(full_path)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Unknown API path',
        )

    # Artifact routes: GET for queries, POST only for upload or annotations.
    if service == 'artifact' and request.method != 'GET':
        is_upload = request.method == 'POST' and '/artifacts/upload' in full_path
        is_annotation = request.method == 'POST' and full_path.rstrip('/').endswith('/annotations')
        if not (is_upload or is_annotation):
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail='Artifact routes only support GET (except upload)',
            )

    # Pre-proxy auth for event-store routes (timeline + SSE streams)
    parts = full_path.rstrip('/').split('/')
    if service == 'event-store':
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
            )
        # Workspace events stream has workspace_id in URL
        if (len(parts) == 6 and parts[2] == 'workspaces'
                and parts[4] == 'events' and parts[5] == 'stream'):
            await check_permission_or_fail(user_id, parts[3], 'workspace:view')
        else:
            es_perm = resolve_event_store_permission(request.method, full_path)
            if es_perm:
                # Timeline and run SSE require workspace_id query param
                es_ws_id = request.query_params.get('workspace_id')
                if not es_ws_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='workspace_id query parameter is required',
                    )
                await check_permission_or_fail(user_id, es_ws_id, es_perm)

    extra_headers = {}
    if user_id:
        extra_headers['X-User-Id'] = user_id

    # Rewrite path for internal API
    backend_path = rewrite_internal_path(service, full_path)

    # Artifact routes need workspace_id/run_id extracted from URL into query params
    extra_params = artifact_query_params(full_path) if service == 'artifact' else None

    response = await forward_to_service(
        service, backend_path, request,
        extra_headers=extra_headers,
        extra_params=extra_params,
    )

    # SSE streams are pre-authorized above; skip post-fetch authz
    if backend_path.rstrip('/').endswith('/events/stream'):
        return response

    # Step 4: Post-fetch authorization for orchestrator GET responses.
    if service == 'orchestrator' and response.status_code == 200 and request.method == 'GET':
        orch_perm = resolve_orchestrator_permission(request.method, full_path)
        if orch_perm and user_id:
            response = await post_fetch_authz(
                user_id, full_path, orch_perm, response,
            )

    # Step 5: Post-fetch defense-in-depth for event-store timeline responses
    if service == 'event-store' and response.status_code == 200:
        es_perm = resolve_event_store_permission(request.method, full_path)
        if es_perm and user_id:
            response = await post_fetch_authz_timeline(
                user_id, es_perm, response,
            )

    return response
