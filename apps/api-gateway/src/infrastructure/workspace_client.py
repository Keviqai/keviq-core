"""HTTP client for workspace-service — used to resolve member role."""

from __future__ import annotations

import os

import httpx

WORKSPACE_SERVICE_URL = os.getenv('WORKSPACE_SERVICE_URL', 'http://workspace-service:8000')
TIMEOUT = float(os.getenv('WORKSPACE_CLIENT_TIMEOUT', '5.0'))

# Shared async client for connection reuse
_client = httpx.AsyncClient(
    base_url=WORKSPACE_SERVICE_URL,
    timeout=TIMEOUT,
)


async def get_member(workspace_id: str, user_id: str) -> dict | None:
    """Get member info from workspace-service. Returns member dict or None."""
    resp = await _client.get(
        f'/v1/workspaces/{workspace_id}/members',
        headers={'X-User-Id': user_id},
    )
    if resp.status_code != 200:
        return None
    members = resp.json()
    for m in members:
        if m.get('user_id') == user_id:
            return m
    return None


from src.application.ports import WorkspaceClient as WorkspaceClientPort


class WorkspaceClientAdapter(WorkspaceClientPort):
    """Infrastructure adapter implementing WorkspaceClient port."""

    async def get_member(self, workspace_id, user_id):
        return await get_member(workspace_id, user_id)
