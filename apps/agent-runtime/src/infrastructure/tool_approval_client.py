"""HTTP client for requesting tool approvals from orchestrator.

Implements ToolApprovalServicePort. Calls POST /internal/v1/tool-approvals.
Fail-open: if orchestrator is unreachable, logs warning and returns None
(caller should treat as ALLOW to avoid blocking execution on infra failure).
"""

from __future__ import annotations

import json
import logging
import os
from uuid import UUID

import httpx

from src.application.ports import ToolApprovalServicePort

logger = logging.getLogger(__name__)

_ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "")
_INTERNAL_AUTH_SECRET = os.getenv("INTERNAL_AUTH_SECRET", "")
_SERVICE_NAME = os.getenv("SERVICE_NAME", "agent-runtime")
_TIMEOUT_SECONDS = 10


class HttpToolApprovalClient(ToolApprovalServicePort):
    """HTTP client for orchestrator tool-approval endpoint."""

    def request_tool_approval(
        self,
        *,
        workspace_id: UUID,
        invocation_id: UUID,
        run_id: UUID,
        task_id: UUID,
        tool_name: str,
        arguments_preview: str,
        risk_reason: str,
    ) -> dict:
        """Request tool approval from orchestrator.

        Returns response dict with approval_id on success.
        Raises RuntimeError if orchestrator is not configured or returns error.
        """
        if not _ORCHESTRATOR_URL:
            raise RuntimeError("ORCHESTRATOR_URL not configured — cannot request tool approval")

        url = f"{_ORCHESTRATOR_URL}/internal/v1/tool-approvals"

        # Truncate arguments preview for payload safety
        safe_preview = arguments_preview[:2000] if arguments_preview else ""

        payload = {
            "workspace_id": str(workspace_id),
            "invocation_id": str(invocation_id),
            "run_id": str(run_id),
            "task_id": str(task_id),
            "tool_name": tool_name,
            "arguments_preview": safe_preview,
            "risk_reason": risk_reason,
        }

        headers = {
            "Content-Type": "application/json",
        }
        if _INTERNAL_AUTH_SECRET:
            headers["X-Internal-Auth"] = _INTERNAL_AUTH_SECRET
            headers["X-Service-Name"] = _SERVICE_NAME

        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json=payload, headers=headers)

            if resp.status_code == 201:
                result = resp.json()
                logger.info(
                    "Tool approval requested: approval_id=%s tool=%s invocation=%s",
                    result.get("id"), tool_name, invocation_id,
                )
                return result

            logger.error(
                "Tool approval request failed: status=%d body=%s",
                resp.status_code, resp.text[:500],
            )
            raise RuntimeError(
                f"Orchestrator returned {resp.status_code}: {resp.text[:200]}"
            )

        except httpx.ConnectError as exc:
            logger.error("Cannot connect to orchestrator for tool approval: %s", exc)
            raise RuntimeError(f"Cannot connect to orchestrator: {exc}") from exc
        except httpx.TimeoutException as exc:
            logger.error("Timeout requesting tool approval: %s", exc)
            raise RuntimeError(f"Timeout requesting tool approval: {exc}") from exc
