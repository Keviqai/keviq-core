"""Secret application service — CRUD with envelope encryption."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.domain.secret import (
    VALID_SECRET_TYPES,
    decrypt_value,
    encrypt_value,
    mask_value,
)
from src.domain.secret_errors import SecretNotFound

from .bootstrap import get_secret_repo


def list_secrets(
    db, workspace_id: uuid.UUID, *, limit: int = 50, offset: int = 0,
) -> list[dict]:
    """List secret metadata (no ciphertext) for a workspace."""
    return get_secret_repo().find_by_workspace(db, workspace_id, limit=limit, offset=offset)


def create_secret(
    db,
    workspace_id: uuid.UUID,
    name: str,
    secret_type: str,
    raw_value: str,
    created_by_id: str,
    description: str | None = None,
) -> dict:
    """Create a secret — encrypt the value, store masked display, return metadata."""
    if secret_type not in VALID_SECRET_TYPES:
        raise ValueError(f"Invalid secret_type: {secret_type}")

    now = datetime.now(timezone.utc)
    secret_id = uuid.uuid4()
    ciphertext, key_version = encrypt_value(raw_value)
    secret = {
        'id': secret_id,
        'workspace_id': workspace_id,
        'name': name,
        'description': description or '',
        'secret_type': secret_type,
        'secret_hash': None,
        'secret_ciphertext': ciphertext,
        'encryption_key_version': key_version,
        'masked_display': mask_value(raw_value),
        'created_by_id': created_by_id,
        'created_at': now,
        'updated_at': now,
    }
    return get_secret_repo().insert(db, secret)


def retrieve_secret_value(
    db, secret_id: uuid.UUID, workspace_id: uuid.UUID,
) -> str:
    """Decrypt and return a secret value. Internal service use only.

    Raises SecretNotFound if the secret doesn't exist or wrong workspace.
    Raises ValueError if the secret was created before encryption (hash-only).
    """
    row = get_secret_repo().find_raw_by_id(db, secret_id, workspace_id)
    if not row:
        raise SecretNotFound(str(secret_id))
    if not row.get('secret_ciphertext'):
        raise ValueError(
            "Secret was created before encryption was enabled — "
            "value is not retrievable. Re-create the secret."
        )
    version = row.get('encryption_key_version', 1)
    return decrypt_value(row['secret_ciphertext'], key_version=version)


def delete_secret(db, secret_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> None:
    """Delete a secret by ID. Raises SecretNotFound if missing or wrong workspace."""
    deleted = get_secret_repo().delete(db, secret_id, workspace_id=workspace_id)
    if not deleted:
        raise SecretNotFound(str(secret_id))


def update_secret_metadata(
    db, secret_id: uuid.UUID, updates: dict, workspace_id: uuid.UUID | None = None,
) -> dict:
    """Update name/description only. Raises SecretNotFound if missing or wrong workspace."""
    result = get_secret_repo().update_metadata(db, secret_id, updates, workspace_id=workspace_id)
    if not result:
        raise SecretNotFound(str(secret_id))
    return result
