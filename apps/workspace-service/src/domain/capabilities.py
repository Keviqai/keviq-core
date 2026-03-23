"""Server-derived capabilities per role.

Capabilities are resolved from the user's role in a workspace.
This is the authoritative source — frontend must NOT derive capabilities from role.
Policy overrides (deny/allow rules) are applied at the gateway/policy-service level.
"""

from __future__ import annotations

# Base capabilities per role (mirrors policy-service ROLE_PERMISSIONS)
ROLE_CAPABILITIES: dict[str, list[str]] = {
    'owner': [
        'workspace:view',
        'workspace:manage_members',
        'workspace:manage_policy',
        'workspace:manage_secrets',
        'workspace:manage_integrations',
        'workspace:delete',
        'task:create',
        'task:view',
        'task:cancel',
    ],
    'admin': [
        'workspace:view',
        'workspace:manage_members',
        'workspace:manage_policy',
        'workspace:manage_secrets',
        'workspace:manage_integrations',
        'task:create',
        'task:view',
        'task:cancel',
    ],
    'editor': [
        'workspace:view',
        'task:create',
        'task:view',
        'task:cancel',
    ],
    'viewer': [
        'workspace:view',
        'task:view',
    ],
}


def resolve_capabilities(role: str) -> list[str]:
    """Return the list of capabilities for a given role."""
    return list(ROLE_CAPABILITIES.get(role, []))
