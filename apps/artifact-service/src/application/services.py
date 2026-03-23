"""Application services for artifact lifecycle.

Each service:
- Calls domain transition methods (never sets status directly)
- Uses repository abstractions (no raw SQL, no SQLAlchemy models)
- Writes outbox events in the same transaction as state mutations
- Returns domain objects for the caller (API layer in PR28)

Carry-over from PR26 review:
- Checksum/provenance immutability enforced: ready artifacts cannot be re-finalized
- Cycle detection at service level using repository data
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from src.domain.artifact import Artifact, ArtifactStatus, ArtifactType, RootType
from src.domain.errors import (
    ArtifactNotFoundError,
    DomainValidationError,
    LineageCycleError,
    LineageSelfLoopError,
)
from src.domain.lineage import ArtifactLineageEdge, EdgeType, detect_cycle
from src.domain.provenance import ArtifactProvenance

from .events import (
    artifact_failed_event,
    artifact_lineage_recorded_event,
    artifact_ready_event,
    artifact_registered_event,
    artifact_writing_event,
)
from .ports import StorageBackend, UnitOfWork


# ── Commands (value objects for service input) ─────────────────


class RegisterArtifactCommand:
    __slots__ = (
        "workspace_id", "task_id", "run_id", "name", "artifact_type",
        "root_type", "step_id", "agent_invocation_id", "mime_type",
        "model_provider", "model_name_concrete", "model_version_concrete",
        "model_temperature", "model_max_tokens", "system_prompt_hash",
        "run_config_hash", "tool_name", "tool_version", "tool_config_hash",
        "input_snapshot", "lineage_chain", "correlation_id",
    )

    def __init__(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        name: str,
        artifact_type: str,
        root_type: str = "generated",
        step_id: UUID | None = None,
        agent_invocation_id: UUID | None = None,
        mime_type: str | None = None,
        # Model provenance
        model_provider: str | None = None,
        model_name_concrete: str | None = None,
        model_version_concrete: str | None = None,
        model_temperature: float | None = None,
        model_max_tokens: int | None = None,
        system_prompt_hash: str | None = None,
        # Run config
        run_config_hash: str | None = None,
        # Tool provenance
        tool_name: str | None = None,
        tool_version: str | None = None,
        tool_config_hash: str | None = None,
        # Input / lineage
        input_snapshot: list[dict[str, str]] | None = None,
        lineage_chain: list[str] | None = None,
        correlation_id: UUID | None = None,
    ):
        self.workspace_id = workspace_id
        self.task_id = task_id
        self.run_id = run_id
        self.name = name
        self.artifact_type = artifact_type
        self.root_type = root_type
        self.step_id = step_id
        self.agent_invocation_id = agent_invocation_id
        self.mime_type = mime_type
        self.model_provider = model_provider
        self.model_name_concrete = model_name_concrete
        self.model_version_concrete = model_version_concrete
        self.model_temperature = model_temperature
        self.model_max_tokens = model_max_tokens
        self.system_prompt_hash = system_prompt_hash
        self.run_config_hash = run_config_hash
        self.tool_name = tool_name
        self.tool_version = tool_version
        self.tool_config_hash = tool_config_hash
        self.input_snapshot = input_snapshot or []
        self.lineage_chain = lineage_chain or []
        self.correlation_id = correlation_id


# ── Service functions ──────────────────────────────────────────


def register_artifact(cmd: RegisterArtifactCommand, uow: UnitOfWork) -> Artifact:
    """Create artifact in PENDING state with provenance record.

    Writes artifact.registered event to outbox in the same transaction.
    """
    correlation_id = cmd.correlation_id or uuid4()

    with uow:
        # Create domain entity — artifact_id assigned by service
        artifact = Artifact(
            workspace_id=cmd.workspace_id,
            task_id=cmd.task_id,
            run_id=cmd.run_id,
            name=cmd.name,
            artifact_type=ArtifactType(cmd.artifact_type),
            root_type=RootType(cmd.root_type),
            step_id=cmd.step_id,
            agent_invocation_id=cmd.agent_invocation_id,
            mime_type=cmd.mime_type,
        )

        # Create provenance record (validates model alias at construction)
        provenance = ArtifactProvenance(
            artifact_id=artifact.id,
            input_snapshot=cmd.input_snapshot,
            run_config_hash=cmd.run_config_hash,
            tool_name=cmd.tool_name,
            tool_version=cmd.tool_version,
            tool_config_hash=cmd.tool_config_hash,
            model_provider=cmd.model_provider,
            model_name_concrete=cmd.model_name_concrete,
            model_version_concrete=cmd.model_version_concrete,
            model_temperature=cmd.model_temperature,
            model_max_tokens=cmd.model_max_tokens,
            system_prompt_hash=cmd.system_prompt_hash,
            lineage_chain=cmd.lineage_chain,
            correlation_id=correlation_id,
        )

        uow.artifacts.save(artifact)
        uow.provenance.save(provenance)
        uow.outbox.write(artifact_registered_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            correlation_id=correlation_id,
            artifact_type=artifact.artifact_type.value,
            root_type=artifact.root_type.value,
            name=artifact.name,
        ))
        uow.commit()

    return artifact


def begin_writing(
    artifact_id: UUID,
    *,
    storage_ref: str,
    uow: UnitOfWork,
    correlation_id: UUID | None = None,
) -> Artifact:
    """Transition artifact from PENDING → WRITING.

    Writes artifact.writing event to outbox.
    """
    cid = correlation_id or uuid4()

    with uow:
        artifact = uow.artifacts.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError(str(artifact_id))

        artifact.begin_writing(storage_ref=storage_ref)

        uow.artifacts.save(artifact)
        uow.outbox.write(artifact_writing_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            correlation_id=cid,
            storage_ref=storage_ref,
        ))
        uow.commit()

    return artifact


def finalize_artifact(
    artifact_id: UUID,
    *,
    checksum: str,
    size_bytes: int,
    uow: UnitOfWork,
    correlation_id: UUID | None = None,
) -> Artifact:
    """Validate provenance completeness + checksum → transition WRITING → READY.

    Enforces:
    - Provenance tuple must be complete (S5-G3)
    - Checksum format validation (SHA-256)
    - Checksum immutability (ready artifacts cannot be re-finalized)

    Writes artifact.ready event to outbox.
    """
    cid = correlation_id or uuid4()

    with uow:
        artifact = uow.artifacts.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError(str(artifact_id))

        # Immutability guard: ready artifacts cannot be re-finalized
        if artifact.artifact_status == ArtifactStatus.READY:
            raise DomainValidationError(
                "Artifact",
                f"artifact {artifact_id} is already ready — "
                "checksum and provenance are immutable",
            )

        # Fetch provenance for validation
        provenance = uow.provenance.get_by_artifact_id(artifact_id)
        if provenance is None:
            raise DomainValidationError(
                "Artifact",
                f"no provenance record found for artifact {artifact_id}",
            )

        # Domain transition — validates checksum format + provenance completeness
        artifact.finalize(
            checksum=checksum,
            size_bytes=size_bytes,
            provenance=provenance,
        )

        uow.artifacts.save(artifact)
        uow.outbox.write(artifact_ready_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            correlation_id=cid,
            checksum=artifact.checksum,
            size_bytes=size_bytes,
        ))
        uow.commit()

    return artifact


def fail_artifact(
    artifact_id: UUID,
    *,
    failure_reason: str | None = None,
    partial_data: bool = False,
    uow: UnitOfWork,
    correlation_id: UUID | None = None,
) -> Artifact:
    """Transition artifact to FAILED state.

    Preserves partial data flag for debug access (doc 10 §6.1).
    Writes artifact.failed event to outbox.
    """
    cid = correlation_id or uuid4()

    with uow:
        artifact = uow.artifacts.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError(str(artifact_id))

        artifact.fail(failure_reason=failure_reason, partial_data=partial_data)

        uow.artifacts.save(artifact)
        uow.outbox.write(artifact_failed_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            correlation_id=cid,
            failure_reason=failure_reason,
        ))
        uow.commit()

    return artifact


def upload_artifact(
    *,
    workspace_id: UUID,
    name: str,
    artifact_type: str,
    mime_type: str | None,
    content: bytes,
    uploader_user_id: str,
    original_filename: str,
    uow: UnitOfWork,
    storage_backend: "StorageBackend",
    correlation_id: UUID | None = None,
) -> Artifact:
    """Upload artifact: register → begin_writing → write storage → finalize.

    All steps in a single call for user-uploaded content.
    Creates uploaded provenance (no model/run provenance required).
    Storage key is derived from the artifact's own ID for consistency.
    """
    cid = correlation_id or uuid4()

    # Create artifact in PENDING state
    artifact = Artifact(
        workspace_id=workspace_id,
        task_id=workspace_id,  # uploaded roots use workspace as task scope
        run_id=workspace_id,   # uploaded roots use workspace as run scope
        name=name,
        artifact_type=ArtifactType(artifact_type),
        root_type=RootType.UPLOAD,
        mime_type=mime_type,
    )

    # Storage key uses actual artifact ID (PR44 convention)
    storage_key = f"workspaces/{workspace_id}/artifacts/{artifact.id}/content"

    # Create uploaded provenance (no model provenance)
    provenance = ArtifactProvenance(
        artifact_id=artifact.id,
        correlation_id=cid,
    )

    # Compute checksum
    checksum = hashlib.sha256(content).hexdigest()
    size_bytes = len(content)

    # State transitions
    artifact.begin_writing(storage_ref=storage_key)

    # Write to storage
    storage_backend.write_content(storage_key, content)

    # Finalize
    artifact.finalize(
        checksum=checksum,
        size_bytes=size_bytes,
        provenance=provenance,
    )

    # Persist everything in one transaction
    with uow:
        uow.artifacts.save(artifact)
        uow.provenance.save(provenance)
        uow.outbox.write(artifact_registered_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            correlation_id=cid,
            artifact_type=artifact.artifact_type.value,
            root_type=artifact.root_type.value,
            name=artifact.name,
        ))
        uow.outbox.write(artifact_writing_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            run_id=artifact.run_id,
            correlation_id=cid,
            storage_ref=storage_key,
        ))
        uow.outbox.write(artifact_ready_event(
            artifact_id=artifact.id,
            workspace_id=artifact.workspace_id,
            correlation_id=cid,
            checksum=checksum,
            size_bytes=size_bytes,
        ))
        uow.commit()

    return artifact


def record_lineage_edge(
    *,
    child_artifact_id: UUID,
    parent_artifact_id: UUID,
    edge_type: str = "derived_from",
    run_id: UUID | None = None,
    step_id: UUID | None = None,
    workspace_id: UUID,
    uow: UnitOfWork,
    correlation_id: UUID | None = None,
) -> ArtifactLineageEdge:
    """Record a lineage edge with DAG cycle detection.

    Performs cycle detection at service/repository level using existing edges
    from the database — not just in-memory domain check.

    Writes artifact.lineage_recorded event to outbox.
    """
    cid = correlation_id or uuid4()

    with uow:
        # Verify both artifacts exist
        child = uow.artifacts.get_by_id(child_artifact_id)
        if child is None:
            raise ArtifactNotFoundError(str(child_artifact_id))

        parent = uow.artifacts.get_by_id(parent_artifact_id)
        if parent is None:
            raise ArtifactNotFoundError(str(parent_artifact_id))

        # Self-loop check before general cycle detection
        if child_artifact_id == parent_artifact_id:
            raise LineageSelfLoopError(str(child_artifact_id))

        # Cycle detection scoped to workspace for performance
        existing_edges = uow.lineage_edges.list_edges_by_workspace(workspace_id)
        if detect_cycle(child_artifact_id, parent_artifact_id, existing_edges):
            raise LineageCycleError(
                str(child_artifact_id), str(parent_artifact_id),
            )

        # Create edge (self-loop check happens in domain __post_init__)
        edge = ArtifactLineageEdge(
            child_artifact_id=child_artifact_id,
            parent_artifact_id=parent_artifact_id,
            edge_type=EdgeType(edge_type),
            run_id=run_id,
            step_id=step_id,
        )

        uow.lineage_edges.save(edge)
        uow.outbox.write(artifact_lineage_recorded_event(
            edge_id=edge.id,
            child_artifact_id=child_artifact_id,
            parent_artifact_id=parent_artifact_id,
            edge_type=edge.edge_type.value,
            workspace_id=workspace_id,
            run_id=run_id,
            correlation_id=cid,
        ))
        uow.commit()

    return edge
