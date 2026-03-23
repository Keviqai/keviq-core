"""No-op sandbox backend — used in hardened/cloud profiles without Docker socket.

All operations succeed silently; no actual containers are created.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from src.application.ports import BackendInfo, ExecResult, SandboxBackend, ToolExecutionBackend

logger = logging.getLogger(__name__)


class NoopSandboxBackend(SandboxBackend):
    """Sandbox backend that does nothing — for environments without Docker."""

    def provision(
        self,
        *,
        sandbox_id: UUID,
        sandbox_type: str,
        resource_limits: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> BackendInfo:
        logger.info("NOOP: provision sandbox %s (type=%s)", sandbox_id, sandbox_type)
        return BackendInfo(container_id=f"noop-{sandbox_id}", host="localhost", port=0)

    def terminate(self, sandbox_id: UUID) -> None:
        logger.info("NOOP: terminate sandbox %s", sandbox_id)

    def is_alive(self, sandbox_id: UUID) -> bool:
        # Noop sandboxes are always "alive" once provisioned
        return True


class NoopExecutionBackend(ToolExecutionBackend):
    """Execution backend that does nothing — for environments without Docker."""

    def exec_in_sandbox(
        self,
        *,
        sandbox_id: UUID,
        command: list[str],
        timeout_s: int = 30,
    ) -> ExecResult:
        logger.info("NOOP: exec in sandbox %s: %s", sandbox_id, command)
        return ExecResult(exit_code=0, stdout="", stderr="noop backend: execution disabled")
