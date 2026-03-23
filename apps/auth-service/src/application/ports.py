"""Application-layer port interfaces for auth-service.

Infrastructure implements these. No SQLAlchemy, no bcrypt, no jwt here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.user import User


class UserRepository(ABC):
    @abstractmethod
    def find_by_email(self, db, email: str) -> User | None: ...
    @abstractmethod
    def find_by_id(self, db, user_id: UUID) -> User | None: ...
    @abstractmethod
    def find_by_ids(self, db, user_ids: list[UUID]) -> list[User]: ...
    @abstractmethod
    def insert(self, db, user: User) -> User: ...
    @abstractmethod
    def update_last_active(self, db, user_id: UUID) -> None: ...
    @abstractmethod
    def find_and_touch(self, db, user_id: UUID) -> User | None: ...


class PasswordHasher(ABC):
    @abstractmethod
    def hash_password(self, plain: str) -> str: ...
    @abstractmethod
    def verify_password(self, plain: str, hashed: str) -> bool: ...


class JwtHandler(ABC):
    @abstractmethod
    def create_access_token(self, user_id: UUID, email: str) -> str: ...
    @abstractmethod
    def create_refresh_token(self, user_id: UUID) -> str: ...
    @abstractmethod
    def decode_token(self, token: str) -> dict: ...
