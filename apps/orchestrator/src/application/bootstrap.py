"""Application bootstrap — UoW factory and dispatcher provider.

The infrastructure layer configures the factories at startup.
The API layer calls get_uow() / get_dispatcher() without importing infrastructure.
"""

from __future__ import annotations

from typing import Any, Callable

from .ports import ExecutionDispatchPort, ExecutionServicePort, UnitOfWork

_uow_factory: Callable[[], UnitOfWork] | None = None
_session_factory: Any = None
_dispatcher: ExecutionDispatchPort | None = None
_execution_service: ExecutionServicePort | None = None


def configure_uow_factory(
    factory: Callable[[], UnitOfWork],
    session_factory: Any = None,
) -> None:
    """Set the UoW factory. Called once at startup by infrastructure."""
    global _uow_factory, _session_factory
    _uow_factory = factory
    _session_factory = session_factory


def configure_dispatcher(dispatcher: ExecutionDispatchPort) -> None:
    """Set the execution dispatcher. Called once at startup."""
    global _dispatcher
    _dispatcher = dispatcher


def get_uow() -> UnitOfWork:
    """Get a new UnitOfWork instance."""
    if _uow_factory is None:
        raise RuntimeError("UoW factory not configured — call configure_uow_factory() at startup")
    return _uow_factory()


def get_dispatcher() -> ExecutionDispatchPort:
    """Get the execution dispatcher."""
    if _dispatcher is None:
        raise RuntimeError("Dispatcher not configured — call configure_dispatcher() at startup")
    return _dispatcher


def configure_execution_service(service: ExecutionServicePort) -> None:
    """Set the execution-service client. Called once at startup."""
    global _execution_service
    _execution_service = service


def get_execution_service() -> ExecutionServicePort:
    """Get the execution-service client."""
    if _execution_service is None:
        raise RuntimeError(
            "Execution service not configured — call configure_execution_service() at startup"
        )
    return _execution_service


def get_session_factory() -> Any:
    """Get the raw session factory for operations that don't need full UoW."""
    if _session_factory is None:
        raise RuntimeError("Session factory not configured")
    return _session_factory
