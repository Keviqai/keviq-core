"""Artifact-service query routes: get artifact, list/search, provenance.

Query routes return 200 with current state and are called by api-gateway.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.bootstrap import get_uow
from src.internal_auth import require_service

from src.api.route_helpers import (
    _MAX_QUERY_LIMIT,
    artifact_to_dict,
    parse_datetime,
    parse_uuid,
    verify_workspace,
)

queries_router = APIRouter()


# ── Query: Get Artifact ──────────────────────────────────────

@queries_router.get("/internal/v1/artifacts/{artifact_id}")
def get_artifact_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway", "agent-runtime", "orchestrator")),
):
    """Get artifact by ID. Workspace isolation enforced."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found",
        )
    verify_workspace(artifact, wid)

    return artifact_to_dict(artifact)


# ── Query: List Artifacts ─────────────────────────────────────

@queries_router.get("/internal/v1/artifacts")
def list_artifacts_endpoint(
    workspace_id: str = Query(..., description="Workspace scope"),
    run_id: str | None = Query(None, description="Filter by run ID"),
    name_contains: str | None = Query(None, description="ILIKE name search"),
    artifact_type: str | None = Query(None, description="Exact type filter"),
    artifact_status: str | None = Query(None, description="Exact status filter"),
    root_type: str | None = Query(None, description="Exact root_type filter"),
    mime_type: str | None = Query(None, description="Exact or prefix (text/%) mime filter"),
    created_after: str | None = Query(None, description="ISO datetime lower bound"),
    created_before: str | None = Query(None, description="ISO datetime upper bound"),
    tag: str | None = Query(None, description="Filter by tag"),
    sort_by: str = Query("created_at", description="Sort field: created_at, name, size_bytes"),
    sort_order: str = Query("desc", description="Sort direction: asc or desc"),
    limit: int = Query(50, ge=1, le=_MAX_QUERY_LIMIT, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    _claims=Depends(require_service("api-gateway")),
):
    """List artifacts with optional search/filter criteria."""
    from src.application.ports import ArtifactSearchFilters

    wid = parse_uuid(workspace_id, "workspace_id")
    rid = parse_uuid(run_id, "run_id") if run_id else None

    if sort_by not in ("created_at", "name", "size_bytes"):
        raise HTTPException(status_code=400, detail="sort_by must be created_at, name, or size_bytes")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_order must be asc or desc")

    dt_after = parse_datetime(created_after) if created_after else None
    dt_before = parse_datetime(created_before) if created_before else None

    filters = ArtifactSearchFilters(
        workspace_id=wid, run_id=rid,
        name_contains=name_contains, artifact_type=artifact_type,
        artifact_status=artifact_status, root_type=root_type,
        mime_type=mime_type, created_after=dt_after, created_before=dt_before,
        tag=tag, sort_by=sort_by, sort_order=sort_order,
        limit=min(limit, _MAX_QUERY_LIMIT), offset=offset,
    )

    uow = get_uow()
    with uow:
        artifacts = uow.artifacts.search(filters)

    return {
        "items": [artifact_to_dict(a) for a in artifacts],
        "count": len(artifacts),
        "limit": filters.limit,
        "offset": offset,
    }


# ── Query: Artifact Provenance ────────────────────────────────

@queries_router.get("/internal/v1/artifacts/{artifact_id}/provenance")
def get_artifact_provenance_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Get provenance record for an artifact."""
    aid = parse_uuid(artifact_id, "artifact_id")
    wid = parse_uuid(workspace_id, "workspace_id")

    uow = get_uow()
    with uow:
        artifact = uow.artifacts.get_by_id(aid)
        if artifact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} not found",
            )
        verify_workspace(artifact, wid)

        provenance = uow.provenance.get_by_artifact_id(aid)

    if provenance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provenance not found for artifact {artifact_id}",
        )

    return provenance.to_dict()
