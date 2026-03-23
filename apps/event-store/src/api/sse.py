"""SSE streaming endpoints for event-store.

Extracted from routes.py to comply with 300-line file limit.
"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from src.internal_auth import require_service

from src.application.bootstrap import get_repo
from src.application.queries import get_run_events_after, get_workspace_events
from src.domain.event import event_to_dict

sse_router = APIRouter()

# SSE heartbeat interval in seconds
_SSE_HEARTBEAT_INTERVAL = 15
# SSE poll interval for new events
_SSE_POLL_INTERVAL = 1


# ── SSE: Workspace Event Stream ───────────────────────────────

@sse_router.get("/internal/v1/workspaces/{workspace_id}/events/stream")
async def workspace_event_stream(
    request: Request,
    workspace_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """SSE stream for workspace events. Supports Last-Event-ID for replay."""
    try:
        ws_id = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    # Support both header (native EventSource reconnect) and query param (custom reconnect)
    last_event_id = (
        request.headers.get("last-event-id")
        or request.query_params.get("last_event_id")
    )
    after_id = None
    if last_event_id:
        try:
            after_id = UUID(last_event_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Last-Event-ID format",
            )

    return StreamingResponse(
        _workspace_sse_generator(ws_id, after_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _workspace_sse_generator(
    workspace_id: UUID,
    after_event_id: UUID | None,
    request: Request,
):
    """Generate SSE events for a workspace stream."""
    last_id = after_event_id
    heartbeat_counter = 0
    repo = get_repo()

    try:
        if last_id:
            missed = get_workspace_events(workspace_id, repo, after_event_id=last_id)
            for event in missed:
                yield _format_sse(event_to_dict(event), str(event.id))
                last_id = event.id

        while True:
            if await request.is_disconnected():
                break

            events = get_workspace_events(
                workspace_id, repo, after_event_id=last_id, limit=50,
            )

            for event in events:
                yield _format_sse(event_to_dict(event), str(event.id))
                last_id = event.id

            if events:
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= _SSE_HEARTBEAT_INTERVAL:
                    yield ":heartbeat\n\n"
                    heartbeat_counter = 0

            await asyncio.sleep(_SSE_POLL_INTERVAL)
    finally:
        repo.close()


# ── SSE: Run Event Stream ─────────────────────────────────────

@sse_router.get("/internal/v1/runs/{run_id}/events/stream")
async def run_event_stream(
    request: Request,
    run_id: str,
    workspace_id: str,
    _claims=Depends(require_service("api-gateway")),
):
    """SSE stream for run-scoped events. Supports Last-Event-ID. Scoped to workspace."""
    try:
        rid = UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format",
        )
    try:
        wid = UUID(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace_id format",
        )

    # Support both header (native EventSource reconnect) and query param (custom reconnect)
    last_event_id = (
        request.headers.get("last-event-id")
        or request.query_params.get("last_event_id")
    )
    after_id = None
    if last_event_id:
        try:
            after_id = UUID(last_event_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Last-Event-ID format",
            )

    return StreamingResponse(
        _run_sse_generator(rid, wid, after_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_sse_generator(
    run_id: UUID,
    workspace_id: UUID,
    after_event_id: UUID | None,
    request: Request,
):
    """Generate SSE events for a run-scoped stream, workspace-isolated."""
    last_id = after_event_id
    heartbeat_counter = 0
    repo = get_repo()

    try:
        if last_id:
            missed = get_run_events_after(run_id, workspace_id, repo, after_event_id=last_id)
            for event in missed:
                yield _format_sse(event_to_dict(event), str(event.id))
                last_id = event.id

        while True:
            if await request.is_disconnected():
                break

            events = get_run_events_after(
                run_id, workspace_id, repo, after_event_id=last_id, limit=50,
            )

            for event in events:
                yield _format_sse(event_to_dict(event), str(event.id))
                last_id = event.id

            if events:
                heartbeat_counter = 0
            else:
                heartbeat_counter += 1
                if heartbeat_counter >= _SSE_HEARTBEAT_INTERVAL:
                    yield ":heartbeat\n\n"
                    heartbeat_counter = 0

            await asyncio.sleep(_SSE_POLL_INTERVAL)
    finally:
        repo.close()


# ── SSE formatting helper ─────────────────────────────────────

def _format_sse(data: dict, event_id: str) -> str:
    """Format a dict as an SSE event string."""
    payload = json.dumps(data)
    return f"id:{event_id}\nevent:{data.get('event_type', 'message')}\ndata:{payload}\n\n"
