"""Mapping between SQLAlchemy rows and domain objects.

Bidirectional conversion keeping domain objects free of ORM concerns.
"""

from __future__ import annotations

import json as _json
from uuid import UUID

from src.domain.artifact import Artifact, ArtifactStatus, ArtifactType, RootType
from src.domain.lineage import ArtifactLineageEdge, EdgeType
from src.domain.provenance import ArtifactProvenance

from .models import ArtifactRow, LineageEdgeRow, ProvenanceRow


# ── Artifact ───────────────────────────────────────────────────


def artifact_row_to_domain(row: ArtifactRow) -> Artifact:
    return Artifact(
        id=UUID(str(row.id)),
        workspace_id=UUID(str(row.workspace_id)),
        task_id=UUID(str(row.task_id)),
        run_id=UUID(str(row.run_id)),
        step_id=UUID(str(row.step_id)) if row.step_id else None,
        agent_invocation_id=UUID(str(row.agent_invocation_id)) if row.agent_invocation_id else None,
        root_type=RootType(row.root_type),
        artifact_type=ArtifactType(row.artifact_type),
        artifact_status=ArtifactStatus(row.artifact_status),
        name=row.name,
        mime_type=row.mime_type,
        storage_ref=row.storage_ref,
        size_bytes=row.size_bytes,
        checksum=row.checksum,
        lineage=row.lineage if row.lineage else [],
        metadata=row.metadata_ if row.metadata_ else {},
        ready_at=row.ready_at,
        failed_at=row.failed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def artifact_domain_to_row(artifact: Artifact) -> dict:
    return dict(
        id=str(artifact.id),
        workspace_id=str(artifact.workspace_id),
        task_id=str(artifact.task_id),
        run_id=str(artifact.run_id),
        step_id=str(artifact.step_id) if artifact.step_id else None,
        agent_invocation_id=str(artifact.agent_invocation_id) if artifact.agent_invocation_id else None,
        root_type=artifact.root_type.value,
        artifact_type=artifact.artifact_type.value,
        artifact_status=artifact.artifact_status.value,
        name=artifact.name,
        mime_type=artifact.mime_type,
        storage_ref=artifact.storage_ref,
        size_bytes=artifact.size_bytes,
        checksum=artifact.checksum,
        lineage=_json.dumps(artifact.lineage) if isinstance(artifact.lineage, (list, dict)) else artifact.lineage,
        metadata_=_json.dumps(artifact.metadata) if isinstance(artifact.metadata, dict) else artifact.metadata,
        ready_at=artifact.ready_at,
        failed_at=artifact.failed_at,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


# ── Provenance ─────────────────────────────────────────────────


def provenance_row_to_domain(row: ProvenanceRow) -> ArtifactProvenance:
    return ArtifactProvenance(
        artifact_id=UUID(str(row.artifact_id)),
        input_snapshot=row.input_snapshot if row.input_snapshot else [],
        run_config_hash=row.run_config_hash,
        tool_name=row.tool_name,
        tool_version=row.tool_version,
        tool_config_hash=row.tool_config_hash,
        model_provider=row.model_provider,
        model_name_concrete=row.model_name_concrete,
        model_version_concrete=row.model_version_concrete,
        model_temperature=row.model_temperature,
        model_max_tokens=row.model_max_tokens,
        system_prompt_hash=row.system_prompt_hash,
        lineage_chain=row.lineage_chain if row.lineage_chain else [],
        correlation_id=UUID(str(row.correlation_id)) if row.correlation_id else None,
        id=UUID(str(row.id)),
    )


def provenance_domain_to_row(prov: ArtifactProvenance) -> dict:
    return dict(
        id=str(prov.id),
        artifact_id=str(prov.artifact_id),
        input_snapshot=prov.input_snapshot,
        run_config_hash=prov.run_config_hash,
        tool_name=prov.tool_name,
        tool_version=prov.tool_version,
        tool_config_hash=prov.tool_config_hash,
        model_provider=prov.model_provider,
        model_name_concrete=prov.model_name_concrete,
        model_version_concrete=prov.model_version_concrete,
        model_temperature=prov.model_temperature,
        model_max_tokens=prov.model_max_tokens,
        system_prompt_hash=prov.system_prompt_hash,
        lineage_chain=prov.lineage_chain,
        correlation_id=str(prov.correlation_id) if prov.correlation_id else None,
    )


# ── Lineage Edge ───────────────────────────────────────────────


def edge_row_to_domain(row: LineageEdgeRow) -> ArtifactLineageEdge:
    return ArtifactLineageEdge(
        id=UUID(str(row.id)),
        child_artifact_id=UUID(str(row.child_artifact_id)),
        parent_artifact_id=UUID(str(row.parent_artifact_id)),
        edge_type=EdgeType(row.edge_type),
        run_id=UUID(str(row.run_id)) if row.run_id else None,
        step_id=UUID(str(row.step_id)) if row.step_id else None,
        transform_detail=row.transform_detail if row.transform_detail else {},
        created_at=row.created_at,
    )


def edge_domain_to_row(edge: ArtifactLineageEdge) -> dict:
    return dict(
        id=str(edge.id),
        child_artifact_id=str(edge.child_artifact_id),
        parent_artifact_id=str(edge.parent_artifact_id),
        edge_type=edge.edge_type.value,
        run_id=str(edge.run_id) if edge.run_id else None,
        step_id=str(edge.step_id) if edge.step_id else None,
        transform_detail=edge.transform_detail,
        created_at=edge.created_at,
    )
