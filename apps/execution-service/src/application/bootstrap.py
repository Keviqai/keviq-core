"""Application bootstrap — UoW factory and sandbox backend provider.

The infrastructure layer configures the factories at startup.
The API layer calls get_uow() / get_backend() without importing infrastructure.
"""

from __future__ import annotations

from typing import Any, Callable

from .ports import SandboxBackend, ToolExecutionBackend, UnitOfWork

_uow_factory: Callable[[], UnitOfWork] | None = None
_session_factory: Any = None
_sandbox_backend: SandboxBackend | None = None
_execution_backend: ToolExecutionBackend | None = None


def configure_uow_factory(
    factory: Callable[[], UnitOfWork],
    session_factory: Any = None,
) -> None:
    """Set the UoW factory. Called once at startup by infrastructure."""
    global _uow_factory, _session_factory
    _uow_factory = factory
    _session_factory = session_factory


def configure_sandbox_backend(backend: SandboxBackend) -> None:
    """Set the sandbox backend. Called once at startup."""
    global _sandbox_backend
    _sandbox_backend = backend


def configure_execution_backend(backend: ToolExecutionBackend) -> None:
    """Set the tool execution backend. Called once at startup."""
    global _execution_backend
    _execution_backend = backend


def get_uow() -> UnitOfWork:
    """Get a new UnitOfWork instance."""
    if _uow_factory is None:
        raise RuntimeError("UoW factory not configured — call configure_uow_factory() at startup")
    return _uow_factory()


def get_sandbox_backend() -> SandboxBackend:
    """Get the sandbox backend."""
    if _sandbox_backend is None:
        raise RuntimeError("Sandbox backend not configured — call configure_sandbox_backend() at startup")
    return _sandbox_backend


def get_execution_backend() -> ToolExecutionBackend:
    """Get the tool execution backend."""
    if _execution_backend is None:
        raise RuntimeError("Execution backend not configured — call configure_execution_backend() at startup")
    return _execution_backend


def get_session_factory() -> Any:
    """Get the raw session factory for operations that don't need full UoW."""
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
