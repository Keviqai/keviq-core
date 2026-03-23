"""Unit tests for auth-service User domain entity."""

import uuid
from datetime import timezone

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.domain.user import User
from src.domain.auth_errors import EmailAlreadyExists, InvalidCredentials, UserNotFound


class TestUserCreateLocal:
    def test_email_is_lowercased(self):
        user = User.create_local("Test@Example.COM", "Name", "hash")
        assert user.email == "test@example.com"

    def test_email_is_stripped(self):
        user = User.create_local("  user@example.com  ", "Name", "hash")
        assert user.email == "user@example.com"

    def test_display_name_is_stripped(self):
        user = User.create_local("a@b.com", "  Alice  ", "hash")
        assert user.display_name == "Alice"

    def test_auth_provider_is_local(self):
        user = User.create_local("a@b.com", "Alice", "hash")
        assert user.auth_provider == "local"

    def test_auth_provider_id_is_none(self):
        user = User.create_local("a@b.com", "Alice", "hash")
        assert user.auth_provider_id is None

    def test_id_is_uuid(self):
        user = User.create_local("a@b.com", "Alice", "hash")
        assert isinstance(user.id, uuid.UUID)

    def test_unique_ids_per_user(self):
        u1 = User.create_local("a@b.com", "Alice", "hash")
        u2 = User.create_local("b@b.com", "Bob", "hash")
        assert u1.id != u2.id

    def test_timestamps_are_utc(self):
        user = User.create_local("a@b.com", "Alice", "hash")
        assert user.created_at.tzinfo == timezone.utc
        assert user.updated_at.tzinfo == timezone.utc
        assert user.last_active_at.tzinfo == timezone.utc

    def test_password_hash_stored(self):
        user = User.create_local("a@b.com", "Alice", "myhash")
        assert user.password_hash == "myhash"


class TestAuthErrors:
    def test_email_already_exists_message(self):
        err = EmailAlreadyExists("test@example.com")
        assert "test@example.com" in str(err)

    def test_invalid_credentials_is_exception(self):
        err = InvalidCredentials()
        assert isinstance(err, Exception)

    def test_user_not_found_message(self):
        err = UserNotFound("abc-123")
        assert "abc-123" in str(err)
