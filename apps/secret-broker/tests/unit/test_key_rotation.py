"""Unit tests for key rotation — registry, versioned encrypt/decrypt, rotation service."""

from __future__ import annotations

import base64
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64_key(raw: bytes | None = None) -> str:
    """Return a base64-encoded 32-byte key string."""
    return base64.b64encode(raw or os.urandom(32)).decode()


def _clean_env(monkeypatch):
    """Remove all encryption key env vars."""
    monkeypatch.delenv('SECRET_ENCRYPTION_KEY', raising=False)
    for i in range(1, 10):
        monkeypatch.delenv(f'SECRET_ENCRYPTION_KEY_V{i}', raising=False)


# ---------------------------------------------------------------------------
# KeyRegistry
# ---------------------------------------------------------------------------

class TestKeyRegistry:
    """KeyRegistry — loading, validation, version management."""

    def test_loads_single_legacy_key(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY', _b64_key())
        reg = KeyRegistry()
        assert reg.current_version == 1
        assert reg.versions == [1]

    def test_loads_versioned_keys(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key())
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V2', _b64_key())
        reg = KeyRegistry()
        assert reg.versions == [1, 2]
        assert reg.current_version == 2

    def test_current_key_returns_highest_version(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        k1 = os.urandom(32)
        k2 = os.urandom(32)
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key(k1))
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V2', _b64_key(k2))
        reg = KeyRegistry()
        key, ver = reg.get_current_key()
        assert ver == 2
        assert key == k2

    def test_get_key_by_version(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        k1 = os.urandom(32)
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key(k1))
        reg = KeyRegistry()
        assert reg.get_key_by_version(1) == k1

    def test_missing_version_raises(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, KeyVersionNotFound, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key())
        reg = KeyRegistry()
        with pytest.raises(KeyVersionNotFound):
            reg.get_key_by_version(99)

    def test_no_keys_raises(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, KeyRegistryError, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        with pytest.raises(KeyRegistryError, match='No encryption keys found'):
            KeyRegistry()

    def test_invalid_key_size_rejected(self, monkeypatch):
        from src.domain.key_registry import KeyRegistry, InvalidKeyError, reset_key_registry
        _clean_env(monkeypatch)
        reset_key_registry()
        short = base64.b64encode(os.urandom(16)).decode()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', short)
        with pytest.raises(InvalidKeyError, match='32 bytes'):
            KeyRegistry()


class TestValidateKey:
    """validate_key — standalone validation."""

    def test_valid_key_passes(self):
        from src.domain.key_registry import validate_key
        validate_key(os.urandom(32))  # should not raise

    def test_short_key_rejected(self):
        from src.domain.key_registry import validate_key, InvalidKeyError
        with pytest.raises(InvalidKeyError):
            validate_key(os.urandom(16))

    def test_non_bytes_rejected(self):
        from src.domain.key_registry import validate_key, InvalidKeyError
        with pytest.raises(InvalidKeyError):
            validate_key("not-bytes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Versioned encrypt / decrypt
# ---------------------------------------------------------------------------

class TestVersionedEncryptDecrypt:
    """encrypt_value / decrypt_value with key registry."""

    def test_encrypt_uses_current_version(self, monkeypatch):
        from src.domain.key_registry import reset_key_registry
        from src.domain.secret import encrypt_value
        _clean_env(monkeypatch)
        reset_key_registry()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key())
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V2', _b64_key())
        reset_key_registry()

        ct, ver = encrypt_value('hello')
        assert ver == 2
        assert ct != 'hello'

    def test_decrypt_with_old_version_works(self, monkeypatch):
        from src.domain.key_registry import reset_key_registry
        from src.domain.secret import encrypt_value, decrypt_value
        _clean_env(monkeypatch)
        reset_key_registry()

        k1 = os.urandom(32)
        k2 = os.urandom(32)
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key(k1))
        reset_key_registry()

        # Encrypt with v1 only
        ct, ver = encrypt_value('secret-data')
        assert ver == 1

        # Now add v2 and re-init registry
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V2', _b64_key(k2))
        reset_key_registry()

        # Decrypt v1 ciphertext using key_version=1
        plain = decrypt_value(ct, key_version=1)
        assert plain == 'secret-data'

    def test_legacy_key_param_still_works(self):
        from src.domain.secret import encrypt_value, decrypt_value
        key = os.urandom(32)
        ct, ver = encrypt_value('test', key=key)
        assert ver == 0  # legacy mode
        plain = decrypt_value(ct, key=key)
        assert plain == 'test'

    def test_round_trip_via_registry(self, monkeypatch):
        from src.domain.key_registry import reset_key_registry
        from src.domain.secret import encrypt_value, decrypt_value
        _clean_env(monkeypatch)
        reset_key_registry()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key())
        reset_key_registry()

        ct, ver = encrypt_value('round-trip-test')
        plain = decrypt_value(ct, key_version=ver)
        assert plain == 'round-trip-test'


# ---------------------------------------------------------------------------
# Rotation service
# ---------------------------------------------------------------------------

class _FakeRepo:
    """In-memory repo for rotation tests."""

    def __init__(self):
        self.secrets: dict[str, dict] = {}

    def find_raw_by_id(self, db, secret_id, workspace_id):
        key = str(secret_id)
        row = self.secrets.get(key)
        if row and str(row['workspace_id']) == str(workspace_id):
            return row
        return None

    def find_all_raw_by_workspace(self, db, workspace_id):
        return [
            r for r in self.secrets.values()
            if str(r['workspace_id']) == str(workspace_id)
        ]

    def update_ciphertext(self, db, secret_id, workspace_id, ciphertext, key_version):
        key = str(secret_id)
        if key in self.secrets:
            self.secrets[key]['secret_ciphertext'] = ciphertext
            self.secrets[key]['encryption_key_version'] = key_version
            return True
        return False

    # Stubs for port compliance
    def find_by_workspace(self, db, wid, *, limit=50, offset=0):
        return []

    def find_by_id(self, db, sid):
        return None

    def insert(self, db, secret):
        return secret

    def delete(self, db, sid, workspace_id=None):
        return True

    def update_metadata(self, db, sid, updates, workspace_id=None):
        return None


class TestRotationService:
    """key_rotation_service — rotate_secret, rotate_workspace_secrets, status."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        _clean_env(monkeypatch)
        from src.domain.key_registry import reset_key_registry
        reset_key_registry()

        self.k1 = os.urandom(32)
        self.k2 = os.urandom(32)
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V1', _b64_key(self.k1))
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY_V2', _b64_key(self.k2))
        reset_key_registry()

        self.repo = _FakeRepo()
        # Patch bootstrap to return our fake repo
        import src.application.bootstrap as bootstrap
        monkeypatch.setattr(bootstrap, '_secret_repo', self.repo)
        monkeypatch.setattr(bootstrap, '_configured', True)

        self.wid = uuid.uuid4()

    def _add_secret(self, version: int = 1, plaintext: str = 'my-secret') -> uuid.UUID:
        """Encrypt with a specific key version and store in fake repo."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from src.domain.key_registry import get_key_registry

        registry = get_key_registry()
        key = registry.get_key_by_version(version)
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
        ct_b64 = base64.b64encode(nonce + ct).decode()

        sid = uuid.uuid4()
        self.repo.secrets[str(sid)] = {
            'id': str(sid),
            'workspace_id': str(self.wid),
            'secret_ciphertext': ct_b64,
            'encryption_key_version': version,
        }
        return sid

    def test_rotate_single_secret(self):
        from src.application.key_rotation_service import rotate_secret
        sid = self._add_secret(version=1)
        rotated = rotate_secret(None, sid, self.wid)
        assert rotated is True
        assert self.repo.secrets[str(sid)]['encryption_key_version'] == 2

    def test_rotate_already_current_returns_false(self):
        from src.application.key_rotation_service import rotate_secret
        sid = self._add_secret(version=2)
        rotated = rotate_secret(None, sid, self.wid)
        assert rotated is False

    def test_rotate_workspace_secrets(self):
        from src.application.key_rotation_service import rotate_workspace_secrets
        self._add_secret(version=1, plaintext='s1')
        self._add_secret(version=1, plaintext='s2')
        self._add_secret(version=2, plaintext='s3')

        result = rotate_workspace_secrets(None, self.wid)
        assert result.rotated == 2
        assert result.already_current == 1
        assert result.errors == []

    def test_rotation_preserves_plaintext(self):
        from src.application.key_rotation_service import rotate_secret
        from src.domain.secret import decrypt_value
        sid = self._add_secret(version=1, plaintext='preserve-me')
        rotate_secret(None, sid, self.wid)

        row = self.repo.secrets[str(sid)]
        plain = decrypt_value(row['secret_ciphertext'], key_version=2)
        assert plain == 'preserve-me'

    def test_get_rotation_status(self):
        from src.application.key_rotation_service import get_rotation_status
        self._add_secret(version=1)
        self._add_secret(version=1)
        self._add_secret(version=2)

        counts = get_rotation_status(None, self.wid)
        status_map = {c.version: c.count for c in counts}
        assert status_map == {1: 2, 2: 1}

    def test_rotate_missing_secret_raises(self):
        from src.application.key_rotation_service import rotate_secret
        with pytest.raises(ValueError, match='not found'):
            rotate_secret(None, uuid.uuid4(), self.wid)

    def test_rotate_no_ciphertext_raises(self):
        from src.application.key_rotation_service import rotate_secret
        sid = uuid.uuid4()
        self.repo.secrets[str(sid)] = {
            'id': str(sid),
            'workspace_id': str(self.wid),
            'secret_ciphertext': None,
            'encryption_key_version': 1,
        }
        with pytest.raises(ValueError, match='no ciphertext'):
            rotate_secret(None, sid, self.wid)
