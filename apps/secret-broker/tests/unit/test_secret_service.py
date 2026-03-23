"""Unit tests for secret application service (mock repo)."""

import base64
import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Set a valid encryption key for tests that need it
_TEST_KEY = os.urandom(32)
os.environ['SECRET_ENCRYPTION_KEY'] = base64.b64encode(_TEST_KEY).decode()


def _mock_repo():
    repo = MagicMock()
    repo.insert.side_effect = lambda db, secret: secret
    repo.find_by_workspace.return_value = []
    repo.find_raw_by_id.return_value = None
    repo.delete.return_value = True
    repo.update_metadata.return_value = {'id': str(uuid4()), 'name': 'updated'}
    return repo


class TestCreateSecret:
    """create_secret — encrypt + store via repo."""

    def test_success_returns_dict_with_ciphertext(self):
        import src.application.secret_service as svc
        repo = _mock_repo()
        ws = uuid4()

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            result = svc.create_secret(
                MagicMock(), ws, 'my-key', 'api_key', 'sk-live-abc123', 'user-1',
            )

        assert result['name'] == 'my-key'
        assert result['secret_type'] == 'api_key'
        assert result['secret_ciphertext'] != 'sk-live-abc123'
        assert result['masked_display'] == '****c123'
        repo.insert.assert_called_once()

    def test_invalid_secret_type_raises(self):
        import src.application.secret_service as svc
        repo = _mock_repo()

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            with pytest.raises(ValueError, match='Invalid secret_type'):
                svc.create_secret(MagicMock(), uuid4(), 'n', 'invalid_type', 'v', 'u')

    def test_description_defaults_to_empty(self):
        import src.application.secret_service as svc
        repo = _mock_repo()

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            result = svc.create_secret(MagicMock(), uuid4(), 'n', 'token', 'v', 'u')

        assert result['description'] == ''


class TestRetrieveSecretValue:
    """retrieve_secret_value — decrypt from repo."""

    def test_success_returns_plaintext(self):
        import src.application.secret_service as svc
        from src.domain.secret import encrypt_value, get_encryption_key
        repo = _mock_repo()
        key = get_encryption_key()
        ciphertext, _ver = encrypt_value('my-secret', key)
        repo.find_raw_by_id.return_value = {
            'secret_ciphertext': ciphertext,
            'encryption_key_version': 1,
        }

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            result = svc.retrieve_secret_value(MagicMock(), uuid4(), uuid4())

        assert result == 'my-secret'

    def test_not_found_raises(self):
        import src.application.secret_service as svc
        from src.domain.secret_errors import SecretNotFound
        repo = _mock_repo()
        repo.find_raw_by_id.return_value = None

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            with pytest.raises(SecretNotFound):
                svc.retrieve_secret_value(MagicMock(), uuid4(), uuid4())

    def test_no_ciphertext_raises_value_error(self):
        import src.application.secret_service as svc
        repo = _mock_repo()
        repo.find_raw_by_id.return_value = {'secret_ciphertext': None}

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            with pytest.raises(ValueError, match='before encryption'):
                svc.retrieve_secret_value(MagicMock(), uuid4(), uuid4())


class TestDeleteSecret:
    """delete_secret — remove via repo."""

    def test_success(self):
        import src.application.secret_service as svc
        repo = _mock_repo()
        repo.delete.return_value = True

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            svc.delete_secret(MagicMock(), uuid4(), uuid4())

        repo.delete.assert_called_once()

    def test_not_found_raises(self):
        import src.application.secret_service as svc
        from src.domain.secret_errors import SecretNotFound
        repo = _mock_repo()
        repo.delete.return_value = False

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            with pytest.raises(SecretNotFound):
                svc.delete_secret(MagicMock(), uuid4())


class TestListSecrets:
    """list_secrets — passthrough to repo."""

    def test_returns_list(self):
        import src.application.secret_service as svc
        repo = _mock_repo()
        repo.find_by_workspace.return_value = [{'id': 'x', 'name': 'test'}]

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            result = svc.list_secrets(MagicMock(), uuid4())

        assert len(result) == 1
        assert result[0]['name'] == 'test'


class TestUpdateSecretMetadata:
    """update_secret_metadata — name/desc only."""

    def test_success(self):
        import src.application.secret_service as svc
        repo = _mock_repo()

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            result = svc.update_secret_metadata(MagicMock(), uuid4(), {'name': 'new'})

        assert result is not None
        repo.update_metadata.assert_called_once()

    def test_not_found_raises(self):
        import src.application.secret_service as svc
        from src.domain.secret_errors import SecretNotFound
        repo = _mock_repo()
        repo.update_metadata.return_value = None

        with patch.object(svc, 'get_secret_repo', return_value=repo):
            with pytest.raises(SecretNotFound):
                svc.update_secret_metadata(MagicMock(), uuid4(), {'name': 'x'})
