"""User repository — database access for identity_core.users."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.domain.user import User

SCHEMA = 'identity_core'


def _row_to_user(row) -> User:
    return User(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        password_hash=row.password_hash,
        auth_provider=row.auth_provider,
        auth_provider_id=row.auth_provider_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_active_at=row.last_active_at,
    )


def find_by_email(db: Session, email: str) -> User | None:
    row = db.execute(
        text(f'SELECT id, email, display_name, password_hash, auth_provider, auth_provider_id, created_at, updated_at, last_active_at FROM {SCHEMA}.users WHERE email = :email'),
        {'email': email.lower().strip()},
    ).fetchone()
    return _row_to_user(row) if row else None


def find_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    row = db.execute(
        text(f'SELECT id, email, display_name, password_hash, auth_provider, auth_provider_id, created_at, updated_at, last_active_at FROM {SCHEMA}.users WHERE id = :id'),
        {'id': str(user_id)},
    ).fetchone()
    return _row_to_user(row) if row else None


def find_by_ids(db: Session, user_ids: list[uuid.UUID]) -> list[User]:
    """Batch lookup by a list of UUIDs — single SQL query, no N+1."""
    if not user_ids:
        return []
    id_strings = [str(uid) for uid in user_ids]
    rows = db.execute(
        text(f'SELECT id, email, display_name, password_hash, auth_provider, auth_provider_id, created_at, updated_at, last_active_at FROM {SCHEMA}.users WHERE id = ANY(CAST(:ids AS uuid[]))'),
        {'ids': id_strings},
    ).fetchall()
    return [_row_to_user(row) for row in rows]


def insert(db: Session, user: User) -> User:
    """Insert a new user. Raises IntegrityError on duplicate email."""
    db.execute(
        text(f"""
            INSERT INTO {SCHEMA}.users
                (id, email, display_name, password_hash, auth_provider,
                 auth_provider_id, created_at, updated_at, last_active_at)
            VALUES
                (:id, :email, :display_name, :password_hash, :auth_provider,
                 :auth_provider_id, :created_at, :updated_at, :last_active_at)
        """),
        {
            'id': str(user.id),
            'email': user.email,
            'display_name': user.display_name,
            'password_hash': user.password_hash,
            'auth_provider': user.auth_provider,
            'auth_provider_id': user.auth_provider_id,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
            'last_active_at': user.last_active_at,
        },
    )
    db.commit()
    return user


def insert_or_raise_duplicate(db: Session, user: User) -> User:
    """Insert a new user with race-safe duplicate detection.

    Uses INSERT ... ON CONFLICT to atomically check uniqueness.
    Returns the user on success, raises IntegrityError-equivalent
    EmailAlreadyExists if email already taken.
    """
    from sqlalchemy import text as sa_text
    result = db.execute(
        sa_text(f"""
            INSERT INTO {SCHEMA}.users
                (id, email, display_name, password_hash, auth_provider,
                 auth_provider_id, created_at, updated_at, last_active_at)
            VALUES
                (:id, :email, :display_name, :password_hash, :auth_provider,
                 :auth_provider_id, :created_at, :updated_at, :last_active_at)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
        """),
        {
            'id': str(user.id),
            'email': user.email,
            'display_name': user.display_name,
            'password_hash': user.password_hash,
            'auth_provider': user.auth_provider,
            'auth_provider_id': user.auth_provider_id,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
            'last_active_at': user.last_active_at,
        },
    )
    row = result.fetchone()
    db.commit()
    if row is None:
        raise DuplicateEmailError(user.email)
    return user


class DuplicateEmailError(Exception):
    """Raised when INSERT ON CONFLICT detects a duplicate email."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Duplicate email: {email}")


def update_last_active(db: Session, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        text(f'UPDATE {SCHEMA}.users SET last_active_at = :now, updated_at = :now WHERE id = :id'),
        {'now': now, 'id': str(user_id)},
    )
    db.commit()


def find_and_touch(db: Session, user_id: uuid.UUID) -> User | None:
    """Find user by id and update last_active_at in a single round-trip."""
    now = datetime.now(timezone.utc)
    row = db.execute(
        text(f"""
            UPDATE {SCHEMA}.users
            SET last_active_at = :now, updated_at = :now
            WHERE id = :id
            RETURNING id, email, display_name, password_hash, auth_provider,
                      auth_provider_id, created_at, updated_at, last_active_at
        """),
        {'now': now, 'id': str(user_id)},
    ).fetchone()
    db.commit()
    return _row_to_user(row) if row else None


from src.application.ports import UserRepository as UserRepositoryPort


class UserRepositoryAdapter(UserRepositoryPort):
    """Infrastructure adapter implementing UserRepository port."""

    def find_by_email(self, db, email: str):
        return find_by_email(db, email)

    def find_by_id(self, db, user_id):
        return find_by_id(db, user_id)

    def find_by_ids(self, db, user_ids):
        return find_by_ids(db, user_ids)

    def insert(self, db, user):
        return insert(db, user)

    def insert_or_raise_duplicate(self, db, user):
        return insert_or_raise_duplicate(db, user)

    def update_last_active(self, db, user_id):
        return update_last_active(db, user_id)

    def find_and_touch(self, db, user_id):
        return find_and_touch(db, user_id)
