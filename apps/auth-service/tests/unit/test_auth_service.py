"""Unit tests for auth application service (login, register, refresh, get_me)."""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-for-unit-tests-only")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.domain.auth_errors import EmailAlreadyExists, InvalidCredentials, UserNotFound
from src.domain.user import User


def _make_user(**kwargs) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Test User",
        password_hash="$2b$12$fakehash",
        auth_provider="local",
        auth_provider_id=None,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        last_active_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    defaults.update(kwargs)
    return User(**defaults)


class TestLogin:
    """Login uses timing-safe dummy hash to prevent user enumeration."""

    def _run_login(self, email, password, user=None, password_ok=True):
        """Helper: patch bootstrap dependencies and call login()."""
        import src.application.auth_service as svc

        mock_repo = MagicMock()
        mock_repo.find_by_email.return_value = user
        mock_repo.update_last_active.return_value = None

        mock_hasher = MagicMock()
        mock_hasher.verify_password.return_value = password_ok

        mock_jwt = MagicMock()
        mock_jwt.create_access_token.return_value = "access_tok"
        mock_jwt.create_refresh_token.return_value = "refresh_tok"

        with patch.object(svc, "get_user_repo", return_value=mock_repo), \
             patch.object(svc, "get_password_hasher", return_value=mock_hasher), \
             patch.object(svc, "get_jwt_handler", return_value=mock_jwt):
            return svc.login(db=MagicMock(), email=email, password=password)

    def test_valid_credentials_returns_tokens(self):
        user = _make_user()
        result = self._run_login("test@example.com", "correct", user=user, password_ok=True)
        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"

    def test_wrong_password_raises_invalid_credentials(self):
        user = _make_user()
        with pytest.raises(InvalidCredentials):
            self._run_login("test@example.com", "wrong", user=user, password_ok=False)

    def test_unknown_email_raises_invalid_credentials(self):
        """User not found must still raise InvalidCredentials (not reveal existence)."""
        with pytest.raises(InvalidCredentials):
            self._run_login("nobody@example.com", "pass", user=None, password_ok=False)

    def test_oauth_user_without_password_hash_raises(self):
        """OAuth users have no password_hash — local login must fail."""
        oauth_user = _make_user(password_hash=None, auth_provider="google")
        with pytest.raises(InvalidCredentials):
            self._run_login("oauth@example.com", "any", user=oauth_user, password_ok=True)

    def test_timing_safe_dummy_hash_used_when_user_missing(self):
        """Even for missing users, verify_password is called (timing safety)."""
        import src.application.auth_service as svc

        mock_repo = MagicMock()
        mock_repo.find_by_email.return_value = None

        mock_hasher = MagicMock()
        mock_hasher.verify_password.return_value = False

        mock_jwt = MagicMock()

        with patch.object(svc, "get_user_repo", return_value=mock_repo), \
             patch.object(svc, "get_password_hasher", return_value=mock_hasher), \
             patch.object(svc, "get_jwt_handler", return_value=mock_jwt):
            with pytest.raises(InvalidCredentials):
                svc.login(db=MagicMock(), email="ghost@example.com", password="pass")

        # verify_password must be called with dummy hash (timing safety)
        mock_hasher.verify_password.assert_called_once()
        _, called_hash = mock_hasher.verify_password.call_args[0]
        assert called_hash.startswith("$2b$")  # bcrypt dummy hash


class TestRegister:
    def _run_register(self, email, display_name, password, existing_user=None):
        import src.application.auth_service as svc

        mock_repo = MagicMock()
        mock_repo.find_by_email.return_value = existing_user
        mock_repo.insert.return_value = None

        mock_hasher = MagicMock()
        mock_hasher.hash_password.return_value = "hashed"

        mock_jwt = MagicMock()
        mock_jwt.create_access_token.return_value = "access_tok"
        mock_jwt.create_refresh_token.return_value = "refresh_tok"

        with patch.object(svc, "get_user_repo", return_value=mock_repo), \
             patch.object(svc, "get_password_hasher", return_value=mock_hasher), \
             patch.object(svc, "get_jwt_handler", return_value=mock_jwt):
            return svc.register(db=MagicMock(), email=email, display_name=display_name, password=password)

    def test_new_user_returns_tokens_and_user(self):
        result = self._run_register("new@example.com", "Alice", "pass123")
        assert "access_token" in result
        assert "user" in result
        assert result["user"]["email"] == "new@example.com"

    def test_duplicate_email_raises(self):
        existing = _make_user(email="dup@example.com")
        with pytest.raises(EmailAlreadyExists):
            self._run_register("dup@example.com", "Alice", "pass", existing_user=existing)


class TestRefresh:
    def test_refresh_with_access_token_raises(self):
        """Passing access token as refresh token must raise InvalidCredentials."""
        import src.application.auth_service as svc

        mock_repo = MagicMock()
        mock_jwt = MagicMock()
        # Simulate decode returning an access token payload
        mock_jwt.decode_token.return_value = {"sub": str(uuid.uuid4()), "type": "access"}

        with patch.object(svc, "get_user_repo", return_value=mock_repo), \
             patch.object(svc, "get_jwt_handler", return_value=mock_jwt):
            with pytest.raises(InvalidCredentials):
                svc.refresh(db=MagicMock(), refresh_token="fake_token")


class TestGetMe:
    def test_unknown_user_raises(self):
        import src.application.auth_service as svc

        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        with patch.object(svc, "get_user_repo", return_value=mock_repo):
            with pytest.raises(UserNotFound):
                svc.get_me(db=MagicMock(), user_id=uuid.uuid4())

    def test_known_user_returns_dict(self):
        import src.application.auth_service as svc

        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user

        with patch.object(svc, "get_user_repo", return_value=mock_repo):
            result = svc.get_me(db=MagicMock(), user_id=user.id)

        assert result["id"] == str(user.id)
        assert result["email"] == user.email
