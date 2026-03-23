"""Artifact-service HTTP client.

Implements ArtifactServicePort by calling artifact-service internal API.
Only this file uses httpx — application layer stays transport-agnostic.

Retry policy: transient errors (timeout, connection, 429/5xx) are retried
with exponential backoff.  Permanent errors fail immediately.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from resilience import RetryPolicy, retry_with_backoff
from src.application.ports import ArtifactServicePort
from src.internal_auth import get_auth_client

logger = logging.getLogger(__name__)

_ARTIFACT_RETRY = RetryPolicy(max_attempts=3, base_delay_s=0.5, max_delay_s=5.0)


class ArtifactServiceError(Exception):
    """Error from artifact-service call."""

    def __init__(self, error_code: str, message: str, retryable: bool = False):
        self.error_code = error_code
        self.retryable = retryable
        super().__init__(message)


class ArtifactServiceClient(ArtifactServicePort):
    """HTTP client for artifact-service."""

    def __init__(self, *, base_url: str):
        if not base_url.startswith(("https://", "http://")):
            raise ValueError(f"base_url must start with https:// or http://, got: {base_url!r}")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

    def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        self._client.close()

    def register_artifact(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        step_id: UUID,
        agent_invocation_id: UUID,
        name: str,
        artifact_type: str,
        root_type: str,
        mime_type: str | None = None,
        model_provider: str | None,
        model_name_concrete: str | None,
        model_version_concrete: str | None,
        model_temperature: float | None,
        model_max_tokens: int | None,
        run_config_hash: str | None,
        correlation_id: UUID | None,
    ) -> dict:
        """Register artifact via POST /internal/v1/artifacts/register."""
        body: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "task_id": str(task_id),
            "run_id": str(run_id),
            "step_id": str(step_id),
            "agent_invocation_id": str(agent_invocation_id),
            "name": name,
            "artifact_type": artifact_type,
            "root_type": root_type,
        }
        if mime_type:
            body["mime_type"] = mime_type
        if model_provider:
            body["model_provider"] = model_provider
        if model_name_concrete:
            body["model_name_concrete"] = model_name_concrete
        if model_version_concrete:
            body["model_version_concrete"] = model_version_concrete
        if model_temperature is not None:
            body["model_temperature"] = model_temperature
        if model_max_tokens is not None:
            body["model_max_tokens"] = model_max_tokens
        if run_config_hash:
            body["run_config_hash"] = run_config_hash
        if correlation_id:
            body["correlation_id"] = str(correlation_id)

        return self._post("/internal/v1/artifacts/register", body)

    def begin_writing(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        storage_ref: str,
        correlation_id: UUID | None,
    ) -> dict:
        """Transition to WRITING via POST /internal/v1/artifacts/{id}/begin-writing."""
        body: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "storage_ref": storage_ref,
        }
        if correlation_id:
            body["correlation_id"] = str(correlation_id)

        return self._post(f"/internal/v1/artifacts/{artifact_id}/begin-writing", body)

    def write_content(self, artifact_id: UUID, content: bytes) -> dict:
        """Write content bytes to artifact via POST /internal/v1/artifacts/{id}/content."""
        import base64
        body = {
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        return self._post(f"/internal/v1/artifacts/{artifact_id}/content", body)

    def finalize_artifact(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        checksum: str,
        size_bytes: int,
        content_base64: str | None = None,
        correlation_id: UUID | None = None,
    ) -> dict:
        """Finalize artifact via POST /internal/v1/artifacts/{id}/finalize."""
        body: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "checksum": checksum,
            "size_bytes": size_bytes,
        }
        if content_base64:
            body["content_base64"] = content_base64
        if correlation_id:
            body["correlation_id"] = str(correlation_id)

        return self._post(f"/internal/v1/artifacts/{artifact_id}/finalize", body)

    def fail_artifact(
        self,
        artifact_id: UUID,
        *,
        workspace_id: UUID,
        failure_reason: str | None,
        correlation_id: UUID | None,
    ) -> dict:
        """Mark artifact as FAILED via POST /internal/v1/artifacts/{id}/fail."""
        body: dict[str, Any] = {
            "workspace_id": str(workspace_id),
        }
        if failure_reason:
            body["failure_reason"] = failure_reason
        if correlation_id:
            body["correlation_id"] = str(correlation_id)

        return self._post(f"/internal/v1/artifacts/{artifact_id}/fail", body)

    def _post(self, path: str, body: dict) -> dict:
        """Execute POST request with standard error handling and retry."""

        def _attempt() -> dict:
            try:
                resp = self._client.post(
                    path,
                    json=body,
                    headers=get_auth_client().auth_headers("artifact-service"),
                    timeout=30.0,
                )
            except httpx.TimeoutException as exc:
                raise ArtifactServiceError(
                    "TIMEOUT", f"Artifact-service timed out: {exc}", retryable=True,
                ) from exc
            except httpx.ConnectError as exc:
                raise ArtifactServiceError(
                    "CONNECTION_ERROR", f"Cannot reach artifact-service: {exc}", retryable=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise ArtifactServiceError(
                    "HTTP_ERROR", str(exc), retryable=False,
                ) from exc

            if resp.status_code not in (200, 202):
                detail = resp.text[:500]
                try:
                    resp_body = resp.json()
                    if isinstance(resp_body, dict):
                        detail = resp_body.get("detail", detail)
                except (ValueError, KeyError, AttributeError):
                    pass
                raise ArtifactServiceError(
                    f"HTTP_{resp.status_code}",
                    str(detail),
                    retryable=resp.status_code in (429, 502, 503, 504),
                )

            return resp.json()

        return retry_with_backoff(
            _attempt,
            _ARTIFACT_RETRY,
            is_retryable=lambda exc: isinstance(exc, ArtifactServiceError) and exc.retryable,
            operation_name=f"artifact_service:{path}",
        )
