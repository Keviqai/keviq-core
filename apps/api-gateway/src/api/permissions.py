"""API Gateway permissions — resolution and capability injection."""

from __future__ import annotations

# Task statuses that allow cancellation (mirrors orchestrator domain)
CANCELLABLE_STATUSES = frozenset({
    'pending', 'running', 'waiting_approval',
})

# Task statuses that allow retry (mirrors orchestrator domain)
RETRYABLE_STATUSES = frozenset({'failed', 'cancelled', 'timed_out'})


def resolve_orchestrator_permission(method: str, path: str) -> str | None:
    """Determine the required permission for an orchestrator route.

    Returns the permission string or None if no workspace-scoped check needed.
    POST /v1/tasks is handled separately (workspace_id from request body).
    """
    parts = path.rstrip('/').split('/')
    # POST /v1/tasks/{id}/cancel
    if method == 'POST' and len(parts) == 5 and parts[4] == 'cancel':
        return 'task:cancel'
    # POST /v1/tasks/{id}/retry
    if method == 'POST' and len(parts) == 5 and parts[4] == 'retry':
        return 'task:create'
    # POST /v1/tasks/{id}/launch
    if method == 'POST' and len(parts) == 5 and parts[4] == 'launch':
        return 'task:create'
    # GET /v1/tasks/{id}
    if method == 'GET' and len(parts) == 4 and parts[2] == 'tasks':
        return 'task:view'
    # PATCH /v1/tasks/{id} -- update brief (post-fetch checks workspace_id)
    if method == 'PATCH' and len(parts) == 4 and parts[2] == 'tasks':
        return 'task:create'
    # GET /v1/runs/{id}
    if method == 'GET' and len(parts) == 4 and parts[2] == 'runs':
        return 'run:view'
    # GET /v1/runs/{id}/steps
    if method == 'GET' and len(parts) == 5 and parts[2] == 'runs' and parts[4] == 'steps':
        return 'run:view'
    return None


def resolve_event_store_permission(method: str, path: str) -> str | None:
    """Determine the required permission for an event-store route.

    Timeline and SSE routes require workspace_id query param for
    workspace-scoped isolation.
    """
    parts = path.rstrip('/').split('/')
    # GET /v1/tasks/{id}/timeline -> task:view
    if method == 'GET' and len(parts) == 5 and parts[2] == 'tasks' and parts[4] == 'timeline':
        return 'task:view'
    # GET /v1/runs/{id}/timeline -> run:view
    if method == 'GET' and len(parts) == 5 and parts[2] == 'runs' and parts[4] == 'timeline':
        return 'run:view'
    # GET /v1/runs/{id}/events/stream -> run:view
    if (method == 'GET' and len(parts) == 6 and parts[2] == 'runs'
            and parts[4] == 'events' and parts[5] == 'stream'):
        return 'run:view'
    return None


def inject_task_capabilities(
    data: dict,
    has_cancel_perm: bool,
    has_retry_perm: bool = False,
) -> dict:
    """Add _capabilities to a task response based on state + permissions."""
    task_status = data.get('task_status', '')
    capabilities = {
        'can_cancel': has_cancel_perm and task_status in CANCELLABLE_STATUSES,
        'can_retry': has_retry_perm and task_status in RETRYABLE_STATUSES,
        'can_view_run': data.get('latest_run_id') is not None,
    }
    data['_capabilities'] = capabilities
    return data


def inject_run_capabilities(data: dict) -> dict:
    """Add _capabilities to a run response."""
    capabilities = {
        'can_view_task': True,
    }
    data['_capabilities'] = capabilities
    return data
