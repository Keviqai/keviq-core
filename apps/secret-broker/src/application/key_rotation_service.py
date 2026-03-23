"""Key rotation service — re-encrypt secrets with the current key version."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from src.domain.key_registry import get_key_registry
from src.domain.secret import decrypt_value, encrypt_value

from .bootstrap import get_secret_repo

logger = logging.getLogger(__name__)


@dataclass
class RotationResult:
    """Outcome of a workspace key rotation batch."""

    rotated: int = 0
    already_current: int = 0
    errors: list[str] = field(default_factory=list)


def rotate_secret(
    db, secret_id: uuid.UUID, workspace_id: uuid.UUID,
) -> bool:
    """Re-encrypt a single secret with the current key version.

    Returns True if re-encrypted, False if already current.
    Raises on decryption/encryption failure.
    """
    repo = get_secret_repo()
    row = repo.find_raw_by_id(db, secret_id, workspace_id)
    if not row:
        raise ValueError(f"Secret {secret_id} not found in workspace {workspace_id}")
    if not row.get('secret_ciphertext'):
        raise ValueError(f"Secret {secret_id} has no ciphertext to rotate")

    registry = get_key_registry()
    current_version = registry.current_version
    old_version = row.get('encryption_key_version', 1)

    if old_version == current_version:
        return False

    # Decrypt with old key, re-encrypt with current key
    plaintext = decrypt_value(row['secret_ciphertext'], key_version=old_version)
    new_ciphertext, new_version = encrypt_value(plaintext)

    repo.update_ciphertext(
        db, uuid.UUID(row['id']), workspace_id, new_ciphertext, new_version,
    )
    logger.info(
        "Rotated secret %s from key v%d to v%d",
        secret_id, old_version, new_version,
    )
    return True


def rotate_workspace_secrets(
    db, workspace_id: uuid.UUID,
) -> RotationResult:
    """Re-encrypt all secrets in a workspace to the current key version."""
    repo = get_secret_repo()
    rows = repo.find_all_raw_by_workspace(db, workspace_id)
    result = RotationResult()
    registry = get_key_registry()
    current_version = registry.current_version

    for row in rows:
        sid = row['id']
        old_version = row.get('encryption_key_version', 1)

        if old_version == current_version:
            result.already_current += 1
            continue

        if not row.get('secret_ciphertext'):
            result.errors.append(f"{sid}: no ciphertext")
            continue

        try:
            plaintext = decrypt_value(
                row['secret_ciphertext'], key_version=old_version,
            )
            new_ct, new_ver = encrypt_value(plaintext)
            repo.update_ciphertext(
                db, uuid.UUID(sid), workspace_id, new_ct, new_ver,
            )
            result.rotated += 1
        except Exception as exc:
            msg = f"{sid}: {exc}"
            logger.error("Rotation failed for secret %s: %s", sid, exc)
            result.errors.append(msg)

    logger.info(
        "Workspace %s rotation complete: rotated=%d, current=%d, errors=%d",
        workspace_id, result.rotated, result.already_current, len(result.errors),
    )
    return result


@dataclass
class VersionCount:
    """Number of secrets encrypted with a given key version."""

    version: int
    count: int


def get_rotation_status(
    db, workspace_id: uuid.UUID,
) -> list[VersionCount]:
    """Return count of secrets per key version for a workspace."""
    repo = get_secret_repo()
    rows = repo.find_all_raw_by_workspace(db, workspace_id)
    counts: dict[int, int] = {}
    for row in rows:
        ver = row.get('encryption_key_version', 1)
        counts[ver] = counts.get(ver, 0) + 1
    return [VersionCount(version=v, count=c) for v, c in sorted(counts.items())]
