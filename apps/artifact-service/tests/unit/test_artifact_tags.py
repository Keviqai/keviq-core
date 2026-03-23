"""Unit tests for artifact tag CRUD operations.

Tests: add tag, get tags, remove tag, workspace isolation.
"""

from __future__ import annotations

import uuid

import pytest

from ._search_fakes import WS_ID, make_artifact, setup_test_env


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def env():
    client, uow = setup_test_env()
    return client, uow


# ── Add and get tags ──────────────────────────────────────────


def test_add_and_get_tags(env):
    client, uow = env
    a = make_artifact(name="tagged-artifact")
    uow.artifacts.save(a)
    aid = str(a.id)

    resp = client.post(
        f"/internal/v1/artifacts/{aid}/tags",
        params={"workspace_id": WS_ID, "tag": "important"},
    )
    assert resp.status_code == 201
    assert resp.json()["tag"] == "important"

    resp = client.get(
        f"/internal/v1/artifacts/{aid}/tags",
        params={"workspace_id": WS_ID},
    )
    assert resp.status_code == 200
    assert "important" in resp.json()["tags"]


def test_add_multiple_tags(env):
    client, uow = env
    a = make_artifact(name="multi-tag")
    uow.artifacts.save(a)
    aid = str(a.id)

    for tag in ["alpha", "beta", "gamma"]:
        client.post(
            f"/internal/v1/artifacts/{aid}/tags",
            params={"workspace_id": WS_ID, "tag": tag},
        )

    resp = client.get(
        f"/internal/v1/artifacts/{aid}/tags",
        params={"workspace_id": WS_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["alpha", "beta", "gamma"]


# ── Remove tag ────────────────────────────────────────────────


def test_remove_tag(env):
    client, uow = env
    a = make_artifact(name="tagged-rm")
    uow.artifacts.save(a)
    aid = str(a.id)

    client.post(
        f"/internal/v1/artifacts/{aid}/tags",
        params={"workspace_id": WS_ID, "tag": "temp"},
    )
    resp = client.delete(
        f"/internal/v1/artifacts/{aid}/tags/temp",
        params={"workspace_id": WS_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["removed"] is True

    resp = client.get(
        f"/internal/v1/artifacts/{aid}/tags",
        params={"workspace_id": WS_ID},
    )
    assert "temp" not in resp.json()["tags"]


def test_remove_nonexistent_tag_returns_404(env):
    client, uow = env
    a = make_artifact(name="no-tags")
    uow.artifacts.save(a)
    aid = str(a.id)

    resp = client.delete(
        f"/internal/v1/artifacts/{aid}/tags/ghost",
        params={"workspace_id": WS_ID},
    )
    assert resp.status_code == 404


# ── Workspace isolation ───────────────────────────────────────


def test_workspace_isolation_on_tags(env):
    client, uow = env
    other_ws = str(uuid.uuid4())
    a = make_artifact(name="other-ws", workspace_id=other_ws)
    uow.artifacts.save(a)

    resp = client.get(
        f"/internal/v1/artifacts/{a.id}/tags",
        params={"workspace_id": WS_ID},
    )
    assert resp.status_code == 404


# ── Tag on nonexistent artifact ───────────────────────────────


def test_add_tag_to_nonexistent_artifact(env):
    client, _ = env
    fake_id = str(uuid.uuid4())

    resp = client.post(
        f"/internal/v1/artifacts/{fake_id}/tags",
        params={"workspace_id": WS_ID, "tag": "test"},
    )
    assert resp.status_code == 404
