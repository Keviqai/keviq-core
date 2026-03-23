"""Secret domain utilities — encryption, masking, and legacy hashing."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.domain.key_registry import get_key_registry

VALID_SECRET_TYPES = frozenset({'api_key', 'token', 'password', 'custom'})

_NONCE_SIZE = 12  # bytes, standard for AES-GCM


def get_encryption_key() -> bytes:
    """Load 32-byte AES-256 key from environment. Fail-fast if missing.

    DEPRECATED: Use KeyRegistry via get_key_registry() instead.
    Kept for backward compatibility with callers that don't need versioning.
    """
    raw = os.environ.get('SECRET_ENCRYPTION_KEY')
    if not raw:
        raise RuntimeError(
            "SECRET_ENCRYPTION_KEY environment variable is required. "
            "Generate with: python -c \"import os,base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError(
            "SECRET_ENCRYPTION_KEY must be exactly 32 bytes (base64-encoded). "
            f"Got {len(key)} bytes."
        )
    return key


def encrypt_value(raw: str, key: bytes | None = None) -> tuple[str, int]:
    """AES-256-GCM encrypt a secret value.

    If *key* is provided, uses it directly with version=0 (legacy mode).
    If *key* is None, uses the KeyRegistry current key with its version.

    Returns (base64-encoded ciphertext, key_version).
    """
    if key is not None:
        # Legacy caller — use provided key, version 0 signals unversioned
        nonce = os.urandom(_NONCE_SIZE)
        ct = AESGCM(key).encrypt(nonce, raw.encode('utf-8'), None)
        return base64.b64encode(nonce + ct).decode('ascii'), 0

    registry = get_key_registry()
    enc_key, version = registry.get_current_key()
    nonce = os.urandom(_NONCE_SIZE)
    ct = AESGCM(enc_key).encrypt(nonce, raw.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('ascii'), version


def decrypt_value(encrypted_b64: str, key: bytes | None = None, *, key_version: int = 0) -> str:
    """Decrypt base64-encoded AES-256-GCM ciphertext to plaintext.

    If *key* is provided, uses it directly (legacy mode).
    If *key* is None, looks up the key by *key_version* from the registry.
    """
    data = base64.b64decode(encrypted_b64)
    nonce, ct = data[:_NONCE_SIZE], data[_NONCE_SIZE:]

    if key is not None:
        return AESGCM(key).decrypt(nonce, ct, None).decode('utf-8')

    registry = get_key_registry()
    dec_key = registry.get_key_by_version(key_version)
    return AESGCM(dec_key).decrypt(nonce, ct, None).decode('utf-8')


def mask_value(raw: str) -> str:
    """Return a masked display string, e.g. '****abcd'."""
    if len(raw) <= 4:
        return '****'
    return '****' + raw[-4:]


def hash_value(raw: str, salt: str = '') -> str:
    """DEPRECATED — salted SHA-256 hex digest. Kept for backward compat only."""
    return hashlib.sha256((salt + raw).encode('utf-8')).hexdigest()
