"""Artifact-service API routes — main router.

Mounts sub-routers for commands, queries, content, lineage, tags, and internal.
Health check endpoints are defined here directly.
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from src.api.routes_commands import commands_router
from src.api.routes_content import content_router
from src.api.routes_internal import internal_router
from src.api.routes_lineage import lineage_router
from src.api.routes_queries import queries_router
from src.api.routes_tags import tags_router

router = APIRouter()

# ── Health ────────────────────────────────────────────────────


@router.get("/healthz/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info() -> dict[str, str]:
    info: dict = {"service": "artifact-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
        info["storage_backend"] = os.getenv("ARTIFACT_STORAGE_BACKEND", "local")
    return info


# ── Mount sub-routers ────────────────────────────────────────

router.include_router(commands_router)
router.include_router(queries_router)
router.include_router(content_router)
router.include_router(lineage_router)
router.include_router(tags_router)
router.include_router(internal_router)
