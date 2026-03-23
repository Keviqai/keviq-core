"""Permission domain — role-to-permission matrix and resolution logic."""

from __future__ import annotations

ROLE_PERMISSIONS: dict[str, set[str]] = {
    'owner': {
        'workspace:view',
        'workspace:manage_members',
        'workspace:manage_policy',
        'workspace:manage_secrets',
        'workspace:manage_integrations',
        'workspace:delete',
        'task:create',
        'task:view',
        'task:cancel',
        'run:view',
        'run:terminal',
        'approval:decide',
        'artifact:create',
    },
    'admin': {
        'workspace:view',
        'workspace:manage_members',
        'workspace:manage_policy',
        'workspace:manage_secrets',
        'workspace:manage_integrations',
        'task:create',
        'task:view',
        'task:cancel',
        'run:view',
        'run:terminal',
        'approval:decide',
        'artifact:create',
    },
    'editor': {
        'workspace:view',
        'task:create',
        'task:view',
        'task:cancel',  # own tasks only — enforced at application layer
        'run:view',
        'artifact:create',
    },
    'viewer': {
        'workspace:view',
        'task:view',
        'run:view',
    },
}

ALL_PERMISSIONS = sorted({p for perms in ROLE_PERMISSIONS.values() for p in perms})


def role_has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def resolve_permission(
    role: str,
    permission: str,
    workspace_policy_rules: list[dict] | None = None,
) -> tuple[bool, str]:
    """Resolve permission following the 6-step order from the contract.

    Returns (allowed, reason).

    Resolution order:
    1. System Global Deny (hardcoded)
    2. Workspace Policy deny rules
    3. Task Override deny (N/A Slice 1)
    4. Workspace Policy allow rules
    5. Task Override allow (N/A Slice 1)
    6. Role-based permission (Member.role → permission matrix)

    Deny wins at same level.
    """
    # Step 1: System global deny — none defined yet
    # Step 2: Workspace policy deny rules
    if workspace_policy_rules:
        for rule in workspace_policy_rules:
            if rule.get('effect') == 'deny' and rule.get('permission') == permission:
                return False, f"policy:deny rule matches {permission}"

    # Step 3: Task override deny (N/A Slice 1)
    # Step 4: Workspace policy allow rules
    if workspace_policy_rules:
        for rule in workspace_policy_rules:
            if rule.get('effect') == 'allow' and rule.get('permission') == permission:
                return True, f"policy:allow rule matches {permission}"

    # Step 5: Task override allow (N/A Slice 1)
    # Step 6: Role-based permission
    if role_has_permission(role, permission):
        return True, f"role:{role} grants {permission}"

    return False, f"role:{role} does not grant {permission}"
