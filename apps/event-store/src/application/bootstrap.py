"""Application bootstrap — repository factory provider.

The infrastructure layer configures the factory at startup.
The API layer calls get_repo() without importing infrastructure.
"""

from __future__ import annotations

from typing import Callable

from .ports import EventRepository

_repo_factory: Callable[[], EventRepository] | None = None


def configure_repo_factory(factory: Callable[[], EventRepository]) -> None:
    """Set the repository factory. Called once at startup by infrastructure."""
    global _repo_factory
    _repo_factory = factory


def get_repo() -> EventRepository:
    """Get a new EventRepository instance."""
    if _repo_factory is None:
        raise RuntimeError(
            "Repository factory not configured — call configure_repo_factory() at startup"
        )
    return _repo_factory()
