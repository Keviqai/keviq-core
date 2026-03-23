"""Unit tests for ArtifactServiceClient.

Tests HTTP client behavior, error handling, and request construction
using httpx mock transport — no real network calls.
"""

import json
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault('INTERNAL_AUTH_SECRET', 'test-secret')
os.environ.setdefault('SERVICE_NAME', 'agent-runtime')

from src.infrastructure.artifact_client import ArtifactServiceClient, ArtifactServiceError

# H1-S1: Mock internal auth globally for artifact_client tests
# The client calls get_auth_client().auth_headers() at request time — mock it
_mock_auth = MagicMock()
_mock_auth.auth_headers.return_value = {"X-Internal-Auth": "test-secret", "X-Service-Name": "agent-runtime"}


@pytest.fixture(autouse=True)
def _mock_internal_auth(monkeypatch):
    """Patch get_auth_client for all tests in this module."""
    monkeypatch.setattr('src.infrastructure.artifact_client.get_auth_client', lambda: _mock_auth)


# ── Helpers ──────────────────────────────────────────────────────

def _mock_transport(status: int = 200, body: dict | None = None, error: Exception | None = None):
    """Create a mock httpx transport that returns a fixed response or raises."""
    body = body or {}

    def handler(request: httpx.Request) -> httpx.Response:
        if error:
            raise error
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


def _make_client(status: int = 200, body: dict | None = None, error: Exception | None = None):
    """Create ArtifactServiceClient with mocked transport."""
    client = ArtifactServiceClient(base_url="http://artifact-service:8000")
    # Replace internal httpx client with mock
    client._client = httpx.Client(
        base_url="http://artifact-service:8000",
        transport=_mock_transport(status, body, error),
    )
    return client


# ── Constructor ──────────────────────────────────────────────────

class TestConstructor:
    def test_valid_http_url(self):
        client = ArtifactServiceClient(base_url="http://localhost:8000")
        client.close()

    def test_valid_https_url(self):
        client = ArtifactServiceClient(base_url="https://artifact.internal")
        client.close()

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="must start with"):
            ArtifactServiceClient(base_url="ftp://invalid")

    def test_trailing_slash_stripped(self):
        client = ArtifactServiceClient(base_url="http://localhost:8000/")
        assert client._base_url == "http://localhost:8000"
        client.close()


# ── register_artifact ───────────────────────────────────────────

class TestRegisterArtifact:
    def test_success(self):
        aid = str(uuid4())
        client = _make_client(body={"artifact_id": aid, "status": "REGISTERED"})

        result = client.register_artifact(
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            agent_invocation_id=uuid4(),
            name="test-output",
            artifact_type="model_output",
            root_type="agent_invocation",
            model_provider="openai",
            model_name_concrete="gpt-4o-2024-05-13",
            model_version_concrete=None,
            model_temperature=0.7,
            model_max_tokens=1000,
            run_config_hash=None,
            correlation_id=uuid4(),
        )

        assert result["artifact_id"] == aid
        client.close()

    def test_optional_fields_omitted_when_none(self):
        """Verify None optional fields are not sent in request body."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"artifact_id": str(uuid4())})

        client = ArtifactServiceClient(base_url="http://test:8000")
        client._client = httpx.Client(
            base_url="http://test:8000",
            transport=httpx.MockTransport(handler),
        )

        client.register_artifact(
            workspace_id=uuid4(),
            task_id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            agent_invocation_id=uuid4(),
            name="test",
            artifact_type="model_output",
            root_type="agent_invocation",
            model_provider=None,
            model_name_concrete=None,
            model_version_concrete=None,
            model_temperature=None,
            model_max_tokens=None,
            run_config_hash=None,
            correlation_id=None,
        )

        body = captured["body"]
        assert "model_provider" not in body
        assert "model_name_concrete" not in body
        assert "model_version_concrete" not in body
        assert "model_temperature" not in body
        assert "model_max_tokens" not in body
        assert "run_config_hash" not in body
        assert "correlation_id" not in body
        client.close()


# ── begin_writing ───────────────────────────────────────────────

class TestBeginWriting:
    def test_success(self):
        client = _make_client(body={"status": "WRITING"})
        result = client.begin_writing(
            uuid4(),
            workspace_id=uuid4(),
            storage_ref="inline://test",
            correlation_id=uuid4(),
        )
        assert result["status"] == "WRITING"
        client.close()


# ── finalize_artifact ───────────────────────────────────────────

class TestFinalizeArtifact:
    def test_success(self):
        client = _make_client(body={"status": "READY"})
        result = client.finalize_artifact(
            uuid4(),
            workspace_id=uuid4(),
            checksum="sha256:abc123",
            size_bytes=42,
            correlation_id=None,
        )
        assert result["status"] == "READY"
        client.close()


# ── fail_artifact ───────────────────────────────────────────────

class TestFailArtifact:
    def test_success(self):
        client = _make_client(body={"status": "FAILED"})
        result = client.fail_artifact(
            uuid4(),
            workspace_id=uuid4(),
            failure_reason="test failure",
            correlation_id=None,
        )
        assert result["status"] == "FAILED"
        client.close()


# ── Error handling ──────────────────────────────────────────────

class TestErrorHandling:
    def test_timeout_raises_retryable(self):
        client = _make_client(error=httpx.ReadTimeout("timed out"))
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.register_artifact(
                workspace_id=uuid4(), task_id=uuid4(), run_id=uuid4(),
                step_id=uuid4(), agent_invocation_id=uuid4(),
                name="t", artifact_type="model_output", root_type="agent_invocation",
                model_provider=None, model_name_concrete=None,
                model_version_concrete=None, model_temperature=None,
                model_max_tokens=None, run_config_hash=None, correlation_id=None,
            )
        assert exc_info.value.error_code == "TIMEOUT"
        assert exc_info.value.retryable is True
        client.close()

    def test_connect_error_raises_retryable(self):
        client = _make_client(error=httpx.ConnectError("refused"))
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.begin_writing(uuid4(), workspace_id=uuid4(), storage_ref="x", correlation_id=None)
        assert exc_info.value.error_code == "CONNECTION_ERROR"
        assert exc_info.value.retryable is True
        client.close()

    def test_http_error_raises_non_retryable(self):
        client = _make_client(error=httpx.DecodingError("bad"))
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.finalize_artifact(uuid4(), workspace_id=uuid4(), checksum="x", size_bytes=0, correlation_id=None)
        assert exc_info.value.error_code == "HTTP_ERROR"
        assert exc_info.value.retryable is False
        client.close()

    def test_4xx_non_retryable(self):
        client = _make_client(status=400, body={"detail": "bad request"})
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.fail_artifact(uuid4(), workspace_id=uuid4(), failure_reason="x", correlation_id=None)
        assert exc_info.value.error_code == "HTTP_400"
        assert exc_info.value.retryable is False
        client.close()

    def test_409_non_retryable(self):
        client = _make_client(status=409, body={"detail": "conflict"})
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.register_artifact(
                workspace_id=uuid4(), task_id=uuid4(), run_id=uuid4(),
                step_id=uuid4(), agent_invocation_id=uuid4(),
                name="t", artifact_type="model_output", root_type="agent_invocation",
                model_provider=None, model_name_concrete=None,
                model_version_concrete=None, model_temperature=None,
                model_max_tokens=None, run_config_hash=None, correlation_id=None,
            )
        assert exc_info.value.error_code == "HTTP_409"
        assert exc_info.value.retryable is False
        client.close()

    def test_429_retryable(self):
        client = _make_client(status=429, body={"detail": "rate limited"})
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.begin_writing(uuid4(), workspace_id=uuid4(), storage_ref="x", correlation_id=None)
        assert exc_info.value.error_code == "HTTP_429"
        assert exc_info.value.retryable is True
        client.close()

    def test_503_retryable(self):
        client = _make_client(status=503, body={"detail": "unavailable"})
        with pytest.raises(ArtifactServiceError) as exc_info:
            client.begin_writing(uuid4(), workspace_id=uuid4(), storage_ref="x", correlation_id=None)
        assert exc_info.value.error_code == "HTTP_503"
        assert exc_info.value.retryable is True
        client.close()

    def test_202_accepted(self):
        """202 is a valid success status code."""
        client = _make_client(status=202, body={"artifact_id": str(uuid4())})
        result = client.register_artifact(
            workspace_id=uuid4(), task_id=uuid4(), run_id=uuid4(),
            step_id=uuid4(), agent_invocation_id=uuid4(),
            name="t", artifact_type="model_output", root_type="agent_invocation",
            model_provider=None, model_name_concrete=None,
            model_version_concrete=None, model_temperature=None,
            model_max_tokens=None, run_config_hash=None, correlation_id=None,
        )
        assert "artifact_id" in result
        client.close()
