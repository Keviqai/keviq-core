"""Local filesystem storage backend for artifacts.

Storage paths follow PR44 naming convention:
  {storage_root}/workspaces/{workspace_id}/runs/{run_id}/artifacts/{artifact_id}/content

Workspace-isolated: each workspace has its own directory subtree.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.application.ports import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """Store artifact content on local filesystem.

    Args:
        storage_root: Base directory for all artifact content.
            Defaults to ARTIFACT_STORAGE_ROOT env var or ./artifact-data.
    """

    def __init__(self, storage_root: str | None = None):
        self._root = Path(
            storage_root
            or os.getenv("ARTIFACT_STORAGE_ROOT", "./artifact-data")
        ).resolve()

    def _full_path(self, storage_key: str) -> Path:
        """Resolve storage key to absolute path, preventing path traversal."""
        resolved = (self._root / storage_key).resolve()
        if not resolved.is_relative_to(self._root):
            raise ValueError(f"Storage key escapes root: {storage_key}")
        return resolved

    def write_content(self, storage_key: str, data: bytes) -> None:
        path = self._full_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("Wrote %d bytes to %s", len(data), storage_key)

    def read_content(self, storage_key: str) -> bytes:
        path = self._full_path(storage_key)
        if not path.is_file():
            raise FileNotFoundError(f"Content not found: {storage_key}")
        return path.read_bytes()

    def exists(self, storage_key: str) -> bool:
        return self._full_path(storage_key).is_file()

    def delete(self, storage_key: str) -> None:
        path = self._full_path(storage_key)
        if path.is_file():
            path.unlink()
            logger.info("Deleted %s", storage_key)
