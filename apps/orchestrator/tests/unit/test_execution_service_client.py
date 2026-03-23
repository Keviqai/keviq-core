"""Unit tests for orchestrator execution-service client robustness.

Tests that malformed/non-JSON responses are handled safely
and produce clear exception types.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.execution_service_client import (
    ExecutionServiceProtocolError,
    ExecutionServiceRejected,
    ExecutionServiceUnavailable,
    HttpExecutionServiceClient,
)


# ── Helpers ──────────────────────────────────────────────────


class FakeResponse:
    """Minimal httpx.Response stand-in for unit testing."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: dict | None = None,
        text: str = "",
        *,
        json_raises: bool = False,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("No JSON")
        if self._json_data is not None:
            return self._json_data
        raise ValueError("No JSON data")


def _make_client() -> HttpExecutionServiceClient:
    return HttpExecutionServiceClient(base_url="http://localhost:9999")


# ── provision_sandbox robustness ─────────────────────────────


class TestProvisionSandboxRobustness:
    def test_non_json_response_raises_protocol_error(self):
        client = _make_client()
        fake_resp = FakeResponse(
            status_code=200,
            text="<html>not json</html>",
            json_raises=True,
        )

        with patch.object(client._client, "post", return_value=fake_resp):
            with pytest.raises(ExecutionServiceProtocolError, match="non-JSON"):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )

    def test_missing_sandbox_id_raises_protocol_error(self):
        client = _make_client()
        fake_resp = FakeResponse(
            status_code=200,
            json_data={"status": "ready"},  # missing sandbox_id
        )

        with patch.object(client._client, "post", return_value=fake_resp):
            with pytest.raises(ExecutionServiceProtocolError, match="missing required"):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )

    def test_http_error_raises_unavailable(self):
        import httpx
        client = _make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(ExecutionServiceUnavailable, match="provision"):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )

    def test_timeout_raises_unavailable(self):
        import httpx
        client = _make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            with pytest.raises(ExecutionServiceUnavailable, match="timed out"):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )

    def test_non_200_raises_rejected(self):
        client = _make_client()
        fake_resp = FakeResponse(status_code=500, text="Internal Server Error")

        with patch.object(client._client, "post", return_value=fake_resp):
            with pytest.raises(ExecutionServiceRejected, match="HTTP 500"):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )


# ── get_execution robustness ─────────────────────────────────


class TestGetExecutionRobustness:
    def test_non_json_response_raises_protocol_error(self):
        client = _make_client()
        fake_resp = FakeResponse(
            status_code=200,
            text="not json",
            json_raises=True,
        )

        with patch.object(client._client, "get", return_value=fake_resp):
            with pytest.raises(ExecutionServiceProtocolError, match="non-JSON"):
                client.get_execution(uuid4())

    def test_http_error_raises_unavailable(self):
        import httpx
        client = _make_client()

        with patch.object(
            client._client, "get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(ExecutionServiceUnavailable):
                client.get_execution(uuid4())

    def test_non_200_raises_rejected(self):
        client = _make_client()
        fake_resp = FakeResponse(status_code=404, text="Not Found")

        with patch.object(client._client, "get", return_value=fake_resp):
            with pytest.raises(ExecutionServiceRejected, match="HTTP 404"):
                client.get_execution(uuid4())


# ── terminate_sandbox bool return ────────────────────────────


class TestTerminateSandboxBoolReturn:
    def test_returns_true_on_200(self):
        client = _make_client()
        fake_resp = FakeResponse(status_code=200, text="ok")

        with patch.object(client._client, "post", return_value=fake_resp):
            result = client.terminate_sandbox(uuid4(), reason="completed")

        assert result is True

    def test_returns_true_on_202(self):
        client = _make_client()
        fake_resp = FakeResponse(status_code=202, text="accepted")

        with patch.object(client._client, "post", return_value=fake_resp):
            result = client.terminate_sandbox(uuid4(), reason="completed")

        assert result is True

    def test_returns_false_on_500(self):
        client = _make_client()
        fake_resp = FakeResponse(status_code=500, text="Internal Server Error")

        with patch.object(client._client, "post", return_value=fake_resp):
            result = client.terminate_sandbox(uuid4(), reason="error")

        assert result is False

    def test_returns_false_on_http_error(self):
        import httpx
        client = _make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = client.terminate_sandbox(uuid4(), reason="completed")

        assert result is False

    def test_returns_false_on_timeout(self):
        import httpx
        client = _make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            result = client.terminate_sandbox(uuid4(), reason="timeout")

        assert result is False
