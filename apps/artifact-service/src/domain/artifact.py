"""Artifact domain entity with state machine.

State machine transitions per doc 05, section 6.
Source of truth: artifact-service (SVC-03, doc 04 §3.12).

States (Slice 5 scope): pending, writing, ready, failed.
Deferred states: superseded, archived (Phase C).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    IncompleteProvenanceError,
    InvalidTransitionError,
    TerminalStateError,
)
from .provenance import ArtifactProvenance


# ── Enums ──────────────────────────────────────────────────────


class RootType(str, enum.Enum):
    """How the artifact originated — doc 10, §2."""
    GENERATED = "generated"
    UPLOAD = "upload"
    REPO_SNAPSHOT = "repo_snapshot"
    IMPORTED = "imported"


class ArtifactType(str, enum.Enum):
    """Classification of artifact content — doc 04 §3.12."""
    FILE = "file"
    CODE_PATCH = "code_patch"
    REPORT = "report"
    DATASET = "dataset"
    LOG = "log"
    STRUCTURED_DATA = "structured_data"
    MODEL_OUTPUT = "model_output"


class ArtifactStatus(str, enum.Enum):
    """Artifact lifecycle states — doc 05 §6."""
    PENDING = "pending"
    WRITING = "writing"
    READY = "ready"
    FAILED = "failed"
    # Deferred to Phase C:
    # SUPERSEDED = "superseded"
    # ARCHIVED = "archived"


# ── State Machine ─────────────────────────────────────────────


_ARTIFACT_TRANSITIONS: dict[ArtifactStatus, frozenset[ArtifactStatus]] = {
    ArtifactStatus.PENDING: frozenset({
        ArtifactStatus.WRITING,
        ArtifactStatus.FAILED,
    }),
    ArtifactStatus.WRITING: frozenset({
        ArtifactStatus.READY,
        ArtifactStatus.FAILED,
    }),
    ArtifactStatus.READY: frozenset(),   # Terminal for Slice 5 (superseded/archived deferred)
    ArtifactStatus.FAILED: frozenset(),  # Terminal for Slice 5 (archived deferred)
}

_ARTIFACT_TERMINAL = frozenset({
    ArtifactStatus.READY,
    ArtifactStatus.FAILED,
})


# ── Entity ─────────────────────────────────────────────────────


class Artifact:
    """Artifact aggregate root.

    Invariants:
    - Only artifact-service mutates artifact_status (S5-G1).
    - Transitions enforced via methods, not free set.
    - workspace_id, run_id are immutable after creation.
    - Checksum is immutable after ready (doc 04 §3.12).
    - Ready requires complete provenance tuple (doc 10 §4.6).
    - artifact_id is assigned by artifact-service (not by caller).
    """

    __slots__ = (
        "id",
        "workspace_id",
        "task_id",
        "run_id",
        "step_id",
        "agent_invocation_id",
        "root_type",
        "artifact_type",
        "artifact_status",
        "name",
        "mime_type",
        "storage_ref",
        "size_bytes",
        "checksum",
        "lineage",
        "metadata",
        "ready_at",
        "failed_at",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        *,
        workspace_id: UUID,
        task_id: UUID,
        run_id: UUID,
        name: str,
        artifact_type: ArtifactType,
        root_type: RootType = RootType.GENERATED,
        step_id: UUID | None = None,
        agent_invocation_id: UUID | None = None,
        mime_type: str | None = None,
        storage_ref: str | None = None,
        size_bytes: int | None = None,
        checksum: str | None = None,
        lineage: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        # For reconstitution from persistence:
        id: UUID | None = None,
        artifact_status: ArtifactStatus = ArtifactStatus.PENDING,
        ready_at: datetime | None = None,
        failed_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if not name or not name.strip():
            raise DomainValidationError("Artifact", "name must not be blank")

        now = datetime.now(timezone.utc)
        self.id = id or uuid4()
        self.workspace_id = workspace_id
        self.task_id = task_id
        self.run_id = run_id
        self.step_id = step_id
        self.agent_invocation_id = agent_invocation_id
        self.root_type = root_type
        self.artifact_type = artifact_type
        self.artifact_status = artifact_status
        self.name = name
        self.mime_type = mime_type
        self.storage_ref = storage_ref
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.lineage = lineage if lineage is not None else []
        self.metadata = metadata if metadata is not None else {}
        self.ready_at = ready_at
        self.failed_at = failed_at
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Artifact) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    # ── Transition helpers ──────────────────────────────────────

    def _transition(self, target: ArtifactStatus) -> ArtifactStatus:
        """Execute a state transition, returning the previous status.

        Raises InvalidTransitionError or TerminalStateError.
        """
        current = self.artifact_status
        if current in _ARTIFACT_TERMINAL:
            raise TerminalStateError("Artifact", current.value, target.value)
        allowed = _ARTIFACT_TRANSITIONS[current]
        if target not in allowed:
            raise InvalidTransitionError("Artifact", current.value, target.value)
        self.artifact_status = target
        self.updated_at = datetime.now(timezone.utc)
        return current

    # ── Public transition API ───────────────────────────────────

    def begin_writing(self, storage_ref: str) -> ArtifactStatus:
        """pending → writing.

        Called when content write begins. storage_ref points to the
        storage location where content will be written.
        """
        if not storage_ref or not storage_ref.strip():
            raise DomainValidationError(
                "Artifact", "storage_ref is required to begin writing",
            )
        prev = self._transition(ArtifactStatus.WRITING)
        self.storage_ref = storage_ref
        return prev

    def finalize(
        self,
        *,
        checksum: str,
        size_bytes: int,
        provenance: ArtifactProvenance,
    ) -> ArtifactStatus:
        """writing → ready.

        Validates provenance completeness and checksum format before
        transitioning to ready. Checksum is immutable after this point.

        Args:
            checksum: SHA-256 hex digest of the artifact content.
            size_bytes: Final size of artifact content in bytes.
            provenance: Complete provenance record — validated here.
        """
        # Validate checksum format (SHA-256 = 64 hex chars)
        if not checksum or len(checksum) != 64:
            raise DomainValidationError(
                "Artifact",
                f"checksum must be 64-char SHA-256 hex digest, got length {len(checksum) if checksum else 0}",
            )
        try:
            int(checksum, 16)
        except ValueError:
            raise DomainValidationError(
                "Artifact", "checksum must be valid hexadecimal",
            )

        # Normalize to lowercase for consistent comparison
        checksum = checksum.lower()

        if size_bytes < 0:
            raise DomainValidationError(
                "Artifact", "size_bytes must be non-negative",
            )

        # Validate provenance completeness (S5-G3)
        provenance.validate_complete(str(self.id), root_type=self.root_type.value)

        prev = self._transition(ArtifactStatus.READY)
        self.checksum = checksum
        self.size_bytes = size_bytes
        self.ready_at = datetime.now(timezone.utc)
        return prev

    def fail(
        self,
        *,
        failure_reason: str | None = None,
        partial_data: bool = False,
    ) -> ArtifactStatus:
        """pending/writing → failed.

        Preserves partial data flag for debug access (doc 10 §6.1).
        """
        prev = self._transition(ArtifactStatus.FAILED)
        self.failed_at = datetime.now(timezone.utc)
        self.metadata = {
            **self.metadata,
            "failure_reason": failure_reason or "unknown",
            "partial_data_available": partial_data,
        }
        return prev

    # ── Query helpers ───────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.artifact_status in _ARTIFACT_TERMINAL

    @property
    def is_ready(self) -> bool:
        return self.artifact_status == ArtifactStatus.READY

    @property
    def is_failed(self) -> bool:
        return self.artifact_status == ArtifactStatus.FAILED
