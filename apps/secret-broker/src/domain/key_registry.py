"""Versioned encryption key registry for secret key rotation.

Manages multiple AES-256 encryption keys by version. Keys are loaded
from environment variables: SECRET_ENCRYPTION_KEY_V1, _V2, etc.
The plain SECRET_ENCRYPTION_KEY is treated as an alias for the latest version.
"""

from __future__ import annotations

import base64
import os
import re


class KeyRegistryError(Exception):
    """Base error for key registry operations."""


class KeyVersionNotFound(KeyRegistryError):
    """Raised when a requested key version does not exist."""

    def __init__(self, version: int) -> None:
        super().__init__(f"Encryption key version {version} not found")
        self.version = version


class InvalidKeyError(KeyRegistryError):
    """Raised when a key fails validation."""


def validate_key(key: bytes) -> None:
    """Ensure key is exactly 32 bytes (AES-256). Raises InvalidKeyError."""
    if not isinstance(key, bytes):
        raise InvalidKeyError(f"Key must be bytes, got {type(key).__name__}")
    if len(key) != 32:
        raise InvalidKeyError(
            f"Encryption key must be exactly 32 bytes. Got {len(key)} bytes."
        )


def _decode_key(raw: str, label: str) -> bytes:
    """Base64-decode and validate a key from an env var value."""
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise InvalidKeyError(f"{label}: invalid base64 — {exc}") from exc
    validate_key(key)
    return key


class KeyRegistry:
    """Versioned encryption key store.

    Keys are loaded from environment on construction and immutable after.
    """

    def __init__(self) -> None:
        self._keys: dict[int, bytes] = {}
        self._current_version: int = 0
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Scan environment for versioned and legacy key variables."""
        pattern = re.compile(r'^SECRET_ENCRYPTION_KEY_V(\d+)$')

        # Load versioned keys: SECRET_ENCRYPTION_KEY_V1, V2, ...
        for var, value in os.environ.items():
            match = pattern.match(var)
            if match and value:
                version = int(match.group(1))
                if version < 1:
                    raise InvalidKeyError(f"{var}: version must be >= 1")
                self._keys[version] = _decode_key(value, var)

        # Legacy fallback: SECRET_ENCRYPTION_KEY → map to version 1
        # if no versioned keys exist, or to max+1 if versioned keys exist.
        legacy = os.environ.get('SECRET_ENCRYPTION_KEY')
        if legacy:
            legacy_key = _decode_key(legacy, 'SECRET_ENCRYPTION_KEY')
            if not self._keys:
                # No versioned keys — legacy becomes version 1
                self._keys[1] = legacy_key
            else:
                # If legacy key matches an existing version, skip.
                # Otherwise, treat it as the latest version.
                if legacy_key not in self._keys.values():
                    next_ver = max(self._keys) + 1
                    self._keys[next_ver] = legacy_key

        if not self._keys:
            raise KeyRegistryError(
                "No encryption keys found. Set SECRET_ENCRYPTION_KEY or "
                "SECRET_ENCRYPTION_KEY_V1 (base64-encoded 32 bytes)."
            )

        self._current_version = max(self._keys)

    @property
    def current_version(self) -> int:
        """The highest key version — used for new encryptions."""
        return self._current_version

    @property
    def versions(self) -> list[int]:
        """All available key versions, sorted ascending."""
        return sorted(self._keys)

    def get_current_key(self) -> tuple[bytes, int]:
        """Return (key, version) for the current (latest) version."""
        return self._keys[self._current_version], self._current_version

    def get_key_by_version(self, version: int) -> bytes:
        """Return the key for a specific version. Raises KeyVersionNotFound."""
        key = self._keys.get(version)
        if key is None:
            raise KeyVersionNotFound(version)
        return key


# Module-level singleton, lazily initialized.
_registry: KeyRegistry | None = None


def get_key_registry() -> KeyRegistry:
    """Return the global KeyRegistry singleton, creating it on first call."""
    global _registry
    if _registry is None:
        _registry = KeyRegistry()
    return _registry


def reset_key_registry() -> None:
    """Reset the singleton — for testing only."""
    global _registry
    _registry = None
