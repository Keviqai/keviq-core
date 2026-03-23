"""Artifact-service domain layer.

Public exports for use by application and infrastructure layers.
"""

from .artifact import Artifact, ArtifactStatus, ArtifactType, RootType
from .errors import (
    ArtifactNotFoundError,
    DomainError,
    DomainValidationError,
    IncompleteProvenanceError,
    InvalidTransitionError,
    LineageCycleError,
    LineageSelfLoopError,
    ModelAliasError,
    TerminalStateError,
)
from .lineage import ArtifactLineageEdge, EdgeType, detect_cycle
from .provenance import ArtifactProvenance

__all__ = [
    "Artifact",
    "ArtifactLineageEdge",
    "ArtifactNotFoundError",
    "ArtifactProvenance",
    "ArtifactStatus",
    "ArtifactType",
    "DomainError",
    "DomainValidationError",
    "EdgeType",
    "IncompleteProvenanceError",
    "InvalidTransitionError",
    "LineageCycleError",
    "LineageSelfLoopError",
    "ModelAliasError",
    "RootType",
    "TerminalStateError",
    "detect_cycle",
]
