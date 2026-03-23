"""Workspace repository — database access for workspace_core tables."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SCHEMA = 'workspace_core'

_WS_COLS = 'id, slug, display_name, plan, deployment_mode, owner_id, created_at, updated_at, settings'
_MEM_COLS = 'id, workspace_id, user_id, role, joined_at, updated_at, invited_by_id'


# ── Workspaces ─────────────────────────────────────────────────────

def find_workspace_by_id(db: Session, workspace_id: uuid.UUID) -> dict | None:
    row = db.execute(
        text(f'SELECT {_WS_COLS} FROM {SCHEMA}.workspaces WHERE id = :id'),
        {'id': str(workspace_id)},
    ).fetchone()
    return _ws_to_dict(row) if row else None


def find_workspace_by_slug(db: Session, slug: str) -> dict | None:
    row = db.execute(
        text(f'SELECT {_WS_COLS} FROM {SCHEMA}.workspaces WHERE slug = :slug'),
        {'slug': slug},
    ).fetchone()
    return _ws_to_dict(row) if row else None


_MAX_LIMIT = 200


def find_workspaces_by_user(
    db: Session, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    """Return workspaces the user belongs to, with their role included."""
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    rows = db.execute(
        text(f"""
            SELECT {'w.' + _WS_COLS.replace(', ', ', w.')}, m.role AS member_role
            FROM {SCHEMA}.workspaces w
            JOIN {SCHEMA}.members m ON m.workspace_id = w.id
            WHERE m.user_id = :user_id
            ORDER BY w.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {'user_id': str(user_id), 'limit': limit, 'offset': offset},
    ).fetchall()
    result = []
    for r in rows:
        ws = _ws_to_dict(r)
        ws['_member_role'] = r.member_role
        result.append(ws)
    return result


def insert_workspace(db: Session, ws: dict) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.workspaces
                (id, slug, display_name, plan, deployment_mode, owner_id, created_at, updated_at, settings)
            VALUES
                (:id, :slug, :display_name, :plan, :deployment_mode, :owner_id, :created_at, :updated_at, :settings)
            RETURNING {_WS_COLS}
        """),
        {
            'id': str(ws['id']),
            'slug': ws['slug'],
            'display_name': ws['display_name'],
            'plan': ws['plan'],
            'deployment_mode': ws['deployment_mode'],
            'owner_id': str(ws['owner_id']),
            'created_at': ws['created_at'],
            'updated_at': ws['updated_at'],
            'settings': json.dumps(ws['settings']),
        },
    ).fetchone()

    return _ws_to_dict(row)


def update_workspace(db: Session, workspace_id: uuid.UUID, updates: dict) -> dict | None:
    now = datetime.now(timezone.utc)
    set_clauses = ['updated_at = :updated_at']
    params: dict = {'id': str(workspace_id), 'updated_at': now}

    for field in ('display_name', 'plan', 'deployment_mode'):
        if field in updates:
            set_clauses.append(f'{field} = :{field}')
            params[field] = updates[field]
    if 'settings' in updates:
        set_clauses.append('settings = :settings')
        params['settings'] = json.dumps(updates['settings'])

    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspaces SET {', '.join(set_clauses)}
            WHERE id = :id RETURNING {_WS_COLS}
        """),
        params,
    ).fetchone()

    return _ws_to_dict(row) if row else None


def delete_workspace(db: Session, workspace_id: uuid.UUID) -> bool:
    result = db.execute(
        text(f'DELETE FROM {SCHEMA}.workspaces WHERE id = :id'),
        {'id': str(workspace_id)},
    )

    return result.rowcount > 0


# ── Members ────────────────────────────────────────────────────────

def find_members_by_workspace(
    db: Session, workspace_id: uuid.UUID, *, limit: int = 200, offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    rows = db.execute(
        text(f"""
            SELECT {_MEM_COLS} FROM {SCHEMA}.members
            WHERE workspace_id = :workspace_id
            ORDER BY joined_at ASC
            LIMIT :limit OFFSET :offset
        """),
        {'workspace_id': str(workspace_id), 'limit': limit, 'offset': offset},
    ).fetchall()
    return [_mem_to_dict(r) for r in rows]


def find_member(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> dict | None:
    row = db.execute(
        text(f'SELECT {_MEM_COLS} FROM {SCHEMA}.members WHERE workspace_id = :workspace_id AND user_id = :user_id'),
        {'workspace_id': str(workspace_id), 'user_id': str(user_id)},
    ).fetchone()
    return _mem_to_dict(row) if row else None


def insert_member(db: Session, mem: dict) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.members
                (id, workspace_id, user_id, role, joined_at, updated_at, invited_by_id)
            VALUES
                (:id, :workspace_id, :user_id, :role, :joined_at, :updated_at, :invited_by_id)
            RETURNING {_MEM_COLS}
        """),
        {
            'id': str(mem['id']),
            'workspace_id': str(mem['workspace_id']),
            'user_id': str(mem['user_id']),
            'role': mem['role'],
            'joined_at': mem['joined_at'],
            'updated_at': mem['updated_at'],
            'invited_by_id': str(mem['invited_by_id']) if mem.get('invited_by_id') else None,
        },
    ).fetchone()

    return _mem_to_dict(row)


def update_member_role(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str) -> dict | None:
    now = datetime.now(timezone.utc)
    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.members SET role = :role, updated_at = :updated_at
            WHERE workspace_id = :workspace_id AND user_id = :user_id
            RETURNING {_MEM_COLS}
        """),
        {'workspace_id': str(workspace_id), 'user_id': str(user_id), 'role': role, 'updated_at': now},
    ).fetchone()

    return _mem_to_dict(row) if row else None


def delete_member(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = db.execute(
        text(f'DELETE FROM {SCHEMA}.members WHERE workspace_id = :workspace_id AND user_id = :user_id'),
        {'workspace_id': str(workspace_id), 'user_id': str(user_id)},
    )

    return result.rowcount > 0


# ── Helpers ────────────────────────────────────────────────────────

def _ws_to_dict(row) -> dict:
    settings = row.settings
    if isinstance(settings, str):
        settings = json.loads(settings)
    return {
        'id': str(row.id),
        'slug': row.slug,
        'display_name': row.display_name,
        'plan': row.plan,
        'deployment_mode': row.deployment_mode,
        'owner_id': str(row.owner_id),
        'created_at': row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
        'updated_at': row.updated_at.isoformat() if hasattr(row.updated_at, 'isoformat') else str(row.updated_at),
        'settings': settings,
    }


def _mem_to_dict(row) -> dict:
    return {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'user_id': str(row.user_id),
        'role': row.role,
        'joined_at': row.joined_at.isoformat() if hasattr(row.joined_at, 'isoformat') else str(row.joined_at),
        'updated_at': row.updated_at.isoformat() if hasattr(row.updated_at, 'isoformat') else str(row.updated_at),
        'invited_by_id': str(row.invited_by_id) if row.invited_by_id else None,
    }


from src.application.ports import WorkspaceRepository as WorkspaceRepositoryPort


class WorkspaceRepositoryAdapter(WorkspaceRepositoryPort):
    """Infrastructure adapter implementing WorkspaceRepository port."""

    def find_workspace_by_id(self, db, workspace_id):
        return find_workspace_by_id(db, workspace_id)

    def find_workspace_by_slug(self, db, slug):
        return find_workspace_by_slug(db, slug)

    def find_workspaces_by_user(self, db, user_id, *, limit=50, offset=0):
        return find_workspaces_by_user(db, user_id, limit=limit, offset=offset)

    def insert_workspace(self, db, ws):
        return insert_workspace(db, ws)

    def update_workspace(self, db, workspace_id, updates):
        return update_workspace(db, workspace_id, updates)

    def delete_workspace(self, db, workspace_id):
        return delete_workspace(db, workspace_id)

    def find_members_by_workspace(self, db, workspace_id, *, limit=200, offset=0):
        return find_members_by_workspace(db, workspace_id, limit=limit, offset=offset)

    def find_member(self, db, workspace_id, user_id):
        return find_member(db, workspace_id, user_id)

    def insert_member(self, db, mem):
        return insert_member(db, mem)

    def update_member_role(self, db, workspace_id, user_id, role):
        return update_member_role(db, workspace_id, user_id, role)

    def delete_member(self, db, workspace_id, user_id):
        return delete_member(db, workspace_id, user_id)
