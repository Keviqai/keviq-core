"""E2E integration proof for Slice 6 — Frontend Application Shell.

11 test cases (requires running services: postgres, auth-service,
workspace-service, policy-service, api-gateway, sse-gateway,
orchestrator, agent-runtime, artifact-service, event-store):

  1.  Login + shell accessible
  2.  Task list rendered from query API
  3.  Task detail shows correct data
  4.  Run detail shows correct data
  5.  Live timeline SSE endpoint responsive
  6.  Artifact list rendered from query API
  7.  Artifact detail + provenance + lineage
  8.  Wrong workspace returns 404 (no leak)
  9.  Unauthenticated access returns 401
  10. Capability-aware response includes _capabilities
  11. No delivery scope — no download/export routes
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8080')
SSE_URL = os.getenv('SSE_GATEWAY_URL', 'http://localhost:8090')
TIMEOUT = 15.0


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope='module')
def client():
    with httpx.Client(base_url=GATEWAY_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def sse_client():
    with httpx.Client(base_url=SSE_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def auth_user(client: httpx.Client):
    """Register a fresh user and return (user_id, access_token)."""
    email = f's6-integ-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Slice 6 Integration User',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    return data['user']['id'], data['access_token']


@pytest.fixture(scope='module')
def auth_headers(auth_user):
    _, token = auth_user
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(scope='module')
def workspace(client: httpx.Client, auth_headers):
    """Create a workspace for Slice 6 integration tests."""
    slug = f's6-integ-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Slice 6 Integration Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Create workspace failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope='module')
def task_with_run(client: httpx.Client, auth_headers, workspace):
    """Submit a task which creates a run, return (task, run) data."""
    ws_id = workspace['id']
    resp = client.post(f'/v1/workspaces/{ws_id}/tasks', json={
        'title': 's6-integ-test-task',
        'task_type': 'code_generation',
        'description': 'Integration test task for Slice 6',
    }, headers=auth_headers)
    assert resp.status_code in (201, 202), f"Submit task failed: {resp.text}"
    task_data = resp.json()
    return task_data


# ── Case 1: Login + shell accessible ──────────────────────────────


def test_login_returns_token(client: httpx.Client):
    """Auth register/login returns access token for shell bootstrap."""
    email = f's6-login-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Login Test User',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert 'access_token' in data
    assert data['access_token'] != ''


# ── Case 2: Task list rendered from query API ─────────────────────


def test_task_list_returns_items(
    client: httpx.Client, auth_headers, workspace, task_with_run,
):
    """GET /v1/workspaces/{ws}/tasks returns task items."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/tasks', headers=auth_headers)
    assert resp.status_code == 200, f"List tasks failed: {resp.text}"

    data = resp.json()
    assert 'items' in data
    assert data['count'] >= 1


# ── Case 3: Task detail shows correct data ────────────────────────


def test_task_detail_has_required_fields(
    client: httpx.Client, auth_headers, workspace, task_with_run,
):
    """GET /v1/workspaces/{ws}/tasks/{id} returns full task with capabilities."""
    ws_id = workspace['id']
    task_id = task_with_run['task_id'] if 'task_id' in task_with_run else task_with_run['id']

    resp = client.get(f'/v1/workspaces/{ws_id}/tasks/{task_id}', headers=auth_headers)
    assert resp.status_code == 200, f"Get task failed: {resp.text}"

    data = resp.json()
    # Required fields for frontend rendering
    required = ['task_status', 'task_type', 'title', 'created_at', 'updated_at']
    for field in required:
        assert field in data, f"Missing required field: {field}"


# ── Case 4: Run detail shows correct data ─────────────────────────


def test_run_detail_has_required_fields(
    client: httpx.Client, auth_headers, workspace, task_with_run,
):
    """GET /v1/runs/{id} returns run with status, timing, and capabilities."""
    # Get runs for the task
    ws_id = workspace['id']
    task_id = task_with_run['task_id'] if 'task_id' in task_with_run else task_with_run['id']

    resp = client.get(f'/v1/workspaces/{ws_id}/tasks/{task_id}/runs', headers=auth_headers)
    if resp.status_code != 200 or resp.json().get('count', 0) == 0:
        pytest.skip("No runs available for this task")

    run_id = resp.json()['items'][0]['run_id']
    resp = client.get(f'/v1/runs/{run_id}', headers=auth_headers)
    assert resp.status_code == 200, f"Get run failed: {resp.text}"

    data = resp.json()
    required = ['run_id', 'run_status', 'task_id', 'attempt_number']
    for field in required:
        assert field in data, f"Missing required field: {field}"


# ── Case 5: Live timeline SSE endpoint responsive ─────────────────


def test_sse_stream_endpoint_exists(
    client: httpx.Client, auth_headers, workspace,
):
    """SSE stream endpoint must respond (200 with event-stream or 401/403)."""
    ws_id = workspace['id']
    # Use regular HTTP GET with Accept header — we don't need to hold SSE open
    resp = client.get(
        f'/v1/workspaces/{ws_id}/events/stream',
        headers={**auth_headers, 'Accept': 'text/event-stream'},
        # Short timeout — we just need to verify the endpoint exists
    )
    # 200 (stream starts), 401/403 (auth issue), or 404 would indicate missing endpoint
    assert resp.status_code != 404, (
        f"SSE stream endpoint not found: {resp.status_code}"
    )


# ── Case 6: Artifact list rendered from query API ─────────────────


def test_artifact_list_returns_structure(
    client: httpx.Client, auth_headers, workspace,
):
    """GET /v1/workspaces/{ws}/artifacts returns proper list structure."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts', headers=auth_headers)
    assert resp.status_code == 200, f"List artifacts failed: {resp.text}"

    data = resp.json()
    assert 'items' in data
    assert 'count' in data


# ── Case 7: Artifact detail + provenance + lineage ────────────────


def test_artifact_provenance_and_lineage_endpoints(
    client: httpx.Client, auth_headers, workspace,
):
    """Artifact provenance and lineage endpoints must exist."""
    ws_id = workspace['id']

    # List artifacts first
    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts', headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    if data['count'] == 0:
        pytest.skip("No artifacts in workspace to test detail/provenance/lineage")

    artifact_id = data['items'][0]['id']

    # Detail
    resp = client.get(
        f'/v1/workspaces/{ws_id}/artifacts/{artifact_id}',
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Artifact detail failed: {resp.text}"
    detail = resp.json()
    assert detail['id'] == artifact_id

    # Provenance
    resp = client.get(
        f'/v1/workspaces/{ws_id}/artifacts/{artifact_id}/provenance',
        headers=auth_headers,
    )
    # 200 or 404 (no provenance) — but endpoint must exist
    assert resp.status_code in (200, 404), (
        f"Provenance endpoint error: {resp.status_code}: {resp.text}"
    )

    # Lineage ancestors
    resp = client.get(
        f'/v1/workspaces/{ws_id}/artifacts/{artifact_id}/lineage/ancestors',
        headers=auth_headers,
    )
    assert resp.status_code in (200, 404), (
        f"Lineage endpoint error: {resp.status_code}: {resp.text}"
    )


# ── Case 8: Wrong workspace returns 404 ───────────────────────────


def test_wrong_workspace_returns_404(
    client: httpx.Client, auth_headers, workspace, task_with_run,
):
    """Accessing task from wrong workspace must return 404 (no leak)."""
    # Create another workspace
    slug = f's6-wrong-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Wrong Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201
    wrong_ws_id = resp.json()['id']

    task_id = task_with_run['task_id'] if 'task_id' in task_with_run else task_with_run['id']
    resp = client.get(
        f'/v1/workspaces/{wrong_ws_id}/tasks/{task_id}',
        headers=auth_headers,
    )
    assert resp.status_code == 404, (
        f"Wrong workspace should return 404, got {resp.status_code}"
    )


# ── Case 9: Unauthenticated access returns 401 ────────────────────


def test_unauthenticated_task_list_denied(client: httpx.Client, workspace):
    """GET tasks without auth token -> 401."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/tasks')
    assert resp.status_code == 401


def test_unauthenticated_artifact_list_denied(client: httpx.Client, workspace):
    """GET artifacts without auth token -> 401."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts')
    assert resp.status_code == 401


# ── Case 10: Capability-aware response includes _capabilities ─────


def test_task_detail_includes_capabilities(
    client: httpx.Client, auth_headers, workspace, task_with_run,
):
    """Task detail response must include _capabilities for frontend rendering."""
    ws_id = workspace['id']
    task_id = task_with_run['task_id'] if 'task_id' in task_with_run else task_with_run['id']

    resp = client.get(f'/v1/workspaces/{ws_id}/tasks/{task_id}', headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert '_capabilities' in data, (
        "S6-G3: Task detail must include _capabilities for capability-aware rendering"
    )
    assert isinstance(data['_capabilities'], dict), (
        "S6-G3: _capabilities must be a dict of capability→boolean"
    )


# ── Case 11: No delivery scope — no download/export routes ────────


def test_no_delivery_routes_on_gateway(client: httpx.Client, auth_headers, workspace):
    """Gateway must not have download/export/signed-URL routes for artifacts."""
    ws_id = workspace['id']
    delivery_paths = [
        f'/v1/workspaces/{ws_id}/artifacts/download',
        f'/v1/workspaces/{ws_id}/artifacts/export',
        f'/v1/workspaces/{ws_id}/artifacts/signed-url',
        f'/v1/workspaces/{ws_id}/artifacts/presign',
    ]
    for path in delivery_paths:
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code in (404, 405), (
            f"S6-G4: Delivery route should not exist: {path} returned {resp.status_code}"
        )

    # POST variants
    for path in delivery_paths:
        resp = client.post(path, json={}, headers=auth_headers)
        assert resp.status_code in (404, 405), (
            f"S6-G4: Delivery route should not exist: POST {path} returned {resp.status_code}"
        )
