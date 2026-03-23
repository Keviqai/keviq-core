"""Internal auth API routes — service-to-service only.

Called by workspace-service to resolve user display names.
Protected by internal service auth (require_service).
"""

from __future__ import annotations

import sys
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, status

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'packages', 'internal-auth')
))
from internal_auth.fastapi_dep import require_service  # noqa: E402

from src.application.bootstrap import get_session_factory, get_user_repo

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_LOOKUP_IDS = 200


@router.get("/internal/v1/users/lookup")
def lookup_users(
    ids: str,
    _claims=Depends(require_service("workspace-service")),
):
    """Batch lookup users by UUID. ids is a comma-separated list of UUIDs.

    Returns [{id, email, display_name}] for each found user.
    Unknown IDs are silently omitted (not an error).
    """
    if not ids:
        return {"users": []}

    raw_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if len(raw_ids) > _MAX_LOOKUP_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many IDs (max {_MAX_LOOKUP_IDS})",
        )

    import uuid as _uuid

    valid_uids: list[_uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            valid_uids.append(_uuid.UUID(raw_id))
        except ValueError:
            pass  # skip malformed IDs

    if not valid_uids:
        return {"users": []}

    user_repo = get_user_repo()
    session_factory = get_session_factory()
    db = None
    try:
        db = session_factory()
        users = user_repo.find_by_ids(db, valid_uids)
    finally:
        if db:
            db.close()

    return {"users": [
        {"id": str(u.id), "email": u.email, "display_name": u.display_name}
        for u in users
    ]}
