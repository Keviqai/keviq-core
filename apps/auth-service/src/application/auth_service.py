"""Auth application service — use cases for registration, login, token refresh."""

from __future__ import annotations

import uuid

from src.domain.auth_errors import EmailAlreadyExists, InvalidCredentials, UserNotFound
from src.domain.user import User
from src.infrastructure.db.user_repository import DuplicateEmailError

from .bootstrap import get_jwt_handler, get_password_hasher, get_user_repo


def register(db, email: str, display_name: str, password: str) -> dict:
    user_repo = get_user_repo()
    password_hasher = get_password_hasher()
    jwt_handler = get_jwt_handler()

    # Fast-path check (avoids expensive bcrypt if email already exists)
    existing = user_repo.find_by_email(db, email)
    if existing:
        raise EmailAlreadyExists(email)

    hashed = password_hasher.hash_password(password)
    user = User.create_local(email=email, display_name=display_name, password_hash=hashed)

    # Race-safe insert: uses INSERT ON CONFLICT to atomically prevent duplicates
    try:
        user_repo.insert_or_raise_duplicate(db, user)
    except DuplicateEmailError:
        raise EmailAlreadyExists(email)

    return {
        'user': _user_to_dict(user),
        'access_token': jwt_handler.create_access_token(user.id, user.email),
        'refresh_token': jwt_handler.create_refresh_token(user.id),
    }


_DUMMY_HASH = '$2b$12$LJ3m4ys3Lg2Fkl0aGrNMWeHNBFN5UVbGCu6yxOCf.VPxEMxWHKG2a'


def login(db, email: str, password: str) -> dict:
    user_repo = get_user_repo()
    password_hasher = get_password_hasher()
    jwt_handler = get_jwt_handler()

    user = user_repo.find_by_email(db, email)
    stored_hash = user.password_hash if (user and user.password_hash) else _DUMMY_HASH
    password_ok = password_hasher.verify_password(password, stored_hash)

    if not user or not user.password_hash or not password_ok:
        raise InvalidCredentials()

    user_repo.update_last_active(db, user.id)

    return {
        'access_token': jwt_handler.create_access_token(user.id, user.email),
        'refresh_token': jwt_handler.create_refresh_token(user.id),
    }


def refresh(db, refresh_token: str) -> dict:
    user_repo = get_user_repo()
    jwt_handler = get_jwt_handler()

    payload = jwt_handler.decode_token(refresh_token)
    if payload.get('type') != 'refresh':
        raise InvalidCredentials()

    user_id = uuid.UUID(payload['sub'])
    user = user_repo.find_and_touch(db, user_id)
    if not user:
        raise UserNotFound(str(user_id))

    return {
        'access_token': jwt_handler.create_access_token(user.id, user.email),
        'refresh_token': jwt_handler.create_refresh_token(user.id),
    }


def get_me(db, user_id: uuid.UUID) -> dict:
    user_repo = get_user_repo()

    user = user_repo.find_by_id(db, user_id)
    if not user:
        raise UserNotFound(str(user_id))
    return _user_to_dict(user)


def _user_to_dict(user: User) -> dict:
    return {
        'id': str(user.id),
        'email': user.email,
        'display_name': user.display_name,
        'auth_provider': user.auth_provider,
        'created_at': user.created_at.isoformat(),
        'last_active_at': user.last_active_at.isoformat(),
    }
