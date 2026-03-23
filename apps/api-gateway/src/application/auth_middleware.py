"""Authentication and permission middleware for api-gateway."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from .bootstrap import get_jwt_verifier, get_policy_client, get_workspace_client

logger = logging.getLogger(__name__)

# Routes that don't require authentication
PUBLIC_ROUTES = {
    '/v1/auth/register',
    '/v1/auth/login',
    '/healthz/live',
    '/healthz/ready',
}

# Routes that require auth but no specific permission
AUTH_ONLY_ROUTES = {
    '/v1/auth/refresh',
    '/v1/auth/me',
    '/v1/workspaces',
    '/v1/tasks',
}

# Permission map: (method, path_pattern) → permission
PERMISSION_MAP = {
    ('GET', '/v1/workspaces/{workspace_id}'): 'workspace:view',
    ('PATCH', '/v1/workspaces/{workspace_id}'): 'workspace:manage_members',
    ('DELETE', '/v1/workspaces/{workspace_id}'): 'workspace:delete',
    ('GET', '/v1/workspaces/{workspace_id}/members'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/members'): 'workspace:manage_members',
    ('PATCH', '/v1/workspaces/{workspace_id}/members/{member_user_id}'): 'workspace:manage_members',
    ('DELETE', '/v1/workspaces/{workspace_id}/members/{member_user_id}'): 'workspace:manage_members',
    ('GET', '/v1/workspaces/{workspace_id}/policies'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/policies'): 'workspace:manage_policy',
    ('GET', '/v1/workspaces/{workspace_id}/policies/{policy_id}'): 'workspace:view',
    ('PATCH', '/v1/workspaces/{workspace_id}/policies/{policy_id}'): 'workspace:manage_policy',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/preview'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/download'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/provenance'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/lineage/ancestors'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/runs/{run_id}/artifacts'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/artifacts/upload'): 'artifact:create',
    ('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/annotations'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/annotations'): 'workspace:view',
    # Secrets (secret-broker)
    ('GET', '/v1/workspaces/{workspace_id}/secrets'): 'workspace:manage_secrets',
    ('POST', '/v1/workspaces/{workspace_id}/secrets'): 'workspace:manage_secrets',
    ('DELETE', '/v1/workspaces/{workspace_id}/secrets/{secret_id}'): 'workspace:manage_secrets',
    ('PATCH', '/v1/workspaces/{workspace_id}/secrets/{secret_id}'): 'workspace:manage_secrets',
    # Activity (event-store)
    ('GET', '/v1/workspaces/{workspace_id}/activity'): 'workspace:view',
    # Notifications (notification-service)
    ('GET', '/v1/workspaces/{workspace_id}/notifications'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/notifications/count'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/notifications/{notification_id}/read'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/notifications/read-all'): 'workspace:view',
    # Integrations (model-gateway)
    ('GET', '/v1/workspaces/{workspace_id}/integrations'): 'workspace:manage_integrations',
    ('POST', '/v1/workspaces/{workspace_id}/integrations'): 'workspace:manage_integrations',
    ('GET', '/v1/workspaces/{workspace_id}/integrations/{integration_id}'): 'workspace:manage_integrations',
    ('PATCH', '/v1/workspaces/{workspace_id}/integrations/{integration_id}'): 'workspace:manage_integrations',
    ('DELETE', '/v1/workspaces/{workspace_id}/integrations/{integration_id}'): 'workspace:manage_integrations',
    ('POST', '/v1/workspaces/{workspace_id}/integrations/{integration_id}/toggle'): 'workspace:manage_integrations',
    # Audit (audit-service)
    ('GET', '/v1/workspaces/{workspace_id}/audit-events'): 'workspace:view',
    # Approvals (orchestrator)
    ('GET', '/v1/workspaces/{workspace_id}/approvals'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/approvals/count'): 'workspace:view',
    ('GET', '/v1/workspaces/{workspace_id}/approvals/{id}'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/approvals'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/approvals/{id}/decide'): 'approval:decide',
    # Task comments (P6-S2)
    ('GET', '/v1/workspaces/{workspace_id}/tasks/{id}/comments'): 'workspace:view',
    ('POST', '/v1/workspaces/{workspace_id}/tasks/{id}/comments'): 'workspace:view',
    # Task runs
    ('GET', '/v1/workspaces/{workspace_id}/tasks/{id}/runs'): 'workspace:view',
}


def _is_sse_endpoint(path: str) -> bool:
    """Check if the path is an SSE streaming endpoint."""
    return path.rstrip('/').endswith('/events/stream')


def extract_auth_context(request: Request) -> dict | None:
    """Extract and verify JWT from Authorization header or query param.

    SSE endpoints (EventSource) cannot send custom headers, so we also
    accept a ``token`` query parameter for paths ending in /events/stream.
    Returns payload dict or None for public routes.
    """
    path = request.url.path

    if path in PUBLIC_ROUTES:
        return None

    auth_header = request.headers.get('authorization', '')
    token: str | None = None

    if auth_header.startswith('Bearer '):
        token = auth_header[len('Bearer '):]
    elif _is_sse_endpoint(path):
        token = request.query_params.get('token')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or invalid Authorization header',
        )

    try:
        return get_jwt_verifier().verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired token',
        )


def match_permission(method: str, path: str) -> tuple[str | None, str | None]:
    """Match request to a permission and extract workspace_id.
    Returns (permission, workspace_id) or (None, None) for auth-only routes."""
    parts = path.rstrip('/').split('/')

    if path.rstrip('/') in AUTH_ONLY_ROUTES:
        return None, None

    if len(parts) >= 3 and parts[1] == 'v1' and parts[2] in ('tasks', 'runs', 'tool-executions', 'sandboxes', 'telemetry'):
        return None, None

    if len(parts) >= 4 and parts[1] == 'v1' and parts[2] == 'workspaces':
        workspace_id = parts[3]

        _ID_PLACEHOLDER = {
            'members': '{member_user_id}',
            'policies': '{policy_id}',
            'artifacts': '{artifact_id}',
            'runs': '{run_id}',
            'secrets': '{secret_id}',
            'notifications': '{notification_id}',
            'integrations': '{integration_id}',
        }

        if len(parts) == 4:
            pattern = '/v1/workspaces/{workspace_id}'
        elif len(parts) == 5:
            pattern = f'/v1/workspaces/{{workspace_id}}/{parts[4]}'
        elif len(parts) == 6:
            # Check if parts[5] is a known action literal (e.g., 'upload')
            _ACTION_LITERALS = {'upload', 'count', 'read-all'}
            if parts[5] in _ACTION_LITERALS:
                pattern = f'/v1/workspaces/{{workspace_id}}/{parts[4]}/{parts[5]}'
            else:
                placeholder = _ID_PLACEHOLDER.get(parts[4], '{id}')
                pattern = f'/v1/workspaces/{{workspace_id}}/{parts[4]}/{placeholder}'
        elif len(parts) == 7:
            placeholder_4 = _ID_PLACEHOLDER.get(parts[4], '{id}')
            pattern = (f'/v1/workspaces/{{workspace_id}}/{parts[4]}'
                       f'/{placeholder_4}/{parts[6]}')
        elif len(parts) == 8:
            placeholder_4 = _ID_PLACEHOLDER.get(parts[4], '{id}')
            pattern = (f'/v1/workspaces/{{workspace_id}}/{parts[4]}'
                       f'/{placeholder_4}/{parts[6]}/{parts[7]}')
        else:
            return None, None

        perm = PERMISSION_MAP.get((method, pattern))
        if perm:
            return perm, workspace_id
        return None, None

    return None, None


async def check_permission_or_fail(
    user_id: str,
    workspace_id: str,
    permission: str,
) -> None:
    """Check permission via policy-service. Fail-closed on any error."""
    try:
        member = await get_workspace_client().get_member(workspace_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Not a member of this workspace',
            )
        role = member['role']

        result = await get_policy_client().check_permission(
            actor_id=user_id,
            workspace_id=workspace_id,
            permission=permission,
            role=role,
        )
        if not result.get('allowed'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.get('reason', 'Permission denied'),
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error('Permission check failed (fail-closed): %s', exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Permission check unavailable — access denied',
        )


async def has_permission(
    user_id: str,
    workspace_id: str,
    permission: str,
) -> bool:
    """Non-throwing permission check. Returns True if allowed, False otherwise."""
    try:
        member = await get_workspace_client().get_member(workspace_id, user_id)
        if not member:
            return False
        role = member['role']

        result = await get_policy_client().check_permission(
            actor_id=user_id,
            workspace_id=workspace_id,
            permission=permission,
            role=role,
        )
        return bool(result.get('allowed'))
    except Exception as exc:
        logger.error('has_permission check failed (fail-closed): %s', exc)
        return False
