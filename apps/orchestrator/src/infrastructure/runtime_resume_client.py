"""HTTP client for resuming agent-runtime invocations after tool approval.

O5-S2: Called by orchestrator when a TOOL_CALL approval is decided.
Sends POST /internal/v1/invocations/{id}/resume to agent-runtime.
Fail-open: resume failure is logged but does not block the approval decision.
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

_AGENT_RUNTIME_URL = os.getenv("AGENT_RUNTIME_URL", "")
_INTERNAL_AUTH_SECRET = os.getenv("INTERNAL_AUTH_SECRET", "")
_SERVICE_NAME = os.getenv("SERVICE_NAME", "orchestrator")
_TIMEOUT_SECONDS = 130  # Must exceed INVOCATION_BUDGET_MS (120s)


def resume_invocation(
    invocation_id: UUID,
    workspace_id: UUID,
    decision: str,
    comment: str | None = None,
    override_output: str | None = None,
) -> dict | None:
    """Call agent-runtime to resume a WAITING_HUMAN invocation.

    Returns response dict on success, None on failure.
    Designed to be called from BackgroundTasks (post-response, non-blocking).
    """
    if not _AGENT_RUNTIME_URL:
        logger.warning("AGENT_RUNTIME_URL not configured — cannot resume invocation %s", invocation_id)
        return None

    url = f"{_AGENT_RUNTIME_URL}/internal/v1/invocations/{invocation_id}/resume"

    payload = {
        "workspace_id": str(workspace_id),
        "decision": decision,
    }
    if comment:
        payload["comment"] = comment[:2000]
    if override_output is not None:
        payload["override_output"] = override_output[:32768]

    headers = {"Content-Type": "application/json"}
    if _INTERNAL_AUTH_SECRET:
        headers["X-Internal-Auth"] = _INTERNAL_AUTH_SECRET
        headers["X-Service-Name"] = _SERVICE_NAME

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code == 200:
            result = resp.json()
            logger.info(
                "Invocation %s resumed: decision=%s status=%s",
                invocation_id, decision, result.get("status"),
            )
            return result

        logger.error(
            "Resume invocation %s failed: status=%d body=%s",
            invocation_id, resp.status_code, resp.text[:500],
        )
        return None

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Cannot reach agent-runtime for resume: %s", exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error resuming invocation %s: %s", invocation_id, exc)
        return None
