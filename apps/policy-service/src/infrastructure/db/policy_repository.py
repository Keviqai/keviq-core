"""Policy repository — database access for policy_core tables."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SCHEMA = 'policy_core'

_MAX_LIMIT = 200


def find_policies_by_workspace(
    db: Session, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    rows = db.execute(
        text(f"""
            SELECT id, workspace_id, name, scope, rules, is_default, created_at, updated_at
            FROM {SCHEMA}.workspace_policies
            WHERE workspace_id = :workspace_id
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
        """),
        {'workspace_id': str(workspace_id), 'limit': limit, 'offset': offset},
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def find_policy_by_id(db: Session, policy_id: uuid.UUID) -> dict | None:
    row = db.execute(
        text(f"""
            SELECT id, workspace_id, name, scope, rules, is_default, created_at, updated_at
            FROM {SCHEMA}.workspace_policies
            WHERE id = :id
        """),
        {'id': str(policy_id)},
    ).fetchone()
    return _row_to_dict(row) if row else None


def insert_policy(db: Session, policy: dict) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.workspace_policies
                (id, workspace_id, name, scope, rules, is_default, created_at, updated_at)
            VALUES
                (:id, :workspace_id, :name, :scope, :rules, :is_default, :created_at, :updated_at)
            RETURNING id, workspace_id, name, scope, rules, is_default, created_at, updated_at
        """),
        {
            'id': str(policy['id']),
            'workspace_id': str(policy['workspace_id']),
            'name': policy['name'],
            'scope': policy['scope'],
            'rules': json.dumps(policy['rules']),
            'is_default': policy['is_default'],
            'created_at': policy['created_at'],
            'updated_at': policy['updated_at'],
        },
    ).fetchone()
    db.commit()
    return _row_to_dict(row)


def update_policy(db: Session, policy_id: uuid.UUID, updates: dict) -> dict | None:
    now = datetime.now(timezone.utc)
    set_clauses = ['updated_at = :updated_at']
    params: dict = {'id': str(policy_id), 'updated_at': now}

    if 'name' in updates:
        set_clauses.append('name = :name')
        params['name'] = updates['name']
    if 'rules' in updates:
        set_clauses.append('rules = :rules')
        params['rules'] = json.dumps(updates['rules'])
    if 'scope' in updates:
        set_clauses.append('scope = :scope')
        params['scope'] = updates['scope']

    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspace_policies
            SET {', '.join(set_clauses)}
            WHERE id = :id
            RETURNING id, workspace_id, name, scope, rules, is_default, created_at, updated_at
        """),
        params,
    ).fetchone()
    db.commit()
    return _row_to_dict(row) if row else None


def log_permission_decision(
    db: Session,
    actor_id: uuid.UUID,
    workspace_id: uuid.UUID,
    permission: str,
    decision: str,
    reason: str | None = None,
    resource_id: str | None = None,
) -> None:
    db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.permission_audit_log
                (actor_id, workspace_id, permission, resource_id, decision, reason)
            VALUES
                (:actor_id, :workspace_id, :permission, :resource_id, :decision, :reason)
        """),
        {
            'actor_id': str(actor_id),
            'workspace_id': str(workspace_id),
            'permission': permission,
            'resource_id': resource_id,
            'decision': decision,
            'reason': reason,
        },
    )
    db.commit()


def _row_to_dict(row) -> dict:
    rules = row.rules
    if isinstance(rules, str):
        rules = json.loads(rules)
    return {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'name': row.name,
        'scope': row.scope,
        'rules': rules,
        'is_default': row.is_default,
        'created_at': row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
        'updated_at': row.updated_at.isoformat() if hasattr(row.updated_at, 'isoformat') else str(row.updated_at),
    }


from src.application.ports import PolicyRepository as PolicyRepositoryPort


class PolicyRepositoryAdapter(PolicyRepositoryPort):
    """Infrastructure adapter implementing PolicyRepository port."""

    def find_policies_by_workspace(self, db, workspace_id, *, limit=50, offset=0):
        return find_policies_by_workspace(db, workspace_id, limit=limit, offset=offset)

    def find_policy_by_id(self, db, policy_id):
        return find_policy_by_id(db, policy_id)

    def insert_policy(self, db, policy):
        return insert_policy(db, policy)

    def update_policy(self, db, policy_id, updates):
        return update_policy(db, policy_id, updates)

    def log_permission_decision(self, db, *, actor_id, workspace_id, permission, decision, reason=None, resource_id=None):
        return log_permission_decision(db, actor_id=actor_id, workspace_id=workspace_id, permission=permission, decision=decision, reason=reason, resource_id=resource_id)
