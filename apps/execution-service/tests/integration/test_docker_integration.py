"""Docker integration tests for execution-service.

These tests require a running Docker daemon. They are skipped automatically
when Docker is not available. Run with:
    pytest -m docker_integration

Or include in a CI pipeline that has Docker support.
"""

from __future__ import annotations

import uuid

import pytest

# Guard: skip all tests if docker is not importable or daemon not reachable
try:
    import docker
    _docker_client = docker.from_env()
    _docker_client.ping()
    _DOCKER_AVAILABLE = True
except Exception:
    _DOCKER_AVAILABLE = False

pytestmark = [
    pytest.mark.docker_integration,
    pytest.mark.skipif(not _DOCKER_AVAILABLE, reason="Docker daemon not available"),
]


@pytest.fixture
def docker_client():
    """Provide a Docker client, cleaned up after test."""
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture
def sandbox_backend(docker_client):
    """Provide a DockerSandboxBackend for integration tests."""
    from src.infrastructure.sandbox.docker_backend import DockerSandboxBackend
    return DockerSandboxBackend(docker_client=docker_client)


@pytest.fixture
def execution_backend(docker_client):
    """Provide a DockerExecutionBackend for integration tests."""
    from src.infrastructure.sandbox.docker_execution_backend import DockerExecutionBackend
    return DockerExecutionBackend(docker_client=docker_client)


class TestDockerSandboxLifecycle:
    def test_provision_and_terminate(self, sandbox_backend):
        """Provision a real sandbox container and terminate it."""
        sandbox_id = uuid.uuid4()

        info = sandbox_backend.provision(
            sandbox_id=sandbox_id,
            sandbox_type="container",
        )
        assert info.container_id
        assert sandbox_backend.is_alive(sandbox_id)

        sandbox_backend.terminate(sandbox_id)
        assert not sandbox_backend.is_alive(sandbox_id)

    def test_terminate_idempotent(self, sandbox_backend):
        """Terminating a non-existent sandbox should not raise."""
        sandbox_backend.terminate(uuid.uuid4())

    def test_is_alive_false_for_unknown(self, sandbox_backend):
        """is_alive returns False for a sandbox that was never provisioned."""
        assert not sandbox_backend.is_alive(uuid.uuid4())


class TestDockerToolExecution:
    def test_execute_simple_command(self, sandbox_backend, execution_backend):
        """Execute a simple command inside a real sandbox."""
        sandbox_id = uuid.uuid4()
        sandbox_backend.provision(sandbox_id=sandbox_id, sandbox_type="container")

        try:
            result = execution_backend.exec_in_sandbox(
                sandbox_id=sandbox_id,
                command=["echo", "hello"],
                timeout_s=10,
            )
            assert result.exit_code == 0
            assert "hello" in result.stdout
        finally:
            sandbox_backend.terminate(sandbox_id)

    def test_execute_nonzero_exit(self, sandbox_backend, execution_backend):
        """Non-zero exit code is captured correctly."""
        sandbox_id = uuid.uuid4()
        sandbox_backend.provision(sandbox_id=sandbox_id, sandbox_type="container")

        try:
            result = execution_backend.exec_in_sandbox(
                sandbox_id=sandbox_id,
                command=["sh", "-c", "exit 42"],
                timeout_s=10,
            )
            assert result.exit_code == 42
        finally:
            sandbox_backend.terminate(sandbox_id)

    def test_execute_timeout(self, sandbox_backend, execution_backend):
        """Timeout is enforced and raises TimeoutError."""
        sandbox_id = uuid.uuid4()
        sandbox_backend.provision(sandbox_id=sandbox_id, sandbox_type="container")

        try:
            with pytest.raises(TimeoutError):
                execution_backend.exec_in_sandbox(
                    sandbox_id=sandbox_id,
                    command=["sleep", "60"],
                    timeout_s=2,
                )
        finally:
            sandbox_backend.terminate(sandbox_id)

    def test_execute_container_not_found(self, execution_backend):
        """Executing in a non-existent container raises RuntimeError."""
        with pytest.raises(RuntimeError, match="not found"):
            execution_backend.exec_in_sandbox(
                sandbox_id=uuid.uuid4(),
                command=["echo", "test"],
                timeout_s=5,
            )

    def test_container_gone_after_terminate(self, sandbox_backend, execution_backend):
        """After termination, executing raises RuntimeError."""
        sandbox_id = uuid.uuid4()
        sandbox_backend.provision(sandbox_id=sandbox_id, sandbox_type="container")
        sandbox_backend.terminate(sandbox_id)

        with pytest.raises(RuntimeError, match="not found"):
            execution_backend.exec_in_sandbox(
                sandbox_id=sandbox_id,
                command=["echo", "test"],
                timeout_s=5,
            )
