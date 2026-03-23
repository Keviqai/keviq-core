"""API Gateway post-fetch authorization — response-level permission checks."""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException, Response, status

from src.application.auth_middleware import check_permission_or_fail, has_permission
from src.api.permissions import inject_task_capabilities, inject_run_capabilities

logger = logging.getLogger(__name__)


async def post_fetch_authz(
    user_id: str,
    path: str,
    permission: str,
    response: Response,
) -> Response:
    """Post-fetch authorization: extract workspace_id from response, check permission.

    If unauthorized, return 403 without leaking resource data.
    If authorized and GET, inject _capabilities based on actual permissions.
    """
    try:
        data = json.loads(response.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response

    # Extract workspace_id from response body
    ws_id = data.get('workspace_id')
    if not ws_id:
        logger.warning(
            "Post-fetch authz: no workspace_id in response for %s", path,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Permission check unavailable — access denied',
        )

    # Check the required permission
    await check_permission_or_fail(user_id, ws_id, permission)

    # If we get here, the user is authorized. Inject capabilities for GET responses.
    parts = path.rstrip('/').split('/')

    # GET /v1/tasks/{task_id} -> inject task capabilities with actual cancel/retry perm
    if len(parts) == 4 and parts[2] == 'tasks':
        cancel_perm = await has_permission(user_id, ws_id, 'task:cancel')
        retry_perm = await has_permission(user_id, ws_id, 'task:create')
        inject_task_capabilities(data, has_cancel_perm=cancel_perm, has_retry_perm=retry_perm)
        return _build_json_response(data, response)

    # GET /v1/runs/{run_id} -> inject run capabilities
    if len(parts) == 4 and parts[2] == 'runs':
        inject_run_capabilities(data)
        return _build_json_response(data, response)

    return response


async def post_fetch_authz_timeline(
    user_id: str,
    permission: str,
    response: Response,
) -> Response:
    """Post-fetch authorization for timeline responses.

    Timeline responses contain events with workspace_id.
    Check permission using the first event's workspace_id.
    """
    try:
        data = json.loads(response.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response

    # Use workspace_id from response (set by event-store from query scope)
    ws_id = data.get('workspace_id')
    if not ws_id:
        # Fallback: extract from first event
        events = data.get('events', [])
        if not events:
            return response
        ws_id = events[0].get('workspace_id')
    if not ws_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Permission check unavailable — access denied',
        )

    await check_permission_or_fail(user_id, ws_id, permission)
    return response


def _build_json_response(data: dict, original: Response) -> Response:
    """Build a new JSON response with updated data, preserving status and headers."""
    new_content = json.dumps(data)
    resp_headers = {
        k: v for k, v in original.headers.items()
        if k.lower() != 'content-length'
    }
    return Response(
        content=new_content,
        status_code=original.status_code,
        headers=resp_headers,
        media_type='application/json',
    )
