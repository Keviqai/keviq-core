"""API Gateway routing — service resolution and path rewriting."""

from __future__ import annotations


def route_to_service(path: str) -> str | None:
    """Determine which backend service handles this path."""
    parts = path.rstrip('/').split('/')

    if path.startswith('/v1/auth/'):
        return 'auth'

    # Template routes -> orchestrator (read-only, system-scoped)
    if path.startswith('/v1/task-templates') or path.startswith('/v1/agent-templates'):
        return 'orchestrator'

    # Event-store routes: timeline and SSE streams
    # /v1/tasks/{id}/timeline -> event-store
    if (len(parts) == 5 and parts[2] == 'tasks' and parts[4] == 'timeline'):
        return 'event-store'
    # /v1/runs/{id}/timeline -> event-store
    if (len(parts) == 5 and parts[2] == 'runs' and parts[4] == 'timeline'):
        return 'event-store'
    # /v1/runs/{id}/events/stream -> event-store
    if (len(parts) == 6 and parts[2] == 'runs'
            and parts[4] == 'events' and parts[5] == 'stream'):
        return 'event-store'
    # /v1/workspaces/{id}/events/stream -> event-store
    if (len(parts) == 6 and parts[2] == 'workspaces'
            and parts[4] == 'events' and parts[5] == 'stream'):
        return 'event-store'

    # Orchestrator routes: tasks, runs (not timeline/stream)
    if path.startswith('/v1/tasks') or path.startswith('/v1/runs'):
        return 'orchestrator'

    # Terminal routes: /v1/terminal/sessions[/...] -> execution-service
    if path.startswith('/v1/terminal/'):
        return 'execution'

    # O7: Tool execution + sandbox detail routes -> execution-service
    if path.startswith('/v1/tool-executions/') or path.startswith('/v1/sandboxes/'):
        return 'execution'

    # O8: Telemetry routes -> telemetry-service
    if path.startswith('/v1/telemetry/'):
        return 'telemetry'

    if path.startswith('/v1/workspaces'):
        # Sub-route: /v1/workspaces/{id}/artifacts[/{id}] -> artifact-service
        if len(parts) >= 5 and parts[4] == 'artifacts':
            return 'artifact'
        # Sub-route: /v1/workspaces/{id}/runs/{id}/artifacts -> artifact-service
        if len(parts) == 7 and parts[4] == 'runs' and parts[6] == 'artifacts':
            return 'artifact'
        # Sub-route: /v1/workspaces/{id}/approvals[/{id}[/...]] -> orchestrator
        if len(parts) >= 5 and parts[4] == 'approvals':
            return 'orchestrator'
        # P6-S2: /v1/workspaces/{id}/tasks/{tid}/comments -> orchestrator
        if len(parts) >= 7 and parts[4] == 'tasks' and parts[6] == 'comments':
            return 'orchestrator'
        # /v1/workspaces/{id}/tasks/{tid}/runs -> orchestrator
        if len(parts) >= 7 and parts[4] == 'tasks' and parts[6] == 'runs':
            return 'orchestrator'
        # Sub-route: /v1/workspaces/{id}/policies -> policy-service
        if len(parts) >= 5 and parts[4] == 'policies':
            return 'policy'
        # Sub-route: /v1/workspaces/{id}/secrets -> secret-broker
        if len(parts) >= 5 and parts[4] == 'secrets':
            return 'secret'
        # Sub-route: /v1/workspaces/{id}/activity -> event-store
        if len(parts) >= 5 and parts[4] == 'activity':
            return 'event-store'
        # Sub-route: /v1/workspaces/{id}/notifications -> notification-service
        if len(parts) >= 5 and parts[4] == 'notifications':
            return 'notification'
        # Sub-route: /v1/workspaces/{id}/integrations -> model-gateway
        if len(parts) >= 5 and parts[4] == 'integrations':
            return 'model-gateway'
        # Sub-route: /v1/workspaces/{id}/audit-events -> audit-service
        if len(parts) >= 5 and parts[4] == 'audit-events':
            return 'audit'
        return 'workspace'

    return None


def rewrite_internal_path(service: str, path: str) -> str:
    """Rewrite public path to internal path for backend services.

    /v1/tasks/... -> /internal/v1/tasks/... (orchestrator)
    /v1/tasks/{id}/timeline -> /internal/v1/tasks/{id}/timeline (event-store)
    /v1/runs/...  -> /internal/v1/runs/... (orchestrator & event-store)
    /v1/workspaces/{id}/events/stream -> /internal/v1/workspaces/{id}/events/stream
    /v1/workspaces/{wid}/artifacts/... -> /internal/v1/artifacts/... (artifact-service)
    """
    if service in ('execution', 'notification'):
        return f'/internal{path}'
    if service == 'telemetry':
        # /v1/telemetry/metrics -> /internal/v1/metrics
        return path.replace('/v1/telemetry/', '/internal/v1/')
    if service in ('orchestrator', 'event-store'):
        if (path.startswith('/v1/tasks')
                or path.startswith('/v1/task-templates')
                or path.startswith('/v1/agent-templates')
                or path.startswith('/v1/runs')
                or path.startswith('/v1/workspaces')):
            return f'/internal{path}'
    if service == 'artifact':
        return _rewrite_artifact_path(path)
    return path


def _rewrite_artifact_path(path: str) -> str:
    """Rewrite artifact public paths to internal API paths.

    Public paths have workspace_id in the URL; internal API takes it as query param.
    The query param is appended by artifact_query_params().

    /v1/workspaces/{wid}/artifacts -> /internal/v1/artifacts
    /v1/workspaces/{wid}/artifacts/{aid} -> /internal/v1/artifacts/{aid}
    /v1/workspaces/{wid}/runs/{rid}/artifacts -> /internal/v1/artifacts
    """
    parts = path.rstrip('/').split('/')

    # /v1/workspaces/{wid}/artifacts/upload
    if len(parts) == 6 and parts[4] == 'artifacts' and parts[5] == 'upload':
        return f'/internal/v1/workspaces/{parts[3]}/artifacts/upload'

    # /v1/workspaces/{wid}/runs/{rid}/artifacts
    if len(parts) == 7 and parts[4] == 'runs' and parts[6] == 'artifacts':
        return '/internal/v1/artifacts'

    # /v1/workspaces/{wid}/artifacts/{aid}/download
    if len(parts) == 7 and parts[4] == 'artifacts' and parts[6] == 'download':
        return f'/internal/v1/artifacts/{parts[5]}/download'

    # /v1/workspaces/{wid}/artifacts/{aid}/preview
    if len(parts) == 7 and parts[4] == 'artifacts' and parts[6] == 'preview':
        return f'/internal/v1/artifacts/{parts[5]}/preview'

    # /v1/workspaces/{wid}/artifacts/{aid}/provenance
    if len(parts) == 7 and parts[4] == 'artifacts' and parts[6] == 'provenance':
        return f'/internal/v1/artifacts/{parts[5]}/provenance'

    # /v1/workspaces/{wid}/artifacts/{aid}/lineage/ancestors
    if len(parts) == 8 and parts[4] == 'artifacts' and parts[6] == 'lineage' and parts[7] == 'ancestors':
        return f'/internal/v1/artifacts/{parts[5]}/lineage/ancestors'

    # /v1/workspaces/{wid}/artifacts/{aid}/annotations
    if len(parts) == 7 and parts[4] == 'artifacts' and parts[6] == 'annotations':
        return f'/internal/v1/artifacts/{parts[5]}/annotations'

    # /v1/workspaces/{wid}/artifacts/{aid}/tags/{tag}
    if len(parts) == 8 and parts[4] == 'artifacts' and parts[6] == 'tags':
        return f'/internal/v1/artifacts/{parts[5]}/tags/{parts[7]}'

    # /v1/workspaces/{wid}/artifacts/{aid}/tags
    if len(parts) == 7 and parts[4] == 'artifacts' and parts[6] == 'tags':
        return f'/internal/v1/artifacts/{parts[5]}/tags'

    # /v1/workspaces/{wid}/artifacts/{aid}
    if len(parts) == 6 and parts[4] == 'artifacts':
        return f'/internal/v1/artifacts/{parts[5]}'

    # /v1/workspaces/{wid}/artifacts
    if len(parts) == 5 and parts[4] == 'artifacts':
        return '/internal/v1/artifacts'

    return path


def artifact_query_params(path: str) -> dict[str, str]:
    """Extract workspace_id and optional run_id from artifact public path for query params.

    /v1/workspaces/{wid}/artifacts -> workspace_id={wid}
    /v1/workspaces/{wid}/artifacts/{aid} -> workspace_id={wid}
    /v1/workspaces/{wid}/runs/{rid}/artifacts -> workspace_id={wid}&run_id={rid}
    """
    parts = path.rstrip('/').split('/')
    params: dict[str, str] = {}

    if len(parts) >= 4 and parts[2] == 'workspaces':
        params['workspace_id'] = parts[3]

    # /v1/workspaces/{wid}/runs/{rid}/artifacts
    if len(parts) == 7 and parts[4] == 'runs' and parts[6] == 'artifacts':
        params['run_id'] = parts[5]

    return params
