"""Terminal session API routes.

Command-response model: POST command → execute in sandbox → return result.
All routes require api-gateway as caller (internal auth).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.internal_auth import require_service

if TYPE_CHECKING:
    from src.domain.terminal_command import TerminalCommand
    from src.domain.terminal_session import TerminalSession

from src.application.bootstrap import get_execution_backend, get_uow
from src.application.terminal_session_service import (
    close_session,
    create_session,
    execute_command,
    get_session,
    list_commands,
)
from src.domain.errors import DomainError, InvalidTransitionError
from src.domain.terminal_contracts import CreateTerminalSessionRequest, ExecCommandRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_user_id(request: Request) -> str:
    """Extract X-User-Id header. Raises 401 if missing."""
    user_id = request.headers.get("X-User-Id", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    return user_id


def _session_dict(s: "TerminalSession") -> dict[str, Any]:
    """Serialize a TerminalSession to JSON-safe dict."""
    return {
        "id": str(s.id),
        "sandbox_id": str(s.sandbox_id),
        "run_id": str(s.run_id),
        "workspace_id": str(s.workspace_id),
        "user_id": s.user_id,
        "status": s.status.value,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
    }


def _command_dict(c: "TerminalCommand") -> dict[str, Any]:
    """Serialize a TerminalCommand to JSON-safe dict."""
    return {
        "id": str(c.id),
        "session_id": str(c.session_id),
        "command": c.command,
        "stdout": c.stdout,
        "stderr": c.stderr,
        "exit_code": c.exit_code,
        "status": c.status.value,
        "created_at": c.created_at.isoformat(),
        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
    }


# -- Create Session -------------------------------------------------------

@router.post(
    "/internal/v1/terminal/sessions",
    status_code=status.HTTP_201_CREATED,
)
async def create_session_endpoint(
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Create a new terminal session for a sandbox."""
    body = await request.json()

    for field in ("sandbox_id", "run_id", "workspace_id"):
        if field not in body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required field: {field}",
            )

    user_id = request.headers.get("X-User-Id", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )

    try:
        req = CreateTerminalSessionRequest.from_dict(body, user_id)
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    try:
        session = create_session(req, uow)
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e),
        )

    return _session_dict(session)


# -- Execute Command ------------------------------------------------------

@router.post("/internal/v1/terminal/sessions/{session_id}/exec")
async def exec_command_endpoint(
    session_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Execute a command in a terminal session. Blocks until completion."""
    user_id = _get_user_id(request)
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    body = await request.json()
    if "command" not in body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: command",
        )

    try:
        req = ExecCommandRequest.from_dict(body, sid)
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )

    uow = get_uow()
    backend = get_execution_backend()

    try:
        cmd = await asyncio.to_thread(
            execute_command, req, uow, backend, user_id=user_id,
        )
    except DomainError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e),
        )

    return _command_dict(cmd)


# -- Get Session ----------------------------------------------------------

@router.get("/internal/v1/terminal/sessions/{session_id}")
def get_session_endpoint(
    session_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Get terminal session by ID."""
    user_id = _get_user_id(request)
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    uow = get_uow()
    try:
        session = get_session(sid, uow, user_id=user_id)
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e),
        )

    return _session_dict(session)


# -- List Command History -------------------------------------------------

@router.get("/internal/v1/terminal/sessions/{session_id}/history")
def list_history_endpoint(
    session_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """List command history for a terminal session."""
    user_id = _get_user_id(request)
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    uow = get_uow()
    try:
        commands = list_commands(sid, uow, user_id=user_id)
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e),
        )

    return {"items": [_command_dict(c) for c in commands]}


# -- Close Session --------------------------------------------------------

@router.post("/internal/v1/terminal/sessions/{session_id}/close")
def close_session_endpoint(
    session_id: str,
    request: Request,
    _claims=Depends(require_service("api-gateway")),
):
    """Close a terminal session."""
    user_id = _get_user_id(request)
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        )

    uow = get_uow()
    try:
        session = close_session(sid, uow, user_id=user_id)
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e),
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e),
        )

    return _session_dict(session)
