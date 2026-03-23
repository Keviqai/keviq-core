"""Unit tests for ArtifactLineageEdge domain model and cycle detection.

Tests lineage rules from doc 10, §3:
- Self-loop rejection
- Cycle detection in DAG
- Append-only semantics (enforced at schema/service level, tested here at domain)
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.errors import LineageSelfLoopError
from src.domain.lineage import ArtifactLineageEdge, EdgeType, detect_cycle


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ── Edge Construction ─────────────────────────────────────────


class TestEdgeConstruction:
    def test_valid_edge(self):
        child = _uuid()
        parent = _uuid()
        edge = ArtifactLineageEdge(
            child_artifact_id=child,
            parent_artifact_id=parent,
            edge_type=EdgeType.DERIVED_FROM,
        )
        assert edge.child_artifact_id == child
        assert edge.parent_artifact_id == parent
        assert edge.edge_type == EdgeType.DERIVED_FROM
        assert edge.id is not None
        assert edge.created_at is not None

    def test_self_loop_rejected(self):
        aid = _uuid()
        with pytest.raises(LineageSelfLoopError, match="self-loop"):
            ArtifactLineageEdge(
                child_artifact_id=aid,
                parent_artifact_id=aid,
                edge_type=EdgeType.DERIVED_FROM,
            )

    def test_edge_types(self):
        assert EdgeType.DERIVED_FROM.value == "derived_from"
        assert EdgeType.TRANSFORMED_FROM.value == "transformed_from"
        assert EdgeType.AGGREGATED_FROM.value == "aggregated_from"
        assert EdgeType.PROMOTED_FROM.value == "promoted_from"

    def test_default_transform_detail_empty(self):
        edge = ArtifactLineageEdge(
            child_artifact_id=_uuid(),
            parent_artifact_id=_uuid(),
            edge_type=EdgeType.DERIVED_FROM,
        )
        assert edge.transform_detail == {}

    def test_to_dict(self):
        child = _uuid()
        parent = _uuid()
        run = _uuid()
        edge = ArtifactLineageEdge(
            child_artifact_id=child,
            parent_artifact_id=parent,
            edge_type=EdgeType.TRANSFORMED_FROM,
            run_id=run,
            transform_detail={"tool": "pdf2md"},
        )
        d = edge.to_dict()
        assert d["child_artifact_id"] == str(child)
        assert d["parent_artifact_id"] == str(parent)
        assert d["edge_type"] == "transformed_from"
        assert d["run_id"] == str(run)
        assert d["transform_detail"] == {"tool": "pdf2md"}


# ── Cycle Detection ──────────────────────────────────────────


class TestCycleDetection:
    def test_no_edges_no_cycle(self):
        """Adding first edge to empty graph — no cycle possible."""
        a = _uuid()
        b = _uuid()
        assert detect_cycle(child_id=b, parent_id=a, existing_edges=[]) is False

    def test_self_loop_detected(self):
        """child == parent is always a cycle."""
        a = _uuid()
        assert detect_cycle(child_id=a, parent_id=a, existing_edges=[]) is True

    def test_direct_cycle_detected(self):
        """A → B exists, adding B → A would create cycle."""
        a = _uuid()
        b = _uuid()
        # Existing: B's parent is A (edge: child=B, parent=A)
        existing = [(b, a)]
        # Adding: A's parent is B (child=A, parent=B)
        # This means B is ancestor of A, and A is ancestor of B → cycle
        assert detect_cycle(child_id=a, parent_id=b, existing_edges=existing) is True

    def test_transitive_cycle_detected(self):
        """A → B → C exists, adding C → A would create cycle."""
        a = _uuid()
        b = _uuid()
        c = _uuid()
        # B's parent is A, C's parent is B
        existing = [(b, a), (c, b)]
        # Adding: A's parent is C — C is ancestor of A (via C→B→A)
        # Actually: check if child_id=A is ancestor of parent_id=C
        # A is ancestor of C (A→B→C), so adding C→A creates cycle
        assert detect_cycle(child_id=a, parent_id=c, existing_edges=existing) is True

    def test_no_cycle_in_valid_dag(self):
        """Valid DAG: A → B, A → C, adding D → C."""
        a = _uuid()
        b = _uuid()
        c = _uuid()
        d = _uuid()
        existing = [(b, a), (c, a)]
        # Adding: D's parent is C — no cycle
        assert detect_cycle(child_id=d, parent_id=c, existing_edges=existing) is False

    def test_diamond_no_cycle(self):
        """Diamond: A → B, A → C, B → D, C → D. Adding E → D is fine."""
        a = _uuid()
        b = _uuid()
        c = _uuid()
        d = _uuid()
        e = _uuid()
        existing = [(b, a), (c, a), (d, b), (d, c)]
        assert detect_cycle(child_id=e, parent_id=d, existing_edges=existing) is False

    def test_long_chain_cycle(self):
        """Chain A → B → C → D → E, adding E → A creates cycle."""
        nodes = [_uuid() for _ in range(5)]
        # Each node's parent is the previous
        existing = [(nodes[i], nodes[i - 1]) for i in range(1, 5)]
        # Adding: nodes[0]'s parent is nodes[4]
        # nodes[0] is ancestor of nodes[4], so this is a cycle
        assert detect_cycle(
            child_id=nodes[0], parent_id=nodes[4], existing_edges=existing,
        ) is True

    def test_long_chain_no_cycle(self):
        """Chain A → B → C → D, adding E → D is fine (E is new)."""
        nodes = [_uuid() for _ in range(4)]
        existing = [(nodes[i], nodes[i - 1]) for i in range(1, 4)]
        e = _uuid()
        assert detect_cycle(
            child_id=e, parent_id=nodes[3], existing_edges=existing,
        ) is False

    def test_disconnected_graph_no_cycle(self):
        """Two disconnected chains, cross-link doesn't create cycle."""
        # Chain 1: A → B
        a1 = _uuid()
        b1 = _uuid()
        # Chain 2: C → D
        c2 = _uuid()
        d2 = _uuid()
        existing = [(b1, a1), (d2, c2)]
        # Adding: B's parent is C — connects chains, no cycle
        assert detect_cycle(
            child_id=b1, parent_id=c2, existing_edges=existing,
        ) is False
