"""Unit tests for JWT token creation and verification."""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Must set before importing jwt_handler (module-level secret check)
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret-for-unit-tests-only")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import jwt as pyjwt
from src.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    JwtHandlerAdapter,
    SECRET_KEY,
    ALGORITHM,
)


class TestCreateAccessToken:
    def test_returns_decodable_token(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        payload = decode_token(token)
        assert payload["sub"] == str(uid)

    def test_email_in_payload(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        payload = decode_token(token)
        assert payload["email"] == "user@example.com"

    def test_type_is_access(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_token_expires(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        payload = decode_token(token)
        assert "exp" in payload


class TestCreateRefreshToken:
    def test_type_is_refresh(self):
        uid = uuid.uuid4()
        token = create_refresh_token(uid)
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_sub_matches_user_id(self):
        uid = uuid.uuid4()
        token = create_refresh_token(uid)
        payload = decode_token(token)
        assert payload["sub"] == str(uid)

    def test_no_email_in_refresh(self):
        uid = uuid.uuid4()
        token = create_refresh_token(uid)
        payload = decode_token(token)
        assert "email" not in payload


class TestDecodeToken:
    def test_invalid_signature_raises(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, "user@example.com")
        # Tamper the signature
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsig"
        with pytest.raises(pyjwt.PyJWTError):
            decode_token(tampered)

    def test_expired_token_raises(self):
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(expired_token)

    def test_wrong_secret_raises(self):
        uid = uuid.uuid4()
        token = pyjwt.encode(
            {"sub": str(uid), "type": "access"},
            "wrong-secret",
            algorithm=ALGORITHM,
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_token(token)


class TestJwtHandlerAdapter:
    def setup_method(self):
        self.adapter = JwtHandlerAdapter()

    def test_access_token_round_trip(self):
        uid = uuid.uuid4()
        token = self.adapter.create_access_token(uid, "a@b.com")
        payload = self.adapter.decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "access"

    def test_refresh_token_round_trip(self):
        uid = uuid.uuid4()
        token = self.adapter.create_refresh_token(uid)
        payload = self.adapter.decode_token(token)
        assert payload["type"] == "refresh"
