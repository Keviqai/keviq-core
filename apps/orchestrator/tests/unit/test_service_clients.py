"""Unit tests for orchestrator service_clients.py — artifact validation path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

ARTIFACT_ID = UUID("b8e4f5a0-1234-4abc-8def-000011112222")
WORKSPACE_ID = UUID("1fce5e07-acd3-4e0b-bd46-21c759066564")
OTHER_WS_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-111122223333")


def _mock_response(status_code: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    if body is not None:
        resp.json.return_value = body
    return resp


# ── validate_artifact_in_workspace ────────────────────────────


class TestValidateArtifactInWorkspace:
    """Tests for validate_artifact_in_workspace — the approval creation guard."""

    def test_success_returns_true(self):
        """200 from artifact-service means artifact belongs to workspace."""
        artifact_body = {
            "id": str(ARTIFACT_ID),
            "workspace_id": str(WORKSPACE_ID),
            "name": "Test Report",
            "artifact_status": "ready",
        }
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(200, artifact_body)

            from src.infrastructure.service_clients import validate_artifact_in_workspace

            result = validate_artifact_in_workspace(ARTIFACT_ID, WORKSPACE_ID)

        assert result is True
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["params"] == {"workspace_id": str(WORKSPACE_ID)}

    def test_cross_workspace_returns_false(self):
        """404 from artifact-service (workspace mismatch) returns False."""
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(404)

            from src.infrastructure.service_clients import validate_artifact_in_workspace

            result = validate_artifact_in_workspace(ARTIFACT_ID, OTHER_WS_ID)

        assert result is False

    def test_upstream_error_returns_false(self):
        """Non-200/404 from artifact-service is fail-closed (returns False)."""
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(403)

            from src.infrastructure.service_clients import validate_artifact_in_workspace

            result = validate_artifact_in_workspace(ARTIFACT_ID, WORKSPACE_ID)

        assert result is False

    def test_connection_error_returns_false(self):
        """Network exception is fail-closed (returns False)."""
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch(
                "src.infrastructure.service_clients.httpx.get",
                side_effect=Exception("connection refused"),
            ),
        ):
            mock_auth.return_value.auth_headers.return_value = {}

            from src.infrastructure.service_clients import validate_artifact_in_workspace

            result = validate_artifact_in_workspace(ARTIFACT_ID, WORKSPACE_ID)

        assert result is False

    def test_no_url_configured_returns_true(self):
        """Empty ARTIFACT_SERVICE_URL skips validation (dev/test environments)."""
        with patch("src.infrastructure.service_clients._ARTIFACT_SERVICE_URL", ""):
            from src.infrastructure.service_clients import validate_artifact_in_workspace

            result = validate_artifact_in_workspace(ARTIFACT_ID, WORKSPACE_ID)

        assert result is True

    def test_workspace_id_sent_as_query_param(self):
        """workspace_id must be sent as query param, not just used for comparison."""
        artifact_body = {"id": str(ARTIFACT_ID), "workspace_id": str(WORKSPACE_ID)}
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(200, artifact_body)

            from src.infrastructure.service_clients import validate_artifact_in_workspace

            validate_artifact_in_workspace(ARTIFACT_ID, WORKSPACE_ID)

            _, kwargs = mock_get.call_args
            assert "params" in kwargs, "workspace_id must be sent as query param"
            assert kwargs["params"].get("workspace_id") == str(WORKSPACE_ID)


# ── get_artifact_name ──────────────────────────────────────────


class TestGetArtifactName:
    def test_returns_name_on_success(self):
        body = {"id": str(ARTIFACT_ID), "workspace_id": str(WORKSPACE_ID), "name": "My Report"}
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(200, body)

            from src.infrastructure.service_clients import get_artifact_name

            result = get_artifact_name(ARTIFACT_ID, WORKSPACE_ID)

        assert result == "My Report"
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["workspace_id"] == str(WORKSPACE_ID)

    def test_returns_none_on_non_200(self):
        with (
            patch(
                "src.infrastructure.service_clients._ARTIFACT_SERVICE_URL",
                "http://artifact-service:8000",
            ),
            patch("src.infrastructure.service_clients.get_auth_client") as mock_auth,
            patch("src.infrastructure.service_clients.httpx.get") as mock_get,
        ):
            mock_auth.return_value.auth_headers.return_value = {}
            mock_get.return_value = _mock_response(404)

            from src.infrastructure.service_clients import get_artifact_name

            result = get_artifact_name(ARTIFACT_ID, WORKSPACE_ID)

        assert result is None
