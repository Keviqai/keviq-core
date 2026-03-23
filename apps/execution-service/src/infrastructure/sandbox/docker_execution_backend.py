"""Docker execution backend — runs commands inside sandbox containers.

Uses Docker exec API to run commands as argv lists inside existing
sandbox containers.  Never uses shell=True or string concatenation.
"""

from __future__ import annotations

import logging
from uuid import UUID

import docker
from docker.errors import NotFound

from src.application.ports import ExecResult, ToolExecutionBackend

logger = logging.getLogger(__name__)


class DockerExecutionBackend(ToolExecutionBackend):
    """Execute commands inside Docker sandbox containers.

    Requires the sandbox container to already exist and be running
    (provisioned via DockerSandboxBackend).
    """

    def __init__(self, *, docker_client: docker.DockerClient | None = None):
        self._client = docker_client or docker.from_env()

    def exec_in_sandbox(
        self,
        *,
        sandbox_id: UUID,
        command: list[str],
        timeout_s: int = 30,
    ) -> ExecResult:
        """Execute a command inside a sandbox container.

        Args:
            sandbox_id: UUID of the sandbox (used to find container).
            command: Argv list — never a shell string.
            timeout_s: Execution timeout in seconds.

        Returns:
            ExecResult with exit_code, stdout, stderr.

        Raises:
            RuntimeError: If container not found or not running.
            TimeoutError: If execution exceeds timeout_s.
        """
        container_name = f"mona-sandbox-{sandbox_id}"

        try:
            container = self._client.containers.get(container_name)
        except NotFound:
            raise RuntimeError(
                f"Sandbox container {container_name} not found"
            )

        if container.status != "running":
            raise RuntimeError(
                f"Sandbox container {container_name} is not running "
                f"(status={container.status})"
            )

        logger.info(
            "Executing in sandbox %s (cmd_len=%d, timeout=%ds)",
            sandbox_id, len(command), timeout_s,
        )

        # Prepend `timeout` to enforce execution time limit inside container.
        # Exit code 124 = timed out (GNU coreutils timeout convention).
        timed_command = ["timeout", str(timeout_s)] + command

        # Docker exec with demux=True to separate stdout/stderr.
        # The environment dict is empty — tools don't get env vars from host.
        exec_result = container.exec_run(
            cmd=timed_command,
            demux=True,
            environment={},
        )

        # output can be None if no output, or (stdout, stderr) tuple with demux
        output = exec_result.output
        if output is None:
            stdout_bytes = b""
            stderr_bytes = b""
        else:
            stdout_bytes = output[0] if output[0] else b""
            stderr_bytes = output[1] if output[1] else b""

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # GNU timeout exits with 124 when the command times out.
        if exec_result.exit_code == 124:
            logger.warning(
                "Sandbox %s exec timed out after %ds", sandbox_id, timeout_s,
            )
            raise TimeoutError(
                f"Command timed out after {timeout_s}s in sandbox {sandbox_id}"
            )

        logger.info(
            "Sandbox %s exec finished (exit_code=%d, stdout_len=%d, stderr_len=%d)",
            sandbox_id, exec_result.exit_code, len(stdout), len(stderr),
        )

        return ExecResult(
            exit_code=exec_result.exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def close(self) -> None:
        """Close the Docker client connection."""
        self._client.close()
