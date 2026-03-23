"""End-to-end integration tests for Slice 5 — Artifact domain.

Requires running services: postgres, auth-service, workspace-service,
policy-service, api-gateway, artifact-service, orchestrator, agent-runtime.

10 test cases:
  1.  Runtime creates artifact via internal API -> 202 Accepted
  2.  Query artifacts by workspace via gateway -> 200 with items
  3.  Get artifact detail via gateway -> 200 with full artifact
  4.  List artifacts by run via gateway -> 200 filtered to run
  5.  Wrong workspace -> 404 (not leaked)
  6.  Unauthenticated query -> 401
  7.  Policy fail-closed -> non-member denied
  8.  Lineage visibility via internal API -> ancestors returned
  9.  Ready requires provenance -> finalize without provenance fails
  10. No delivery scope -> no download/export/signed-URL routes exist
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8080')
ARTIFACT_SERVICE_URL = os.getenv('ARTIFACT_SERVICE_DIRECT_URL', 'http://localhost:8006')
TIMEOUT = 15.0


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def client():
    with httpx.Client(base_url=GATEWAY_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def artifact_client():
    """Direct client for artifact-service internal API."""
    with httpx.Client(base_url=ARTIFACT_SERVICE_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def auth_user(client: httpx.Client):
    """Register a fresh user and return (user_id, access_token)."""
    email = f's5-integ-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Slice 5 Integration User',
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
    """Create a workspace for Slice 5 integration tests."""
    slug = f's5-integ-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Slice 5 Integration Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Create workspace failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope='module')
def registered_artifact(artifact_client: httpx.Client, workspace):
    """Register an artifact via internal API and return the response."""
    ws_id = workspace['id']
    task_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    resp = artifact_client.post('/internal/v1/artifacts/register', json={
        'workspace_id': ws_id,
        'task_id': task_id,
        'run_id': run_id,
        'name': 'slice5-e2e-test-artifact',
        'artifact_type': 'code_file',
        'root_type': 'generated',
        'model_provider': 'anthropic',
        'model_name_concrete': 'claude-opus-4-20250514',
        'model_version_concrete': '2025-05-14',
        'run_config_hash': 'sha256:' + 'a' * 64,
        'input_snapshot': {'prompt': 'test'},
    })
    assert resp.status_code == 202, f"Register artifact failed: {resp.text}"
    data = resp.json()
    data['_workspace_id'] = ws_id
    data['_task_id'] = task_id
    data['_run_id'] = run_id
    return data


@pytest.fixture(scope='module')
def writing_artifact(artifact_client: httpx.Client, registered_artifact):
    """Transition artifact to WRITING state."""
    aid = registered_artifact['artifact_id']
    ws_id = registered_artifact['_workspace_id']

    resp = artifact_client.post(f'/internal/v1/artifacts/{aid}/begin-writing', json={
        'workspace_id': ws_id,
        'storage_ref': f's3://test-bucket/artifacts/{aid}',
    })
    assert resp.status_code == 202, f"Begin writing failed: {resp.text}"
    return registered_artifact


# ── Case 1: Runtime creates artifact via internal API ─────────────

def test_register_artifact_returns_202(registered_artifact):
    """Artifact registration via internal API returns 202 with artifact_id."""
    assert 'artifact_id' in registered_artifact
    assert registered_artifact['status'] == 'accepted'
    assert registered_artifact['artifact_status'] == 'pending'


# ── Case 2: Query artifacts by workspace via gateway ──────────────

def test_query_artifacts_by_workspace(
    client: httpx.Client, auth_headers, workspace, registered_artifact,
):
    """GET /v1/workspaces/{ws}/artifacts via gateway returns items."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts', headers=auth_headers)
    assert resp.status_code == 200, f"List artifacts failed: {resp.text}"

    data = resp.json()
    assert 'items' in data
    assert 'count' in data
    assert data['count'] >= 1

    # Our artifact must appear in the list
    artifact_ids = [item['id'] for item in data['items']]
    assert registered_artifact['artifact_id'] in artifact_ids


# ── Case 3: Get artifact detail via gateway ───────────────────────

def test_get_artifact_detail_via_gateway(
    client: httpx.Client, auth_headers, workspace, registered_artifact,
):
    """GET /v1/workspaces/{ws}/artifacts/{id} returns full artifact."""
    ws_id = workspace['id']
    aid = registered_artifact['artifact_id']

    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts/{aid}', headers=auth_headers)
    assert resp.status_code == 200, f"Get artifact failed: {resp.text}"

    data = resp.json()
    assert data['id'] == aid
    assert data['workspace_id'] == ws_id
    assert data['name'] == 'slice5-e2e-test-artifact'
    assert data['artifact_type'] == 'code_file'


# ── Case 4: List artifacts by run via gateway ─────────────────────

def test_list_artifacts_by_run(
    client: httpx.Client, auth_headers, workspace, registered_artifact,
):
    """GET /v1/workspaces/{ws}/runs/{run}/artifacts returns filtered list."""
    ws_id = workspace['id']
    run_id = registered_artifact['_run_id']

    resp = client.get(
        f'/v1/workspaces/{ws_id}/runs/{run_id}/artifacts',
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"List by run failed: {resp.text}"

    data = resp.json()
    assert 'items' in data
    assert data['count'] >= 1


# ── Case 5: Wrong workspace returns 404 ──────────────────────────

def test_wrong_workspace_returns_404(
    client: httpx.Client, auth_headers, registered_artifact,
):
    """Artifact from different workspace must return 404 (no leaking)."""
    # Create a second workspace
    slug = f's5-wrong-ws-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Wrong Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201
    wrong_ws_id = resp.json()['id']

    aid = registered_artifact['artifact_id']
    resp = client.get(
        f'/v1/workspaces/{wrong_ws_id}/artifacts/{aid}',
        headers=auth_headers,
    )
    assert resp.status_code == 404, (
        f"Wrong workspace should return 404, got {resp.status_code}: {resp.text}"
    )


# ── Case 6: Unauthenticated query returns 401 ────────────────────

def test_unauthenticated_artifact_query_denied(client: httpx.Client, workspace):
    """GET artifacts without auth token -> 401."""
    ws_id = workspace['id']
    resp = client.get(f'/v1/workspaces/{ws_id}/artifacts')
    assert resp.status_code == 401


# ── Case 7: Policy fail-closed — non-member denied ───────────────

def test_non_member_artifact_query_denied(
    client: httpx.Client, workspace, registered_artifact,
):
    """User who is NOT a workspace member cannot query artifacts -> 403."""
    # Register outsider
    email = f'outsider-s5-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Outsider S5',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201
    outsider_token = resp.json()['access_token']

    ws_id = workspace['id']
    resp = client.get(
        f'/v1/workspaces/{ws_id}/artifacts',
        headers={'Authorization': f'Bearer {outsider_token}'},
    )
    assert resp.status_code == 403, (
        f"Non-member should get 403, got {resp.status_code}: {resp.text}"
    )


# ── Case 8: Lineage visibility via internal API ──────────────────

def test_lineage_ancestors_returned(
    artifact_client: httpx.Client, workspace, registered_artifact,
):
    """Lineage ancestors endpoint must return valid response."""
    ws_id = registered_artifact['_workspace_id']
    aid = registered_artifact['artifact_id']

    resp = artifact_client.get(
        f'/internal/v1/artifacts/{aid}/lineage/ancestors',
        params={'workspace_id': ws_id},
    )
    assert resp.status_code == 200, f"Lineage query failed: {resp.text}"

    data = resp.json()
    assert data['artifact_id'] == aid
    assert 'ancestors' in data
    # New artifact has no ancestors — that's correct
    assert data['count'] == 0


# ── Case 9: Ready requires provenance ────────────────────────────

def test_finalize_without_complete_provenance_fails(
    artifact_client: httpx.Client, workspace,
):
    """Finalizing an artifact without complete provenance must fail."""
    ws_id = workspace['id']
    task_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    # Register without model provenance fields
    resp = artifact_client.post('/internal/v1/artifacts/register', json={
        'workspace_id': ws_id,
        'task_id': task_id,
        'run_id': run_id,
        'name': 'incomplete-provenance-test',
        'artifact_type': 'code_file',
        # No model_provider, model_name_concrete, model_version_concrete
    })
    assert resp.status_code == 202
    aid = resp.json()['artifact_id']

    # Begin writing
    resp = artifact_client.post(f'/internal/v1/artifacts/{aid}/begin-writing', json={
        'workspace_id': ws_id,
        'storage_ref': f's3://test-bucket/artifacts/{aid}',
    })
    assert resp.status_code == 202

    # Finalize should fail — provenance incomplete
    resp = artifact_client.post(f'/internal/v1/artifacts/{aid}/finalize', json={
        'workspace_id': ws_id,
        'checksum': 'a' * 64,
        'size_bytes': 1024,
    })
    assert resp.status_code == 400, (
        f"Finalize without provenance should return 400, got {resp.status_code}: {resp.text}"
    )


# ── Case 10: No delivery scope — no download/export routes ───────

def test_no_delivery_routes_exist(artifact_client: httpx.Client):
    """Artifact-service must not have download, export, or signed-URL routes."""
    delivery_paths = [
        '/internal/v1/artifacts/download',
        '/internal/v1/artifacts/export',
        '/internal/v1/artifacts/signed-url',
        '/internal/v1/artifacts/presign',
        '/internal/v1/artifacts/publish',
    ]
    for path in delivery_paths:
        resp = artifact_client.get(path)
        # Must return 404 or 405 — NOT 200 or 422 (422 means route exists)
        assert resp.status_code in (404, 405), (
            f"Delivery route should not exist: {path} returned {resp.status_code}"
        )

    # Also check POST variants
    for path in delivery_paths:
        resp = artifact_client.post(path, json={})
        assert resp.status_code in (404, 405), (
            f"Delivery route should not exist: POST {path} returned {resp.status_code}"
        )
