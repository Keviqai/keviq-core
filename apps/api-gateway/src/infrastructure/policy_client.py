"""HTTP client for policy-service internal API."""

from __future__ import annotations

import os

import httpx

POLICY_SERVICE_URL = os.getenv('POLICY_SERVICE_URL', 'http://policy-service:8000')
TIMEOUT = float(os.getenv('POLICY_CLIENT_TIMEOUT', '5.0'))

# Shared async client for connection reuse
_client = httpx.AsyncClient(
    base_url=POLICY_SERVICE_URL,
    timeout=TIMEOUT,
)


async def check_permission(
    actor_id: str,
    workspace_id: str,
    permission: str,
    role: str,
    resource_id: str | None = None,
) -> dict:
    """Call policy-service to check permission.
    Returns {'allowed': bool, 'reason': str}.
    Raises on network error (fail-closed at caller)."""
    resp = await _client.post(
        '/internal/v1/check-permission',
        json={
            'actor_id': actor_id,
            'workspace_id': workspace_id,
            'permission': permission,
            'role': role,
            'resource_id': resource_id,
        },
    )
    resp.raise_for_status()
    return resp.json()


from src.application.ports import PolicyClient as PolicyClientPort


class PolicyClientAdapter(PolicyClientPort):
    """Infrastructure adapter implementing PolicyClient port."""

    async def check_permission(self, *, actor_id, workspace_id, permission, role, resource_id=None):
        return await check_permission(actor_id=actor_id, workspace_id=workspace_id, permission=permission, role=role, resource_id=resource_id)
