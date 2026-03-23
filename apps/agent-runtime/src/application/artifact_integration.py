"""Artifact integration — best-effort artifact creation after invocation completion.

Extracted from execution_handler.py to keep file sizes under 300 lines.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any
from uuid import UUID

from src.application.ports import ArtifactServicePort
from src.domain.execution_contracts import ExecutionRequest

logger = logging.getLogger(__name__)


def create_artifact_best_effort(
    *,
    artifact_service: ArtifactServicePort | None,
    request: ExecutionRequest,
    output_text: str,
    gw_response: dict[str, Any],
) -> UUID | None:
    """Register, write, and finalize an artifact. Best-effort — failures are logged, not raised.

    Returns artifact_id on success, None on failure or when artifact_service is not configured.
    """
    if artifact_service is None:
        return None

    if not output_text or not output_text.strip():
        logger.info(
            "No output text for invocation %s — skipping artifact creation",
            request.agent_invocation_id,
        )
        return None

    artifact_id: UUID | None = None
    try:
        # Register
        reg = artifact_service.register_artifact(
            workspace_id=request.workspace_id,
            task_id=request.task_id,
            run_id=request.run_id,
            step_id=request.step_id,
            agent_invocation_id=request.agent_invocation_id,
            name=(
                f"{request.instruction[:80]} — output"
                if request.instruction
                else f"invocation-{request.agent_invocation_id}-output"
            ),
            artifact_type="model_output",
            mime_type="text/plain",
            root_type="generated",
            model_provider=gw_response.get("provider_name", "unknown"),
            model_name_concrete=gw_response.get(
                "model_concrete", request.model_profile.model_alias,
            ),
            model_version_concrete=gw_response.get(
                "model_concrete", request.model_profile.model_alias,
            ),
            model_temperature=request.model_profile.temperature,
            model_max_tokens=request.model_profile.max_tokens,
            run_config_hash=hashlib.sha256(
                f"{request.model_profile.model_alias}:{request.model_profile.temperature}:{request.model_profile.max_tokens}".encode()
            ).hexdigest(),
            correlation_id=request.correlation_id,
        )
        artifact_id = UUID(reg["artifact_id"])

        # Begin writing — use file-based storage key
        storage_ref = (
            f"workspaces/{request.workspace_id}/runs/{request.run_id}"
            f"/artifacts/{artifact_id}/content"
        )
        artifact_service.begin_writing(
            artifact_id,
            workspace_id=request.workspace_id,
            storage_ref=storage_ref,
            correlation_id=request.correlation_id,
        )

        # Finalize with content + checksum
        content_bytes = output_text.encode("utf-8")
        checksum = hashlib.sha256(content_bytes).hexdigest()
        artifact_service.finalize_artifact(
            artifact_id,
            workspace_id=request.workspace_id,
            checksum=checksum,
            size_bytes=len(content_bytes),
            content_base64=base64.b64encode(content_bytes).decode("ascii"),
            correlation_id=request.correlation_id,
        )

        logger.info(
            "Artifact %s created for invocation %s",
            artifact_id,
            request.agent_invocation_id,
        )
        return artifact_id

    except Exception:
        logger.warning(
            "Best-effort artifact creation failed for invocation %s",
            request.agent_invocation_id,
            exc_info=True,
        )
        # Attempt to mark artifact as failed if we got an ID
        if artifact_id is not None:
            try:
                artifact_service.fail_artifact(
                    artifact_id,
                    workspace_id=request.workspace_id,
                    failure_reason="Artifact creation failed during runtime integration",
                    correlation_id=request.correlation_id,
                )
            except Exception:
                logger.debug(
                    "Failed to mark artifact %s as FAILED",
                    artifact_id,
                    exc_info=True,
                )
        return None
