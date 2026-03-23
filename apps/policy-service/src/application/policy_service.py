"""Policy application service — permission checking and policy CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.domain.permissions import resolve_permission
from src.domain.policy_errors import PolicyNotFound

from .bootstrap import get_policy_repo


def check_permission(
    db,
    actor_id: uuid.UUID,
    workspace_id: uuid.UUID,
    permission: str,
    role: str,
    resource_id: str | None = None,
) -> dict:
    """Check if actor has permission in workspace. Logs the decision."""
    policy_repo = get_policy_repo()

    policies = policy_repo.find_policies_by_workspace(db, workspace_id)

    all_rules: list[dict] = []
    for policy in policies:
        all_rules.extend(policy.get('rules', []))

    allowed, reason = resolve_permission(role, permission, all_rules)
    decision = 'allowed' if allowed else 'denied'

    policy_repo.log_permission_decision(
        db,
        actor_id=actor_id,
        workspace_id=workspace_id,
        permission=permission,
        decision=decision,
        reason=reason,
        resource_id=resource_id,
    )

    return {'allowed': allowed, 'reason': reason}


def list_policies(db, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> list[dict]:
    return get_policy_repo().find_policies_by_workspace(db, workspace_id, limit=limit, offset=offset)


def get_policy(db, policy_id: uuid.UUID) -> dict:
    policy = get_policy_repo().find_policy_by_id(db, policy_id)
    if not policy:
        raise PolicyNotFound(str(policy_id))
    return policy


def create_policy(
    db,
    workspace_id: uuid.UUID,
    name: str,
    scope: str = 'workspace',
    rules: list | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    policy = {
        'id': uuid.uuid4(),
        'workspace_id': workspace_id,
        'name': name,
        'scope': scope,
        'rules': rules or [],
        'is_default': False,
        'created_at': now,
        'updated_at': now,
    }
    return get_policy_repo().insert_policy(db, policy)


def update_policy(db, policy_id: uuid.UUID, updates: dict) -> dict:
    result = get_policy_repo().update_policy(db, policy_id, updates)
    if not result:
        raise PolicyNotFound(str(policy_id))
    return result
