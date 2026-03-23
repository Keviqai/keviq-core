"""Secret repository — database access for secret_core tables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SCHEMA = 'secret_core'

_MAX_LIMIT = 200

# Metadata columns — NEVER includes secret_ciphertext or secret_hash
_SELECT_COLS = (
    'id, workspace_id, name, description, secret_type, '
    'masked_display, created_by_id, created_at, updated_at'
)

# Raw columns — includes ciphertext for internal decrypt
_RAW_SELECT_COLS = (
    'id, workspace_id, secret_ciphertext, encryption_key_version'
)


def find_by_workspace(
    db: Session, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    rows = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.workspace_secrets
            WHERE workspace_id = :workspace_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {'workspace_id': str(workspace_id), 'limit': limit, 'offset': offset},
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def find_by_id(db: Session, secret_id: uuid.UUID) -> dict | None:
    row = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.workspace_secrets
            WHERE id = :id
        """),
        {'id': str(secret_id)},
    ).fetchone()
    return _row_to_dict(row) if row else None


def find_raw_by_id(
    db: Session, secret_id: uuid.UUID, workspace_id: uuid.UUID,
) -> dict | None:
    """Return secret row with ciphertext for decryption. Workspace-scoped."""
    row = db.execute(
        text(f"""
            SELECT {_RAW_SELECT_COLS}
            FROM {SCHEMA}.workspace_secrets
            WHERE id = :id AND workspace_id = :workspace_id
        """),
        {'id': str(secret_id), 'workspace_id': str(workspace_id)},
    ).fetchone()
    if not row:
        return None
    return {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'secret_ciphertext': row.secret_ciphertext,
        'encryption_key_version': row.encryption_key_version,
    }


def insert(db: Session, secret: dict) -> dict:
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.workspace_secrets
                (id, workspace_id, name, description, secret_type,
                 secret_hash, secret_ciphertext, encryption_key_version,
                 masked_display, created_by_id, created_at, updated_at)
            VALUES
                (:id, :workspace_id, :name, :description, :secret_type,
                 :secret_hash, :secret_ciphertext, :encryption_key_version,
                 :masked_display, :created_by_id, :created_at, :updated_at)
            RETURNING {_SELECT_COLS}
        """),
        {
            'id': str(secret['id']),
            'workspace_id': str(secret['workspace_id']),
            'name': secret['name'],
            'description': secret['description'],
            'secret_type': secret['secret_type'],
            'secret_hash': secret.get('secret_hash'),
            'secret_ciphertext': secret.get('secret_ciphertext'),
            'encryption_key_version': secret.get('encryption_key_version', 1),
            'masked_display': secret['masked_display'],
            'created_by_id': secret['created_by_id'],
            'created_at': secret['created_at'],
            'updated_at': secret['updated_at'],
        },
    ).fetchone()
    db.commit()
    return _row_to_dict(row)


def delete(db: Session, secret_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> bool:
    if workspace_id:
        result = db.execute(
            text(f"DELETE FROM {SCHEMA}.workspace_secrets WHERE id = :id AND workspace_id = :wid"),
            {'id': str(secret_id), 'wid': str(workspace_id)},
        )
    else:
        result = db.execute(
            text(f"DELETE FROM {SCHEMA}.workspace_secrets WHERE id = :id"),
            {'id': str(secret_id)},
        )
    db.commit()
    return result.rowcount > 0


def update_metadata(
    db: Session, secret_id: uuid.UUID, updates: dict, workspace_id: uuid.UUID | None = None,
) -> dict | None:
    now = datetime.now(timezone.utc)
    set_clauses = ['updated_at = :updated_at']
    params: dict = {'id': str(secret_id), 'updated_at': now}
    if workspace_id:
        params['wid'] = str(workspace_id)

    if 'name' in updates:
        set_clauses.append('name = :name')
        params['name'] = updates['name']
    if 'description' in updates:
        set_clauses.append('description = :description')
        params['description'] = updates['description']

    where = 'WHERE id = :id'
    if workspace_id:
        where += ' AND workspace_id = :wid'
    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspace_secrets
            SET {', '.join(set_clauses)}
            {where}
            RETURNING {_SELECT_COLS}
        """),
        params,
    ).fetchone()
    db.commit()
    return _row_to_dict(row) if row else None


def find_all_raw_by_workspace(
    db: Session, workspace_id: uuid.UUID,
) -> list[dict]:
    """Return all secret rows with ciphertext for rotation."""
    rows = db.execute(
        text(f"""
            SELECT {_RAW_SELECT_COLS}
            FROM {SCHEMA}.workspace_secrets
            WHERE workspace_id = :workspace_id
            ORDER BY created_at ASC
        """),
        {'workspace_id': str(workspace_id)},
    ).fetchall()
    return [
        {
            'id': str(r.id),
            'workspace_id': str(r.workspace_id),
            'secret_ciphertext': r.secret_ciphertext,
            'encryption_key_version': r.encryption_key_version,
        }
        for r in rows
    ]


def update_ciphertext(
    db: Session,
    secret_id: uuid.UUID,
    workspace_id: uuid.UUID,
    ciphertext: str,
    key_version: int,
) -> bool:
    """Update ciphertext and key version after re-encryption."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspace_secrets
            SET secret_ciphertext = :ciphertext,
                encryption_key_version = :key_version,
                updated_at = :updated_at
            WHERE id = :id AND workspace_id = :workspace_id
        """),
        {
            'id': str(secret_id),
            'workspace_id': str(workspace_id),
            'ciphertext': ciphertext,
            'key_version': key_version,
            'updated_at': now,
        },
    )
    db.commit()
    return result.rowcount > 0


def _row_to_dict(row) -> dict:
    """Convert DB row to dict. NEVER includes secret_hash or ciphertext."""
    return {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'name': row.name,
        'description': row.description or '',
        'secret_type': row.secret_type,
        'masked_display': row.masked_display,
        'created_by_id': row.created_by_id,
        'created_at': row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
        'updated_at': row.updated_at.isoformat() if hasattr(row.updated_at, 'isoformat') else str(row.updated_at),
    }


from src.application.ports import SecretRepository as SecretRepositoryPort


class SecretRepositoryAdapter(SecretRepositoryPort):
    """Infrastructure adapter implementing SecretRepository port."""

    def find_by_workspace(self, db, workspace_id, *, limit=50, offset=0):
        return find_by_workspace(db, workspace_id, limit=limit, offset=offset)

    def find_by_id(self, db, secret_id):
        return find_by_id(db, secret_id)

    def find_raw_by_id(self, db, secret_id, workspace_id):
        return find_raw_by_id(db, secret_id, workspace_id)

    def insert(self, db, secret):
        return insert(db, secret)

    def delete(self, db, secret_id, workspace_id=None):
        return delete(db, secret_id, workspace_id=workspace_id)

    def update_metadata(self, db, secret_id, updates, workspace_id=None):
        return update_metadata(db, secret_id, updates, workspace_id=workspace_id)

    def find_all_raw_by_workspace(self, db, workspace_id):
        return find_all_raw_by_workspace(db, workspace_id)

    def update_ciphertext(self, db, secret_id, workspace_id, ciphertext, key_version):
        return update_ciphertext(db, secret_id, workspace_id, ciphertext, key_version)
