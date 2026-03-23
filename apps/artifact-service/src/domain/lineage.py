"""Artifact lineage edge domain model.

Implements lineage rules from doc 10, §3.
Lineage is append-only DAG (L2). Cycles are rejected (§3.3).
Self-loops are rejected at both domain and DB level.
"""

from __future__ import annotations

import enum
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from .errors import (
    DomainValidationError,
    LineageCycleError,
    LineageSelfLoopError,
)


class EdgeType(str, enum.Enum):
    """Types of lineage relationships — doc 10, §3.1.

    Slice 5 only uses DERIVED_FROM. Others defined for schema
    completeness but behavior is deferred.
    """
    DERIVED_FROM = "derived_from"
    TRANSFORMED_FROM = "transformed_from"
    AGGREGATED_FROM = "aggregated_from"
    PROMOTED_FROM = "promoted_from"


@dataclass
class ArtifactLineageEdge:
    """A directed edge in the artifact lineage DAG.

    Invariants (doc 10):
    - L2: Append-only — edges cannot be modified or deleted after recording.
    - §3.3: Lineage is DAG — cycles are rejected.
    - Self-loops are invalid (child_artifact_id != parent_artifact_id).
    """

    child_artifact_id: UUID
    parent_artifact_id: UUID
    edge_type: EdgeType
    run_id: UUID | None = None
    step_id: UUID | None = None
    transform_detail: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate basic invariants at construction time."""
        if self.child_artifact_id == self.parent_artifact_id:
            raise LineageSelfLoopError(str(self.child_artifact_id))

    def to_dict(self) -> dict[str, Any]:
        """Serialize edge to dict for storage/API response."""
        return {
            "id": str(self.id),
            "child_artifact_id": str(self.child_artifact_id),
            "parent_artifact_id": str(self.parent_artifact_id),
            "edge_type": self.edge_type.value,
            "run_id": str(self.run_id) if self.run_id else None,
            "step_id": str(self.step_id) if self.step_id else None,
            "transform_detail": self.transform_detail,
            "created_at": self.created_at.isoformat(),
        }


def detect_cycle(
    child_id: UUID,
    parent_id: UUID,
    existing_edges: list[tuple[UUID, UUID]],
) -> bool:
    """Check if adding edge parent_id → child_id would create a cycle.

    Performs BFS from parent_id following existing parent→child edges
    to see if child_id is reachable as an ancestor of parent_id.
    If child_id is an ancestor of parent_id, adding child←parent
    would create a cycle.

    Args:
        child_id: The child artifact in the new edge.
        parent_id: The parent artifact in the new edge.
        existing_edges: List of (child_artifact_id, parent_artifact_id) tuples.

    Returns:
        True if adding this edge would create a cycle.
    """
    # Self-loop is always a cycle
    if child_id == parent_id:
        return True

    # Build adjacency: for each artifact, who are its parents?
    # We need to check: is child_id an ancestor of parent_id?
    # Ancestor means: can we reach child_id by following parent edges from parent_id.
    parents_of: dict[UUID, set[UUID]] = {}
    for edge_child, edge_parent in existing_edges:
        parents_of.setdefault(edge_child, set()).add(edge_parent)

    # BFS: start from parent_id, follow parent edges upward
    visited: set[UUID] = set()
    queue: deque[UUID] = deque([parent_id])

    while queue:
        current = queue.popleft()
        if current == child_id:
            return True  # child_id is an ancestor of parent_id → cycle
        if current in visited:
            continue
        visited.add(current)
        for ancestor in parents_of.get(current, set()):
            if ancestor not in visited:
                queue.append(ancestor)

    return False
