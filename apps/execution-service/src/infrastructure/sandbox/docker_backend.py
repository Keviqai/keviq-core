"""Docker sandbox backend — provisions real Docker containers.

This backend creates, starts, and removes Docker containers as sandbox
execution boundaries. The container image and config come from internal
profiles only — never from user request input (G20-3).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import docker
from docker.errors import DockerException, NotFound

from src.application.ports import BackendInfo, SandboxBackend

from .profiles import get_profile

logger = logging.getLogger(__name__)

# Label prefix for sandbox metadata on containers.
_LABEL_PREFIX = "monaos.sandbox."


class DockerSandboxBackend(SandboxBackend):
    """Sandbox backend using local Docker daemon.

    Containers are created from internal profiles and labeled with
    sandbox metadata for identification and cleanup.
    """

    def __init__(self, *, docker_client: docker.DockerClient | None = None):
        self._client = docker_client or docker.from_env()

    def provision(
        self,
        *,
        sandbox_id: UUID,
        sandbox_type: str,
        resource_limits: dict[str, Any] | None = None,
        labels: dict[str, str] | None = None,
    ) -> BackendInfo:
        """Create and start a Docker container as a sandbox.

        Uses the internal profile for the given sandbox_type.
        Raises on failure (DockerException, image pull failure, etc.).
        """
        profile = get_profile(sandbox_type)

        container_labels = {
            f"{_LABEL_PREFIX}id": str(sandbox_id),
            f"{_LABEL_PREFIX}type": sandbox_type,
            f"{_LABEL_PREFIX}profile": profile.name,
        }
        if labels:
            for k, v in labels.items():
                container_labels[f"{_LABEL_PREFIX}{k}"] = v

        container_name = f"mona-sandbox-{sandbox_id}"

        logger.info(
            "Provisioning sandbox %s (image=%s, name=%s)",
            sandbox_id, profile.image, container_name,
        )

        container = self._client.containers.run(
            image=profile.image,
            command=profile.command,
            name=container_name,
            labels=container_labels,
            detach=True,
            mem_limit=profile.mem_limit,
            cpu_quota=profile.cpu_quota,
            network_mode=profile.network_mode,
            # Security: no host mounts, no privileged mode
            privileged=False,
            read_only=False,  # sandbox needs to write temp files
        )

        logger.info(
            "Sandbox %s container started (id=%s)",
            sandbox_id, container.short_id,
        )

        return BackendInfo(
            container_id=container.id,
            host="localhost",
        )

    def terminate(self, sandbox_id: UUID) -> None:
        """Stop and remove the sandbox container.

        Idempotent: does not raise if container is already gone.
        """
        container_name = f"mona-sandbox-{sandbox_id}"

        try:
            container = self._client.containers.get(container_name)
        except NotFound:
            logger.info(
                "Sandbox %s container already removed",
                sandbox_id,
            )
            return

        try:
            container.stop(timeout=10)
        except DockerException as exc:
            logger.warning(
                "Sandbox %s stop warning: %s", sandbox_id, exc,
            )

        try:
            container.remove(force=True)
        except NotFound:
            pass  # Already removed

        logger.info("Sandbox %s container removed", sandbox_id)

    def is_alive(self, sandbox_id: UUID) -> bool:
        """Check if the sandbox container is running."""
        container_name = f"mona-sandbox-{sandbox_id}"
        try:
            container = self._client.containers.get(container_name)
            return container.status == "running"
        except NotFound:
            return False

    def close(self) -> None:
        """Close the Docker client connection."""
        self._client.close()
