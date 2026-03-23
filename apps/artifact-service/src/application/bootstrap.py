"""Application bootstrap — UoW factory provider.

The infrastructure layer configures the factory at startup.
The API layer calls get_uow() without importing infrastructure.
"""

from __future__ import annotations

from typing import Any, Callable

from .ports import StorageBackend, UnitOfWork

_uow_factory: Callable[[], UnitOfWork] | None = None
_session_factory: Any = None
_storage_backend: StorageBackend | None = None


def configure_uow_factory(
    factory: Callable[[], UnitOfWork],
    session_factory: Any = None,
) -> None:
    """Set the UoW factory. Called once at startup by infrastructure."""
    global _uow_factory, _session_factory
    _uow_factory = factory
    _session_factory = session_factory


def configure_storage_backend(backend: StorageBackend) -> None:
    """Set the storage backend. Called once at startup by infrastructure."""
    global _storage_backend
    _storage_backend = backend


def get_uow() -> UnitOfWork:
    """Get a new UnitOfWork instance."""
    if _uow_factory is None:
        raise RuntimeError(
            "UoW factory not configured — call configure_uow_factory() at startup"
        )
    return _uow_factory()


def get_session_factory() -> Any:
    """Get the raw session factory for operations that don't need full UoW."""
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend."""
    if _storage_backend is None:
        raise RuntimeError(
            "Storage backend not configured — call configure_storage_backend() at startup"
        )
    return _storage_backend
