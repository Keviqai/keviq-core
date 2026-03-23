"""Unit tests for retry/backoff behaviour in orchestrator HTTP clients.

Verifies:
- Transient errors are retried with bounded attempts
- Permanent errors fail fast (no retry)
- Exhausted retries return appropriate results
- Timeout budget is propagated downstream
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
from uuid import uuid4

import pytest

# Mock internal auth before importing clients
_mock_auth_client = MagicMock()
_mock_auth_client.auth_headers.return_value = {"Authorization": "Bearer test"}


@pytest.fixture(autouse=True)
def _mock_auth():
    with patch("src.internal_auth.get_auth_client", return_value=_mock_auth_client):
        yield


# ── Helpers ──────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self):
        if self._json_data is not None:
            return self._json_data
        raise ValueError("No JSON data")


# ── HttpRuntimeClient retry ──────────────────────────────────────


class TestRuntimeClientRetry:
    def _make_client(self):
        from src.infrastructure.runtime_client import HttpRuntimeClient
        return HttpRuntimeClient(base_url="http://localhost:9999")

    def _dispatch_kwargs(self):
        return dict(
            agent_invocation_id=uuid4(),
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            correlation_id=uuid4(),
            agent_id="test-agent",
            model_alias="default",
            instruction="test",
            timeout_ms=30_000,
        )

    def test_retries_on_connect_error(self):
        import httpx
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("refused")
            return FakeResponse(200, json_data={"status": "completed"})

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.dispatch(**self._dispatch_kwargs())

        assert result.status == "completed"
        assert call_count == 3

    def test_no_retry_on_400(self):
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return FakeResponse(400, text="Bad Request")

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.dispatch(**self._dispatch_kwargs())

        assert result.status == "failed"
        assert result.error_code == "HTTP_400"
        assert call_count == 1  # No retry for 400

    def test_retries_on_503(self):
        import httpx
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return FakeResponse(503, text="Service Unavailable")
            return FakeResponse(200, json_data={"status": "completed"})

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.dispatch(**self._dispatch_kwargs())

        assert result.status == "completed"
        assert call_count == 2

    def test_exhausted_retries_return_last_error(self):
        import httpx
        client = self._make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ConnectError("refused"),
        ):
            result = client.dispatch(**self._dispatch_kwargs())

        assert result.status == "failed"
        assert result.error_code == "CONNECTION_ERROR"

    def test_timeout_budget_propagated(self):
        """Body should contain decremented timeout_ms."""
        client = self._make_client()
        captured_body = {}

        def capture_post(url, json=None, **kwargs):
            captured_body.update(json)
            return FakeResponse(200, json_data={"status": "completed"})

        with patch.object(client._client, "post", side_effect=capture_post):
            client.dispatch(
                **{**self._dispatch_kwargs(), "timeout_ms": 10_000},
            )

        # Budget should be less than original due to overhead
        assert captured_body["timeout_ms"] < 10_000
        assert captured_body["timeout_ms"] > 0


# ── HttpExecutionServiceClient retry ────────────────────────────


class TestExecutionServiceClientRetry:
    def _make_client(self):
        from src.infrastructure.execution_service_client import HttpExecutionServiceClient
        return HttpExecutionServiceClient(base_url="http://localhost:9999")

    def test_provision_retries_on_timeout(self):
        import httpx
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ReadTimeout("timed out")
            return FakeResponse(200, json_data={
                "sandbox_id": str(uuid4()),
                "sandbox_status": "ready",
            })

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.provision_sandbox(
                workspace_id=uuid4(),
                task_id=uuid4(),
                run_id=uuid4(),
                step_id=uuid4(),
                agent_invocation_id=uuid4(),
            )

        assert result.sandbox_status == "ready"
        assert call_count == 3

    def test_provision_retries_on_503(self):
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return FakeResponse(503, text="Service Unavailable")
            return FakeResponse(200, json_data={
                "sandbox_id": str(uuid4()),
                "sandbox_status": "ready",
            })

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.provision_sandbox(
                workspace_id=uuid4(),
                task_id=uuid4(),
                run_id=uuid4(),
                step_id=uuid4(),
                agent_invocation_id=uuid4(),
            )

        assert result.sandbox_status == "ready"
        assert call_count == 2

    def test_provision_no_retry_on_400(self):
        from src.infrastructure.execution_service_client import ExecutionServiceRejected

        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return FakeResponse(400, text="Bad Request")

        with patch.object(client._client, "post", side_effect=side_effect):
            with pytest.raises(ExecutionServiceRejected):
                client.provision_sandbox(
                    workspace_id=uuid4(),
                    task_id=uuid4(),
                    run_id=uuid4(),
                    step_id=uuid4(),
                    agent_invocation_id=uuid4(),
                )

        assert call_count == 1

    def test_terminate_retries_on_connect_error(self):
        import httpx
        client = self._make_client()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("refused")
            return FakeResponse(200, text="ok")

        with patch.object(client._client, "post", side_effect=side_effect):
            result = client.terminate_sandbox(uuid4(), reason="completed")

        assert result is True
        assert call_count == 2

    def test_terminate_returns_false_after_exhausted_retries(self):
        import httpx
        client = self._make_client()

        with patch.object(
            client._client, "post",
            side_effect=httpx.ConnectError("refused"),
        ):
            result = client.terminate_sandbox(uuid4(), reason="completed")

        assert result is False

    def test_execute_tool_timeout_budget_propagated(self):
        """execute_tool should propagate decremented timeout_ms."""
        client = self._make_client()
        captured_body = {}

        def capture_post(url, json=None, **kwargs):
            captured_body.update(json)
            return FakeResponse(200, json_data={
                "execution_id": str(uuid4()),
                "sandbox_id": str(uuid4()),
                "status": "completed",
            })

        with patch.object(client._client, "post", side_effect=capture_post):
            client.execute_tool(
                sandbox_id=uuid4(),
                tool_name="test",
                tool_input={},
                timeout_ms=10_000,
            )

        assert captured_body["timeout_ms"] < 10_000
        assert captured_body["timeout_ms"] > 0
