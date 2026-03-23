"""Domain errors for artifact-service."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all artifact-service domain errors."""


class InvalidTransitionError(DomainError):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(
        self, entity: str, current: str, target: str,
        reason: str | None = None,
    ):
        self.entity = entity
        self.current_status = current
        self.target_status = target
        self.reason = reason
        msg = f"{entity}: transition {current!r} → {target!r} is not allowed"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class TerminalStateError(InvalidTransitionError):
    """Raised when attempting to transition from a terminal state."""

    def __init__(self, entity: str, current: str, target: str):
        super().__init__(entity, current, target, reason="terminal state")


class DomainValidationError(DomainError):
    """Raised when domain validation fails."""

    def __init__(self, entity: str, message: str):
        self.entity = entity
        super().__init__(f"{entity}: {message}")


class IncompleteProvenanceError(DomainError):
    """Raised when provenance tuple is incomplete for finalization."""

    def __init__(self, artifact_id: str, missing_fields: list[str]):
        self.artifact_id = artifact_id
        self.missing_fields = missing_fields
        fields = ", ".join(missing_fields)
        super().__init__(
            f"Artifact {artifact_id}: incomplete provenance — "
            f"missing: {fields}"
        )


class ModelAliasError(DomainError):
    """Raised when a model alias is used instead of a concrete version."""

    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(
            f"Model identity must be concrete, not alias: "
            f"{field}={value!r}"
        )


class ArtifactNotFoundError(DomainError):
    """Raised when an artifact cannot be found."""

    def __init__(self, artifact_id: str):
        self.artifact_id = artifact_id
        super().__init__(f"Artifact {artifact_id} not found")


class LineageCycleError(DomainError):
    """Raised when a lineage edge would create a cycle in the DAG."""

    def __init__(self, child_id: str, parent_id: str):
        self.child_id = child_id
        self.parent_id = parent_id
        super().__init__(
            f"Lineage cycle detected: adding edge "
            f"{parent_id} → {child_id} would create a cycle"
        )


class LineageSelfLoopError(DomainError):
    """Raised when a lineage edge points to itself."""

    def __init__(self, artifact_id: str):
        self.artifact_id = artifact_id
        super().__init__(
            f"Lineage self-loop: artifact {artifact_id} cannot be its own parent"
        )
