"""Integration application service — CRUD for workspace integration configs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.domain.integration import (
    VALID_INTEGRATION_TYPES,
    VALID_PROVIDER_KINDS,
    IntegrationNotFound,
)

from .integration_bootstrap import get_integration_repo


def list_integrations(
    db: Session, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    """List integration configs for a workspace."""
    return get_integration_repo().find_by_workspace(
        db, workspace_id, limit=limit, offset=offset,
    )


def create_integration(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
    integration_type: str,
    provider_kind: str,
    created_by_id: str,
    endpoint_url: str | None = None,
    default_model: str | None = None,
    api_key_secret_ref: str | None = None,
    description: str | None = None,
    is_enabled: bool = True,
) -> dict:
    """Create a workspace integration config."""
    if integration_type not in VALID_INTEGRATION_TYPES:
        raise ValueError(f"Invalid integration_type: {integration_type}")
    if provider_kind not in VALID_PROVIDER_KINDS:
        raise ValueError(f"Invalid provider_kind: {provider_kind}")

    now = datetime.now(timezone.utc)
    integration = {
        'id': uuid.uuid4(),
        'workspace_id': workspace_id,
        'name': name,
        'integration_type': integration_type,
        'provider_kind': provider_kind,
        'endpoint_url': endpoint_url,
        'default_model': default_model,
        'api_key_secret_ref': api_key_secret_ref,
        'description': description or '',
        'is_enabled': is_enabled,
        'config': None,
        'created_by_id': created_by_id,
        'created_at': now,
        'updated_at': now,
    }
    return get_integration_repo().insert(db, integration)


def get_integration(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> dict:
    """Get a single integration by ID, workspace-scoped."""
    result = get_integration_repo().find_by_id(db, integration_id, workspace_id)
    if not result:
        raise IntegrationNotFound(str(integration_id))
    return result


def update_integration(
    db: Session, integration_id: uuid.UUID, updates: dict, workspace_id: uuid.UUID,
) -> dict:
    """Update integration fields. Raises IntegrationNotFound if missing."""
    if 'integration_type' in updates and updates['integration_type'] not in VALID_INTEGRATION_TYPES:
        raise ValueError(f"Invalid integration_type: {updates['integration_type']}")
    if 'provider_kind' in updates and updates['provider_kind'] not in VALID_PROVIDER_KINDS:
        raise ValueError(f"Invalid provider_kind: {updates['provider_kind']}")

    result = get_integration_repo().update(db, integration_id, updates, workspace_id)
    if not result:
        raise IntegrationNotFound(str(integration_id))
    return result


def delete_integration(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> None:
    """Delete an integration. Raises IntegrationNotFound if missing."""
    deleted = get_integration_repo().delete(db, integration_id, workspace_id)
    if not deleted:
        raise IntegrationNotFound(str(integration_id))


def toggle_integration(
    db: Session, integration_id: uuid.UUID, workspace_id: uuid.UUID,
) -> dict:
    """Atomically toggle is_enabled on an integration."""
    result = get_integration_repo().toggle_enabled(db, integration_id, workspace_id)
    if not result:
        raise IntegrationNotFound(str(integration_id))
    return result
