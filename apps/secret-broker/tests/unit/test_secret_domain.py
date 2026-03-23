"""Unit tests for secret domain — encryption, masking, key validation."""

import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestGetEncryptionKey:
    """get_encryption_key() — env var validation."""

    def test_missing_key_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv('SECRET_ENCRYPTION_KEY', raising=False)
        from src.domain.secret import get_encryption_key
        with pytest.raises(RuntimeError, match='SECRET_ENCRYPTION_KEY'):
            get_encryption_key()

    def test_valid_key_returns_32_bytes(self, monkeypatch):
        key = os.urandom(32)
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY', base64.b64encode(key).decode())
        from src.domain.secret import get_encryption_key
        result = get_encryption_key()
        assert result == key
        assert len(result) == 32

    def test_wrong_length_key_raises(self, monkeypatch):
        short_key = base64.b64encode(os.urandom(16)).decode()
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY', short_key)
        from src.domain.secret import get_encryption_key
        with pytest.raises(RuntimeError, match='32 bytes'):
            get_encryption_key()

    def test_empty_string_raises(self, monkeypatch):
        monkeypatch.setenv('SECRET_ENCRYPTION_KEY', '')
        from src.domain.secret import get_encryption_key
        with pytest.raises(RuntimeError, match='SECRET_ENCRYPTION_KEY'):
            get_encryption_key()


class TestEncryptDecrypt:
    """encrypt_value / decrypt_value — round-trip correctness."""

    def _key(self):
        return os.urandom(32)

    def test_round_trip(self):
        from src.domain.secret import encrypt_value, decrypt_value
        key = self._key()
        plaintext = 'my-secret-api-key-12345'
        encrypted, _ver = encrypt_value(plaintext, key)
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == plaintext

    def test_encrypted_is_base64(self):
        from src.domain.secret import encrypt_value
        key = self._key()
        encrypted, _ver = encrypt_value('test', key)
        base64.b64decode(encrypted)  # should not raise

    def test_encrypted_differs_from_plaintext(self):
        from src.domain.secret import encrypt_value
        key = self._key()
        plaintext = 'secret'
        encrypted, _ver = encrypt_value(plaintext, key)
        assert encrypted != plaintext

    def test_different_encryptions_produce_different_ciphertext(self):
        from src.domain.secret import encrypt_value
        key = self._key()
        e1, _ = encrypt_value('same', key)
        e2, _ = encrypt_value('same', key)
        assert e1 != e2  # random nonce

    def test_wrong_key_fails_decrypt(self):
        from src.domain.secret import encrypt_value, decrypt_value
        key1 = self._key()
        key2 = self._key()
        encrypted, _ver = encrypt_value('secret', key1)
        with pytest.raises(Exception):  # InvalidTag from cryptography
            decrypt_value(encrypted, key2)

    def test_empty_string_round_trip(self):
        from src.domain.secret import encrypt_value, decrypt_value
        key = self._key()
        encrypted, _ver = encrypt_value('', key)
        assert decrypt_value(encrypted, key) == ''

    def test_unicode_round_trip(self):
        from src.domain.secret import encrypt_value, decrypt_value
        key = self._key()
        plaintext = 'mật-khẩu-bí-mật-🔐'
        encrypted, _ver = encrypt_value(plaintext, key)
        assert decrypt_value(encrypted, key) == plaintext


class TestMaskValue:
    """mask_value — display masking."""

    def test_short_value_fully_masked(self):
        from src.domain.secret import mask_value
        assert mask_value('abc') == '****'
        assert mask_value('ab') == '****'
        assert mask_value('') == '****'

    def test_long_value_shows_last_4(self):
        from src.domain.secret import mask_value
        assert mask_value('my-api-key-12345') == '****2345'

    def test_exactly_4_chars_fully_masked(self):
        from src.domain.secret import mask_value
        assert mask_value('abcd') == '****'

    def test_5_chars_shows_last_4(self):
        from src.domain.secret import mask_value
        assert mask_value('abcde') == '****bcde'


class TestValidSecretTypes:
    """VALID_SECRET_TYPES — known types."""

    def test_contains_expected_types(self):
        from src.domain.secret import VALID_SECRET_TYPES
        assert 'api_key' in VALID_SECRET_TYPES
        assert 'token' in VALID_SECRET_TYPES
        assert 'password' in VALID_SECRET_TYPES
        assert 'custom' in VALID_SECRET_TYPES

    def test_is_frozen(self):
        from src.domain.secret import VALID_SECRET_TYPES
        assert isinstance(VALID_SECRET_TYPES, frozenset)
