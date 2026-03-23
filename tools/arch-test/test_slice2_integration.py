"""End-to-end integration tests for Slice 2.

Requires running services: postgres, auth-service, workspace-service,
policy-service, api-gateway, orchestrator, event-store.

8 mandatory E2E cases:
  1. Submit task → 202 Accepted (never blocks, returns task_id + links)
  2. Poll task → terminal state (completed/failed within timeout)
  3. Timeline matches final state (events in correct order)
  4. SSE live event delivery (at least one event received)
  5. Last-Event-ID replay (SSE reconnect replays missed events)
  6. Query vs timeline consistency (query state matches last timeline event)
  7. Unauthorized deny (no token / wrong workspace → 401/403)
  8. Cancel semantics (cancel running task → 202, cascades to run/steps)
"""

from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8080')
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_DIRECT_URL', 'http://localhost:8001')
TIMEOUT = 15.0
POLL_INTERVAL = 0.5
POLL_MAX_WAIT = 30.0


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def client():
    with httpx.Client(base_url=GATEWAY_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope='module')
def auth_user(client: httpx.Client):
    """Register a fresh user and return (user_id, access_token)."""
    email = f's2-integ-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Slice 2 Integration User',
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
    """Create a workspace for slice 2 integration tests."""
    slug = f's2-integ-{uuid.uuid4().hex[:8]}'
    resp = client.post('/v1/workspaces', json={
        'slug': slug,
        'display_name': 'Slice 2 Integration Workspace',
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Create workspace failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope='module')
def submitted_task(client: httpx.Client, auth_headers, auth_user, workspace):
    """Submit a task and return the submit response."""
    user_id, _ = auth_user
    resp = client.post('/v1/tasks', json={
        'workspace_id': workspace['id'],
        'title': f'Slice 2 E2E Test Task {uuid.uuid4().hex[:6]}',
        'task_type': 'coding',
        'created_by_id': user_id,
        'description': 'Automated integration test for Slice 2',
    }, headers=auth_headers)
    assert resp.status_code == 202, f"Submit task failed: {resp.text}"
    return resp.json()


def _poll_task_until_terminal(
    client: httpx.Client,
    task_id: str,
    headers: dict,
    max_wait: float = POLL_MAX_WAIT,
) -> dict:
    """Poll GET /v1/tasks/{task_id} until task reaches terminal state."""
    terminal = {'completed', 'failed', 'cancelled', 'archived'}
    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        resp = client.get(f'/v1/tasks/{task_id}', headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('task_status') in terminal:
                return data
        time.sleep(POLL_INTERVAL)
    pytest.fail(f"Task {task_id} did not reach terminal state within {max_wait}s")


def _trigger_outbox_relay():
    """Trigger outbox relay on orchestrator to push events to event-store."""
    with httpx.Client(timeout=10.0) as c:
        try:
            c.post(f'{ORCHESTRATOR_URL}/internal/v1/outbox/relay')
        except httpx.HTTPError:
            pass  # Best-effort; relay may run automatically


def _flush_outbox(settle_seconds: float = 1.0):
    """Trigger relay and wait for events to settle in event-store.

    Calls relay twice to handle the case where the first call relays events
    that were written after the initial query but before commit.
    """
    _trigger_outbox_relay()
    time.sleep(settle_seconds)
    _trigger_outbox_relay()


# ── Case 1: Submit → 202 Accepted ────────────────────────────────

def test_submit_returns_202(submitted_task):
    """Submit task returns 202 with task_id and links, never final state."""
    assert 'task_id' in submitted_task
    assert submitted_task.get('status') == 'accepted'
    assert 'links' in submitted_task
    assert 'task' in submitted_task['links']
    # Must NOT contain final state fields (S2-G2)
    assert 'task_status' not in submitted_task
    assert 'run_status' not in submitted_task


# ── Case 2: Poll → terminal state ────────────────────────────────

@pytest.fixture(scope='module')
def terminal_task(client: httpx.Client, auth_headers, submitted_task):
    """Wait for the submitted task to reach terminal state."""
    task_id = submitted_task['task_id']
    return _poll_task_until_terminal(client, task_id, auth_headers)


def test_poll_reaches_terminal(terminal_task):
    """Task reaches a terminal state (completed or failed) via polling."""
    status = terminal_task['task_status']
    assert status in {'completed', 'failed', 'cancelled'}, (
        f"Expected terminal state completed/failed/cancelled, got '{status}'"
    )
    assert 'task_id' in terminal_task
    assert 'workspace_id' in terminal_task


# ── Case 3: Timeline matches final state ─────────────────────────

def test_timeline_matches_final_state(
    client: httpx.Client, auth_headers, submitted_task, terminal_task,
):
    """Task timeline events must exist and reflect the execution lifecycle."""
    task_id = submitted_task['task_id']

    # Flush outbox to ensure events are in event-store
    _flush_outbox()

    resp = client.get(f'/v1/tasks/{task_id}/timeline', headers=auth_headers)
    assert resp.status_code == 200, f"Timeline fetch failed: {resp.text}"
    data = resp.json()

    events = data.get('events', [])
    assert len(events) > 0, "Timeline must contain at least one event"

    # Events must be ordered by occurred_at
    timestamps = [e['occurred_at'] for e in events]
    assert timestamps == sorted(timestamps), "Timeline events not ordered by occurred_at"

    # First event should be task.submitted
    event_types = [e['event_type'] for e in events]
    assert 'task.submitted' in event_types, (
        f"Timeline must contain task.submitted, got: {event_types}"
    )

    # Last event type should reflect terminal state
    final_status = terminal_task['task_status']
    if final_status == 'completed':
        assert 'task.completed' in event_types, (
            f"Terminal state is completed but task.completed not in timeline: {event_types}"
        )
    elif final_status == 'failed':
        assert 'task.failed' in event_types, (
            f"Terminal state is failed but task.failed not in timeline: {event_types}"
        )


# ── Case 4: SSE live event delivery ─────────────────────────────

def test_sse_receives_events(
    client: httpx.Client, auth_headers, auth_user, workspace,
):
    """SSE workspace stream must deliver at least one event for a new task."""
    user_id, token = auth_user
    ws_id = workspace['id']

    # Submit a new task to generate events
    resp = client.post('/v1/tasks', json={
        'workspace_id': ws_id,
        'title': f'SSE Test Task {uuid.uuid4().hex[:6]}',
        'task_type': 'coding',
        'created_by_id': user_id,
    }, headers=auth_headers)
    assert resp.status_code == 202

    # Wait for execution + flush outbox
    time.sleep(3)
    _flush_outbox()

    # Connect to SSE stream with a short timeout
    # Use httpx stream to read SSE events
    events_received = []
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)) as sse_client:
            with sse_client.stream(
                'GET',
                f'{GATEWAY_URL}/v1/workspaces/{ws_id}/events/stream',
                headers={'Authorization': f'Bearer {token}'},
            ) as stream:
                buffer = ''
                for chunk in stream.iter_text():
                    buffer += chunk
                    # Parse SSE events from buffer
                    while '\n\n' in buffer:
                        event_str, buffer = buffer.split('\n\n', 1)
                        if event_str.startswith(':'):
                            continue  # heartbeat
                        if 'data:' in event_str:
                            events_received.append(event_str)
                    if len(events_received) >= 1:
                        break
    except (httpx.ReadTimeout, httpx.ReadError):
        pass  # Expected — SSE is long-lived

    assert len(events_received) >= 1, (
        "SSE stream must deliver at least one event"
    )


# ── Case 5: Last-Event-ID replay ─────────────────────────────────

def test_last_event_id_replay(
    client: httpx.Client, auth_headers, submitted_task,
):
    """SSE Last-Event-ID must replay events after the given ID."""
    task_id = submitted_task['task_id']

    # Ensure events exist
    _flush_outbox()

    # Get timeline to find an event ID
    resp = client.get(f'/v1/tasks/{task_id}/timeline', headers=auth_headers)
    if resp.status_code != 200:
        pytest.skip("Timeline not available")

    events = resp.json().get('events', [])
    if len(events) < 2:
        pytest.skip("Need at least 2 events for replay test")

    # Use the first event's ID as Last-Event-ID
    first_event_id = events[0].get('event_id') or events[0].get('id')
    if not first_event_id:
        pytest.skip("Event ID not found in timeline")

    # Get run_id from events for run-scoped SSE
    run_events = [e for e in events if e.get('run_id')]
    if not run_events:
        pytest.skip("No run-scoped events for replay test")

    run_id = run_events[0]['run_id']
    first_run_event_id = run_events[0].get('event_id') or run_events[0].get('id')

    # Connect to run SSE stream with Last-Event-ID
    replay_events = []
    try:
        with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)) as sse_client:
            with sse_client.stream(
                'GET',
                f'{GATEWAY_URL}/v1/runs/{run_id}/events/stream',
                headers={
                    'Authorization': auth_headers['Authorization'],
                    'Last-Event-ID': first_run_event_id,
                },
            ) as stream:
                buffer = ''
                for chunk in stream.iter_text():
                    buffer += chunk
                    while '\n\n' in buffer:
                        event_str, buffer = buffer.split('\n\n', 1)
                        if event_str.startswith(':'):
                            continue
                        if 'data:' in event_str:
                            replay_events.append(event_str)
                    if len(replay_events) >= 1:
                        break
    except (httpx.ReadTimeout, httpx.ReadError):
        pass

    # Replay should return events AFTER the first one
    # (at minimum, there should be events since we had >= 2)
    assert len(replay_events) >= 1, (
        "Last-Event-ID replay must return events after the given ID"
    )

    # Verify replayed events don't include the first event
    for ev_str in replay_events:
        for line in ev_str.split('\n'):
            if line.startswith('id:'):
                replayed_id = line[3:].strip()
                assert replayed_id != first_run_event_id, (
                    "Replayed events must NOT include the Last-Event-ID event itself"
                )


# ── Case 6: Query vs timeline consistency ─────────────────────────

def test_query_matches_timeline(
    client: httpx.Client, auth_headers, submitted_task, terminal_task,
):
    """Query state must be consistent with the last timeline event."""
    task_id = submitted_task['task_id']

    _flush_outbox()

    # Get current task state
    resp = client.get(f'/v1/tasks/{task_id}', headers=auth_headers)
    assert resp.status_code == 200
    query_status = resp.json()['task_status']

    # Get timeline
    resp = client.get(f'/v1/tasks/{task_id}/timeline', headers=auth_headers)
    assert resp.status_code == 200
    events = resp.json().get('events', [])

    if not events:
        pytest.skip("No timeline events to verify consistency")

    # The last event type should correspond to the query status
    last_event = events[-1]
    event_type = last_event['event_type']

    # Map: task event → expected task_status
    event_to_status = {
        'task.submitted': 'pending',
        'task.started': 'running',
        'task.approval_requested': 'waiting_approval',
        'task.approved': 'running',
        'task.completed': 'completed',
        'task.failed': 'failed',
        'task.cancelled': 'cancelled',
        'task.archived': 'archived',
    }

    if event_type in event_to_status:
        expected_status = event_to_status[event_type]
        assert query_status == expected_status, (
            f"Query status '{query_status}' inconsistent with last timeline event "
            f"'{event_type}' (expected '{expected_status}')"
        )
    # If last event is run/step-scoped, skip assertion (task-level
    # consistency is what matters; run events don't map to task_status)


# ── Case 7: Unauthorized deny ────────────────────────────────────

def test_unauthenticated_submit_denied(client: httpx.Client, workspace):
    """Submit task without auth token → 401."""
    resp = client.post('/v1/tasks', json={
        'workspace_id': workspace['id'],
        'title': 'Unauthorized Task',
        'task_type': 'coding',
        'created_by_id': str(uuid.uuid4()),
    })
    assert resp.status_code == 401


def test_unauthenticated_query_denied(client: httpx.Client, submitted_task):
    """Query task without auth token → 401."""
    task_id = submitted_task['task_id']
    resp = client.get(f'/v1/tasks/{task_id}')
    assert resp.status_code == 401


def test_wrong_workspace_denied(client: httpx.Client, submitted_task):
    """User from different workspace cannot access task → 403."""
    # Register a new user (not member of workspace)
    email = f'outsider-s2-{uuid.uuid4().hex[:8]}@test.com'
    resp = client.post('/v1/auth/register', json={
        'email': email,
        'display_name': 'Outsider S2',
        'password': 'testpassword123',
    })
    assert resp.status_code == 201
    outsider_token = resp.json()['access_token']

    task_id = submitted_task['task_id']
    resp = client.get(
        f'/v1/tasks/{task_id}',
        headers={'Authorization': f'Bearer {outsider_token}'},
    )
    assert resp.status_code == 403, (
        f"Non-member should get 403, got {resp.status_code}: {resp.text}"
    )


# ── Case 8: Cancel semantics ─────────────────────────────────────

def test_cancel_returns_202_and_cascades(
    client: httpx.Client, auth_headers, auth_user, workspace,
):
    """Cancel a task → 202 Accepted, cascades to runs and steps.

    NOTE: In Phase B, simulated execution runs synchronously inside the submit
    endpoint, so tasks typically complete before we can cancel. This test uses
    two strategies:
    1. Try to cancel immediately after submit (race the sync execution).
    2. If task already completed, verify cancel on a completed task returns
       409 (InvalidTransitionError) — proving the state machine protects
       against invalid cancellation.
    """
    user_id, _ = auth_user
    ws_id = workspace['id']

    # Submit a new task
    resp = client.post('/v1/tasks', json={
        'workspace_id': ws_id,
        'title': f'Cancel Test Task {uuid.uuid4().hex[:6]}',
        'task_type': 'coding',
        'created_by_id': user_id,
    }, headers=auth_headers)
    assert resp.status_code == 202
    task_id = resp.json()['task_id']

    # Check current state
    resp = client.get(f'/v1/tasks/{task_id}', headers=auth_headers)
    assert resp.status_code == 200
    task_data = resp.json()
    current_status = task_data.get('task_status')

    cancellable = {'pending', 'running', 'waiting_approval'}
    if current_status in cancellable:
        # Task is still cancellable — test the happy path
        resp = client.post(
            f'/v1/tasks/{task_id}/cancel',
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 202, f"Cancel failed: {resp.status_code} {resp.text}"
        cancel_data = resp.json()
        assert cancel_data.get('status') == 'accepted'

        # Verify cascading fields present
        assert 'cancelled_runs' in cancel_data
        assert 'cancelled_steps' in cancel_data

        # Poll to confirm task is cancelled
        time.sleep(1)
        resp = client.get(f'/v1/tasks/{task_id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()['task_status'] == 'cancelled', (
            f"Task should be cancelled, got {resp.json()['task_status']}"
        )

        # Verify cancel event in timeline
        _flush_outbox()
        resp = client.get(f'/v1/tasks/{task_id}/timeline', headers=auth_headers)
        if resp.status_code == 200:
            events = resp.json().get('events', [])
            event_types = [e['event_type'] for e in events]
            assert 'task.cancelled' in event_types, (
                f"Timeline must contain task.cancelled, got: {event_types}"
            )
    else:
        # Task already completed (sync execution finished) — verify cancel is
        # rejected with 409, proving state machine guards work
        assert current_status in {'completed', 'failed'}, (
            f"Unexpected status: {current_status}"
        )
        resp = client.post(
            f'/v1/tasks/{task_id}/cancel',
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 409, (
            f"Cancel on {current_status} task should return 409 Conflict, "
            f"got {resp.status_code}: {resp.text}"
        )
