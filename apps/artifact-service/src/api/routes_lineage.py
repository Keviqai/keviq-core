"""Artifact-service lineage routes: record lineage edge, get ancestors.

Lineage tracks parent-child relationships between artifacts (DAG).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError

from src.application.bootstrap import get_uow
from src.application.services import record_lineage_edge
from src.domain.errors import DomainError
from src.internal_auth import require_service

from src.api.route_helpers import (
    check_artifact_workspace,
    handle_domain_error,
    parse_body,
    parse_uuid,
    require_fields,
    verify_workspace,
)

lineage_router = APIRouter()


# ── Command: Record Lineage Edge ─────────────────────────────

@lineage_router.post(
    "/internal/v1/artifacts/{artifact_id}/lineage",
    status_code=status.HTTP_202_ACCEPTED,
)
async def record_lineage_endpoint(artifact_id: str, request: Request, _claims=Depends(require_service("agent-runtime"))):
    """Record a lineage edge (child <- parent). Returns 202 Accepted."""
    child_id = parse_uuid(artifact_id, "artifact_id")
    body = await parse_body(request)

    require_fields(body, ["workspace_id", "parent_artifact_id"])

    wid = parse_uuid(body["workspace_id"], "workspace_id")
    parent_id = parse_uuid(body["parent_artifact_id"], "parent_artifact_id")
    cid = parse_uuid(body["correlation_id"], "correlation_id") if body.get("correlation_id") else None

    # Workspace isolation: verify both artifacts belong to workspace
    uow = get_uow()
    try:
        with uow:
            check_artifact_workspace(uow, child_id, wid)
            check_artifact_workspace(uow, parent_id, wid)

        edge = record_lineage_edge(
            child_artifact_id=child_id,
            parent_artifact_id=parent_id,
            edge_type=body.get("edge_type", "derived_from"),
            run_id=parse_uuid(body["run_id"], "run_id") if body.get("run_id") else None,
            step_id=parse_uuid(body["step_id"], "step_id") if body.get("step_id") else None,
            workspace_id=wid,
            uow=get_uow(),
            correlation_id=cid,
        )
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate lineage edge — this edge already exists",
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value: {e}",
        )
    except DomainError as e:
        handle_domain_error(e)

    return {
        "edge_id": str(edge.id),
        "status": "accepted",
        "child_artifact_id": str(edge.child_artifact_id),
        "parent_artifact_id": str(edge.parent_artifact_id),
        "edge_type": edge.edge_type.value,
    }


# ── Query: Artifact Lineage Ancestors ─────────────────────────

@lineage_router.get("/internal/v1/artifacts/{artifact_id}/lineage/ancestors")
def get_artifact_ancestors_endpoint(
    artifact_id: str,
    workspace_id: str = Query(..., description="Workspace scope"),
    _claims=Depends(require_service("api-gateway")),
):
    """Get ancestor edges for an artifact (BFS up the DAG)."""
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

        edges = uow.lineage_edges.list_ancestor_edges(aid)

    return {
        "artifact_id": str(aid),
        "ancestors": [e.to_dict() for e in edges],
        "count": len(edges),
    }
