"""Unit tests for artifact search/filter capabilities.

Tests: name ILIKE, type/status filter, date range, combined filters,
       sort by different fields, pagination offset, tag-based filtering.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.artifact import ArtifactStatus, ArtifactType, RootType

from ._search_fakes import WS_ID, make_artifact, setup_test_env


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def env():
    client, uow = setup_test_env()
    return client, uow


# ── Filter by name (ILIKE) ───────────────────────────────────


def test_filter_by_name_contains(env):
    client, uow = env
    for a in [
        make_artifact(name="Final Report Q1"),
        make_artifact(name="Draft Notes"),
        make_artifact(name="report-summary"),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "name_contains": "report"},
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "Final Report Q1" in names
    assert "report-summary" in names
    assert "Draft Notes" not in names


# ── Filter by type ────────────────────────────────────────────


def test_filter_by_artifact_type(env):
    client, uow = env
    for a in [
        make_artifact(name="code.patch", artifact_type=ArtifactType.CODE_PATCH),
        make_artifact(name="data.csv", artifact_type=ArtifactType.DATASET),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "artifact_type": "code_patch"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["artifact_type"] == "code_patch"


# ── Filter by status ──────────────────────────────────────────


def test_filter_by_status(env):
    client, uow = env
    for a in [
        make_artifact(name="ready-one", artifact_status=ArtifactStatus.READY),
        make_artifact(name="pending-one", artifact_status=ArtifactStatus.PENDING),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "artifact_status": "pending"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["artifact_status"] == "pending"


# ── Filter by date range ──────────────────────────────────────


def test_filter_by_date_range(env):
    client, uow = env
    now = datetime.now(timezone.utc)
    for a in [
        make_artifact(name="old-artifact", created_at=now - timedelta(days=30)),
        make_artifact(name="recent-artifact", created_at=now - timedelta(hours=1)),
    ]:
        uow.artifacts.save(a)

    cutoff = (now - timedelta(days=7)).isoformat()
    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "created_after": cutoff},
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "recent-artifact" in names
    assert "old-artifact" not in names


# ── Combined filters ──────────────────────────────────────────


def test_combined_filters(env):
    client, uow = env
    for a in [
        make_artifact(name="Final Report", artifact_type=ArtifactType.REPORT, mime_type="text/html"),
        make_artifact(name="Draft Report", artifact_type=ArtifactType.REPORT, mime_type="application/pdf"),
        make_artifact(name="Final Code", artifact_type=ArtifactType.CODE_PATCH, mime_type="text/plain"),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "name_contains": "Report", "artifact_type": "report"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert {i["name"] for i in items} == {"Final Report", "Draft Report"}


# ── Sort ──────────────────────────────────────────────────────


def test_sort_by_name_asc(env):
    client, uow = env
    for a in [
        make_artifact(name="Bravo"),
        make_artifact(name="Alpha"),
        make_artifact(name="Charlie"),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "sort_by": "name", "sort_order": "asc"},
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert names == ["Alpha", "Bravo", "Charlie"]


def test_sort_by_size_bytes_desc(env):
    client, uow = env
    for a in [
        make_artifact(name="small", size_bytes=10),
        make_artifact(name="big", size_bytes=9999),
        make_artifact(name="medium", size_bytes=500),
    ]:
        uow.artifacts.save(a)

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "sort_by": "size_bytes", "sort_order": "desc"},
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert names == ["big", "medium", "small"]


def test_invalid_sort_by_returns_400(env):
    client, _ = env
    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "sort_by": "invalid_field"},
    )
    assert resp.status_code == 400


# ── Offset / pagination ──────────────────────────────────────


def test_offset_pagination(env):
    client, uow = env
    now = datetime.now(timezone.utc)
    for i in range(5):
        uow.artifacts.save(
            make_artifact(name=f"item-{i}", created_at=now - timedelta(minutes=i)),
        )

    resp = client.get(
        "/internal/v1/artifacts",
        params={
            "workspace_id": WS_ID,
            "sort_by": "created_at", "sort_order": "desc",
            "limit": 2, "offset": 2,
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert resp.json()["offset"] == 2


# ── Tag-based filtering in search ────────────────────────────


def test_filter_by_tag(env):
    client, uow = env
    a1 = make_artifact(name="tagged-one")
    a2 = make_artifact(name="untagged")
    for a in [a1, a2]:
        uow.artifacts.save(a)

    client.post(
        f"/internal/v1/artifacts/{a1.id}/tags",
        params={"workspace_id": WS_ID, "tag": "reviewed"},
    )

    resp = client.get(
        "/internal/v1/artifacts",
        params={"workspace_id": WS_ID, "tag": "reviewed"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "tagged-one"
