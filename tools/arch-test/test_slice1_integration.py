"""End-to-end integration tests for Slice 1.

Requires running services: postgres, auth-service, workspace-service,
policy-service, api-gateway.

Tests the full flow through the api-gateway:
  1. Register + login
  2. Create workspace (with _capabilities)
  3. Fetch workspace (with _capabilities)
  4. Fail-closed: policy-service down → 403
  5. Member management
"""

import os
import subprocess
import time
import uuid

import httpx
import pytest

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8080')
TIMEOUT = 10.0


@pytest.fixture(scope='module')
def client():
    with httpx.Client(base_url=GATEWAY_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def auth_user(client: httpx.Client):
    """Register a fresh user and return (user_id, access_token)."""
    email = f'integ-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Integration Test User',
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
def workspace(client: httpx.Client, auth_headers, auth_user):
    """Create a workspace and return the response dict."""
    slug = f'integ-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Integration Test Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Create workspace failed: {resp.text}"
    return resp.json()


# ── Test 1: Health Check ────────────────────────────────────────────

def test_gateway_health(client: httpx.Client):
    resp = client.get('/healthz/live')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'live'


# ── Test 2: Register + Login ────────────────────────────────────────

def test_register_and_login(client: httpx.Client):
    email = f'login-{uuid.uuid4().hex[:8]}@test.com'

    # Register
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Login Test',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201
    data = resp.json()
    assert 'access_token' in data
    assert data['user']['email'] == email

    # Login
    resp = client.post('/v1/auth/login', json={
        'email': email,
        'password': 'testpassword123',
    })
    assert resp.status_code == 200
    assert 'access_token' in resp.json()


# ── Test 3: Create Workspace with _capabilities ─────────────────────

def test_create_workspace_has_capabilities(workspace):
    assert '_capabilities' in workspace, (
        "Workspace response must include _capabilities (server-derived)"
    )
    caps = workspace['_capabilities']
    assert isinstance(caps, list)
    assert len(caps) > 0
    # Owner should have all workspace capabilities
    assert 'workspace:view' in caps
    assert 'workspace:delete' in caps
    assert 'workspace:manage_members' in caps


# ── Test 4: Fetch Workspace with _capabilities ──────────────────────

def test_get_workspace_has_capabilities(client: httpx.Client, auth_headers, workspace):
    resp = client.get(f'/v1/workspaces/{workspace["id"]}', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert '_capabilities' in data
    assert 'workspace:view' in data['_capabilities']


# ── Test 5: Unauthenticated access denied ───────────────────────────

def test_unauthenticated_denied(client: httpx.Client, workspace):
    resp = client.get(f'/v1/workspaces/{workspace["id"]}')
    assert resp.status_code == 401


# ── Test 6: Non-member denied ───────────────────────────────────────

def test_non_member_denied(client: httpx.Client, workspace):
    # Register a second user
    email = f'outsider-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Outsider',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201
    token = resp.json()['access_token']

    # Try to access workspace
    resp = client.get(
        f'/v1/workspaces/{workspace["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 403, (
        f"Non-member should get 403, got {resp.status_code}: {resp.text}"
    )


# ── Test 7: Fail-closed (policy-service down → 403) ─────────────────

def test_fail_closed_policy_service_down(client: httpx.Client, auth_headers, workspace):
    """When policy-service is stopped, gateway must return 403 (not 500/502).

    This test stops the policy-service container, makes a permissioned request,
    and verifies the fail-closed behavior. Then restarts policy-service.
    """
    ws_id = workspace['id']

    # Stop policy-service
    subprocess.run(
        ['docker', 'compose', 'stop', 'policy-service'],
        cwd=os.path.join(os.path.dirname(__file__), '../../infra/docker'),
        capture_output=True,
        timeout=30,
    )

    try:
        # Wait for it to actually stop
        time.sleep(2)

        # Make a permissioned request (GET workspace requires workspace:view)
        resp = client.get(
            f'/v1/workspaces/{ws_id}',
            headers=auth_headers,
        )
        # Fail-closed: should return 403, NOT 500 or 502
        assert resp.status_code == 403, (
            f"Expected fail-closed 403 when policy-service is down, "
            f"got {resp.status_code}: {resp.text}"
        )
    finally:
        # Restart policy-service
        subprocess.run(
            ['docker', 'compose', 'start', 'policy-service'],
            cwd=os.path.join(os.path.dirname(__file__), '../../infra/docker'),
            capture_output=True,
            timeout=30,
        )
        time.sleep(3)  # Wait for it to come back up


# ── Test 8: Member management ──────────────────────────────────────

def test_invite_and_list_members(client: httpx.Client, auth_headers, workspace):
    ws_id = workspace['id']

    # Register a new user to invite
    email = f'invitee-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Invitee',
        'password': 'testpassword123',
    })
    invitee_id = resp.json()['user']['id']

    # Invite as editor
    resp = client.post(
        f'/v1/workspaces/{ws_id}/members',
        json={'user_id': invitee_id, 'role': 'editor'},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"Invite failed: {resp.text}"
    assert resp.json()['role'] == 'editor'

    # List members — should have 2 (owner + invitee)
    resp = client.get(f'/v1/workspaces/{ws_id}/members', headers=auth_headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) >= 2

    # Invitee should see editor capabilities
    invitee_token = client.post('/v1/auth/login', json={
        'email': email, 'password': 'testpassword123',
    }).json()['access_token']

    resp = client.get(
        f'/v1/workspaces/{ws_id}',
        headers={'Authorization': f'Bearer {invitee_token}'},
    )
    assert resp.status_code == 200
    caps = resp.json()['_capabilities']
    assert 'workspace:view' in caps
    assert 'task:create' in caps
    # Editor should NOT have manage_members
    assert 'workspace:manage_members' not in caps
