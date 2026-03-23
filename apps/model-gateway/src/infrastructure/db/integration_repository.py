"""Integration repository — database access for workspace_integrations table."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.application.integration_ports import IntegrationRepository as IntegrationRepositoryPort

SCHEMA = 'model_gateway_core'

_MAX_LIMIT = 200

_UPDATE_FRAGMENTS: dict[str, str] = {
    'name': 'name = :name',
    'integration_type': 'integration_type = :integration_type',
    'provider_kind': 'provider_kind = :provider_kind',
    'endpoint_url': 'endpoint_url = :endpoint_url',
    'default_model': 'default_model = :default_model',
    'api_key_secret_ref': 'api_key_secret_ref = :api_key_secret_ref',
    'description': 'description = :description',
    'is_enabled': 'is_enabled = :is_enabled',
}

_SELECT_COLS = (
    'id, workspace_id, name, integration_type, provider_kind, '
    'endpoint_url, default_model, api_key_secret_ref, description, '
    'is_enabled, config, created_by_id, created_at, updated_at'
)


def find_by_workspace(
    db: Session, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    limit = min(max(limit, 1), _MAX_LIMIT)
    offset = max(offset, 0)
    rows = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.workspace_integrations
            WHERE workspace_id = :wid
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {'wid': str(workspace_id), 'limit': limit, 'offset': offset},
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def find_by_id(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> dict | None:
    row = db.execute(
        text(f"""
            SELECT {_SELECT_COLS}
            FROM {SCHEMA}.workspace_integrations
            WHERE id = :id AND workspace_id = :wid
        """),
        {'id': str(integration_id), 'wid': str(workspace_id)},
    ).fetchone()
    return _row_to_dict(row) if row else None


def insert(db: Session, integration: dict) -> dict:
    config_json = json.dumps(integration['config']) if integration['config'] else None
    row = db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.workspace_integrations
                (id, workspace_id, name, integration_type, provider_kind,
                 endpoint_url, default_model, api_key_secret_ref, description,
                 is_enabled, config, created_by_id, created_at, updated_at)
            VALUES
                (:id, :workspace_id, :name, :integration_type, :provider_kind,
                 :endpoint_url, :default_model, :api_key_secret_ref, :description,
                 :is_enabled, CAST(:config AS jsonb), :created_by_id, :created_at, :updated_at)
            RETURNING {_SELECT_COLS}
        """),
        {
            'id': str(integration['id']),
            'workspace_id': str(integration['workspace_id']),
            'name': integration['name'],
            'integration_type': integration['integration_type'],
            'provider_kind': integration['provider_kind'],
            'endpoint_url': integration.get('endpoint_url'),
            'default_model': integration.get('default_model'),
            'api_key_secret_ref': integration.get('api_key_secret_ref'),
            'description': integration.get('description', ''),
            'is_enabled': integration.get('is_enabled', True),
            'config': config_json,
            'created_by_id': integration['created_by_id'],
            'created_at': integration['created_at'],
            'updated_at': integration['updated_at'],
        },
    ).fetchone()
    db.commit()
    return _row_to_dict(row)


def update(
    db: Session, integration_id: uuid.UUID, updates: dict, workspace_id: uuid.UUID,
) -> dict | None:
    now = datetime.now(timezone.utc)
    set_clauses = ['updated_at = :updated_at']
    params: dict = {
        'id': str(integration_id),
        'wid': str(workspace_id),
        'updated_at': now,
    }

    for key in updates:
        if key in _UPDATE_FRAGMENTS:
            set_clauses.append(_UPDATE_FRAGMENTS[key])
            params[key] = updates[key]

    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspace_integrations
            SET {', '.join(set_clauses)}
            WHERE id = :id AND workspace_id = :wid
            RETURNING {_SELECT_COLS}
        """),
        params,
    ).fetchone()
    db.commit()
    return _row_to_dict(row) if row else None


def delete(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> bool:
    result = db.execute(
        text(f"""
            DELETE FROM {SCHEMA}.workspace_integrations
            WHERE id = :id AND workspace_id = :wid
        """),
        {'id': str(integration_id), 'wid': str(workspace_id)},
    )
    db.commit()
    return result.rowcount > 0


def toggle_enabled(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> dict | None:
    """Atomically flip is_enabled. Returns updated row or None."""
    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.workspace_integrations
            SET is_enabled = NOT is_enabled, updated_at = :now
            WHERE id = :id AND workspace_id = :wid
            RETURNING {_SELECT_COLS}
        """),
        {
            'id': str(integration_id),
            'wid': str(workspace_id),
            'now': datetime.now(timezone.utc),
        },
    ).fetchone()
    db.commit()
    return _row_to_dict(row) if row else None


def _row_to_dict(row) -> dict:
    """Convert DB row to dict."""
    return {
        'id': str(row.id),
        'workspace_id': str(row.workspace_id),
        'name': row.name,
        'integration_type': row.integration_type,
        'provider_kind': row.provider_kind,
        'endpoint_url': row.endpoint_url or '',
        'default_model': row.default_model or '',
        'api_key_secret_ref': row.api_key_secret_ref or '',
        'description': row.description or '',
        'is_enabled': row.is_enabled,
        'config': row.config,
        'created_by_id': row.created_by_id,
        'created_at': row.created_at.isoformat(),
        'updated_at': row.updated_at.isoformat(),
    }


class IntegrationRepositoryAdapter(IntegrationRepositoryPort):
    """Infrastructure adapter implementing IntegrationRepository port."""

    def find_by_workspace(self, db, workspace_id, *, limit=50, offset=0):
        return find_by_workspace(db, workspace_id, limit=limit, offset=offset)

    def find_by_id(self, db, integration_id, workspace_id):
        return find_by_id(db, integration_id, workspace_id)

    def insert(self, db, integration):
        return insert(db, integration)

    def update(self, db, integration_id, updates, workspace_id):
        return update(db, integration_id, updates, workspace_id)

    def delete(self, db, integration_id, workspace_id):
        return delete(db, integration_id, workspace_id)

    def toggle_enabled(self, db, integration_id, workspace_id):
        return toggle_enabled(db, integration_id, workspace_id)
