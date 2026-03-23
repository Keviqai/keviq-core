"""Auth-service client — fetch user display names for member enrichment.

Called by list_members (via MemberEnricher port) to resolve user_id → display_name / email.
Uses internal-auth token for service-to-service auth.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import httpx

from src.application.ports import MemberEnricher

logger = logging.getLogger(__name__)

_AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "").rstrip("/")

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'packages', 'internal-auth')
))


def _get_auth_headers() -> dict[str, str]:
    try:
        from internal_auth.bootstrap import get_auth_client  # noqa: E402
        return get_auth_client().auth_headers("auth-service")
    except Exception as exc:
        logger.warning("internal auth client unavailable: %s", exc)
        return {}


def _fetch_user_display_names(user_ids: list[str]) -> dict[str, dict[str, str]]:
    """Return {user_id: {display_name, email}} for the given IDs.

    Falls back to empty dict on error — callers must handle missing names gracefully.
    IDs not found in auth-service are omitted from result.
    """
    if not _AUTH_SERVICE_URL or not user_ids:
        return {}

    ids_param = ",".join(user_ids)
    url = f"{_AUTH_SERVICE_URL}/internal/v1/users/lookup"
    headers = _get_auth_headers()

    try:
        resp = httpx.get(url, params={"ids": ids_param}, headers=headers, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("auth-service user lookup failed: %s", exc)
        return {}

    result: dict[str, dict[str, str]] = {}
    for u in data.get("users", []):
        uid = u.get("id")
        if uid:
            result[uid] = {
                "display_name": u.get("display_name") or "",
                "email": u.get("email") or "",
            }
    return result


class AuthServiceMemberEnricher(MemberEnricher):
    """Infrastructure adapter: enriches member dicts with display_name/email from auth-service."""

    def enrich(self, members: list[dict[str, Any]]) -> None:
        """Mutate each member dict in-place: add display_name and email fields.

        If auth-service is unavailable, fields are set to None (graceful degradation).
        """
        user_ids = list({m["user_id"] for m in members if m.get("user_id")})
        if not user_ids:
            return

        name_map = _fetch_user_display_names(user_ids)

        for m in members:
            uid = m.get("user_id")
            info = name_map.get(str(uid)) if uid else None
            m["display_name"] = info["display_name"] if info else None
            m["email"] = info["email"] if info else None
