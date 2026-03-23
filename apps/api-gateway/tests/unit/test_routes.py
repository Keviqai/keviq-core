"""Unit tests for gateway routing, path rewriting, capabilities, and post-fetch authz."""

import json

import pytest
from fastapi import Response

from src.api.routing import (
    _rewrite_artifact_path,
    artifact_query_params as _artifact_query_params,
    rewrite_internal_path as _rewrite_internal_path,
    route_to_service as _route_to_service,
)
from src.api.permissions import (
    inject_run_capabilities as _inject_run_capabilities,
    inject_task_capabilities as _inject_task_capabilities,
    resolve_event_store_permission as _resolve_event_store_permission,
    resolve_orchestrator_permission as _resolve_orchestrator_permission,
)
from src.api.post_fetch import _build_json_response


# ── _route_to_service ─────────────────────────────────────────────

class TestRouteToService:
    def test_auth_routes(self):
        assert _route_to_service('/v1/auth/login') == 'auth'
        assert _route_to_service('/v1/auth/register') == 'auth'
        assert _route_to_service('/v1/auth/me') == 'auth'

    def test_workspace_routes(self):
        assert _route_to_service('/v1/workspaces') == 'workspace'
        assert _route_to_service('/v1/workspaces/123') == 'workspace'
        assert _route_to_service('/v1/workspaces/123/members') == 'workspace'

    def test_policy_routes(self):
        assert _route_to_service('/v1/workspaces/123/policies') == 'policy'
        assert _route_to_service('/v1/workspaces/123/policies/456') == 'policy'

    def test_task_routes(self):
        assert _route_to_service('/v1/tasks') == 'orchestrator'
        assert _route_to_service('/v1/tasks/abc-123') == 'orchestrator'
        assert _route_to_service('/v1/tasks/abc-123/cancel') == 'orchestrator'

    def test_run_routes(self):
        assert _route_to_service('/v1/runs') == 'orchestrator'
        assert _route_to_service('/v1/runs/abc-123') == 'orchestrator'
        assert _route_to_service('/v1/runs/abc-123/steps') == 'orchestrator'

    def test_unknown_path_returns_none(self):
        assert _route_to_service('/v1/unknown/thing') is None
        assert _route_to_service('/v1/something') is None

    # ── Event-store routes ──────────────────────────────────────

    def test_task_timeline_routes_to_event_store(self):
        assert _route_to_service('/v1/tasks/abc-123/timeline') == 'event-store'

    def test_run_timeline_routes_to_event_store(self):
        assert _route_to_service('/v1/runs/abc-123/timeline') == 'event-store'

    def test_run_sse_routes_to_event_store(self):
        assert _route_to_service('/v1/runs/abc-123/events/stream') == 'event-store'

    def test_workspace_sse_routes_to_event_store(self):
        assert _route_to_service('/v1/workspaces/ws-123/events/stream') == 'event-store'

    def test_timeline_takes_precedence_over_orchestrator(self):
        """Timeline routes must match before the generic /v1/tasks prefix."""
        assert _route_to_service('/v1/tasks/abc/timeline') == 'event-store'
        assert _route_to_service('/v1/runs/abc/timeline') == 'event-store'

    def test_run_events_stream_takes_precedence(self):
        """SSE stream routes must match before the generic /v1/runs prefix."""
        assert _route_to_service('/v1/runs/abc/events/stream') == 'event-store'

    # ── Artifact routes ────────────────────────────────────────

    def test_artifact_list_routes_to_artifact(self):
        assert _route_to_service('/v1/workspaces/ws-1/artifacts') == 'artifact'

    def test_artifact_get_routes_to_artifact(self):
        assert _route_to_service('/v1/workspaces/ws-1/artifacts/art-1') == 'artifact'

    def test_artifact_by_run_routes_to_artifact(self):
        assert _route_to_service('/v1/workspaces/ws-1/runs/run-1/artifacts') == 'artifact'

    def test_artifact_trailing_slash(self):
        assert _route_to_service('/v1/workspaces/ws-1/artifacts/') == 'artifact'


# ── _rewrite_internal_path ────────────────────────────────────────

class TestRewriteInternalPath:
    def test_task_path_orchestrator(self):
        assert _rewrite_internal_path('orchestrator', '/v1/tasks') == '/internal/v1/tasks'
        assert _rewrite_internal_path('orchestrator', '/v1/tasks/abc') == '/internal/v1/tasks/abc'
        assert _rewrite_internal_path('orchestrator', '/v1/tasks/abc/cancel') == '/internal/v1/tasks/abc/cancel'

    def test_run_path_orchestrator(self):
        assert _rewrite_internal_path('orchestrator', '/v1/runs/abc') == '/internal/v1/runs/abc'
        assert _rewrite_internal_path('orchestrator', '/v1/runs/abc/steps') == '/internal/v1/runs/abc/steps'

    def test_task_timeline_event_store(self):
        assert _rewrite_internal_path('event-store', '/v1/tasks/abc/timeline') == '/internal/v1/tasks/abc/timeline'

    def test_run_timeline_event_store(self):
        assert _rewrite_internal_path('event-store', '/v1/runs/abc/timeline') == '/internal/v1/runs/abc/timeline'

    def test_run_sse_event_store(self):
        assert _rewrite_internal_path('event-store', '/v1/runs/abc/events/stream') == '/internal/v1/runs/abc/events/stream'

    def test_workspace_sse_event_store(self):
        assert _rewrite_internal_path('event-store', '/v1/workspaces/ws-1/events/stream') == '/internal/v1/workspaces/ws-1/events/stream'

    def test_artifact_path_rewrite(self):
        assert _rewrite_internal_path('artifact', '/v1/workspaces/ws-1/artifacts') == '/internal/v1/artifacts'
        assert _rewrite_internal_path('artifact', '/v1/workspaces/ws-1/artifacts/art-1') == '/internal/v1/artifacts/art-1'
        assert _rewrite_internal_path('artifact', '/v1/workspaces/ws-1/runs/run-1/artifacts') == '/internal/v1/artifacts'

    def test_non_rewritten_service(self):
        assert _rewrite_internal_path('auth', '/v1/auth/login') == '/v1/auth/login'
        assert _rewrite_internal_path('workspace', '/v1/workspaces') == '/v1/workspaces'


# ── _resolve_orchestrator_permission ──────────────────────────────

class TestResolveOrchestratorPermission:
    def test_get_task(self):
        assert _resolve_orchestrator_permission('GET', '/v1/tasks/abc') == 'task:view'

    def test_post_cancel(self):
        assert _resolve_orchestrator_permission('POST', '/v1/tasks/abc/cancel') == 'task:cancel'

    def test_get_run(self):
        assert _resolve_orchestrator_permission('GET', '/v1/runs/abc') == 'run:view'

    def test_get_run_steps(self):
        assert _resolve_orchestrator_permission('GET', '/v1/runs/abc/steps') == 'run:view'

    def test_post_tasks_no_permission(self):
        """POST /v1/tasks is handled separately (body-based workspace_id)."""
        assert _resolve_orchestrator_permission('POST', '/v1/tasks') is None

    def test_unknown_returns_none(self):
        assert _resolve_orchestrator_permission('DELETE', '/v1/tasks/abc') is None


# ── _resolve_event_store_permission ──────────────────────────────

class TestResolveEventStorePermission:
    def test_task_timeline(self):
        assert _resolve_event_store_permission('GET', '/v1/tasks/abc/timeline') == 'task:view'

    def test_run_timeline(self):
        assert _resolve_event_store_permission('GET', '/v1/runs/abc/timeline') == 'run:view'

    def test_run_events_stream(self):
        assert _resolve_event_store_permission('GET', '/v1/runs/abc/events/stream') == 'run:view'

    def test_post_returns_none(self):
        assert _resolve_event_store_permission('POST', '/v1/tasks/abc/timeline') is None

    def test_unknown_returns_none(self):
        assert _resolve_event_store_permission('GET', '/v1/tasks/abc') is None
        assert _resolve_event_store_permission('GET', '/v1/runs') is None


# ── _inject_task_capabilities ─────────────────────────────────────

class TestInjectTaskCapabilities:
    def test_cancellable_task(self):
        data = {'task_status': 'running', 'latest_run_id': 'abc'}
        result = _inject_task_capabilities(data, has_cancel_perm=True)

        assert result['_capabilities']['can_cancel'] is True
        assert result['_capabilities']['can_view_run'] is True

    def test_completed_task_not_cancellable(self):
        data = {'task_status': 'completed', 'latest_run_id': 'abc'}
        result = _inject_task_capabilities(data, has_cancel_perm=True)

        assert result['_capabilities']['can_cancel'] is False

    def test_no_cancel_permission(self):
        data = {'task_status': 'running', 'latest_run_id': 'abc'}
        result = _inject_task_capabilities(data, has_cancel_perm=False)

        assert result['_capabilities']['can_cancel'] is False

    def test_no_latest_run(self):
        data = {'task_status': 'pending'}
        result = _inject_task_capabilities(data, has_cancel_perm=True)

        assert result['_capabilities']['can_view_run'] is False

    def test_pending_cancellable(self):
        data = {'task_status': 'pending'}
        result = _inject_task_capabilities(data, has_cancel_perm=True)
        assert result['_capabilities']['can_cancel'] is True

    def test_waiting_approval_cancellable(self):
        data = {'task_status': 'waiting_approval'}
        result = _inject_task_capabilities(data, has_cancel_perm=True)
        assert result['_capabilities']['can_cancel'] is True


# ── _inject_run_capabilities ──────────────────────────────────────

class TestInjectRunCapabilities:
    def test_always_has_can_view_task(self):
        data = {'run_id': 'abc', 'task_id': 'def'}
        result = _inject_run_capabilities(data)

        assert result['_capabilities']['can_view_task'] is True


# ── _build_json_response ─────────────────────────────────────────

class TestBuildJsonResponse:
    def _make_response(self, data: dict) -> Response:
        return Response(
            content=json.dumps(data),
            status_code=200,
            media_type='application/json',
        )

    def test_builds_response_with_updated_data(self):
        original = self._make_response({'task_id': 'abc'})
        data = {'task_id': 'abc', '_capabilities': {'can_cancel': True}}
        result = _build_json_response(data, original)

        body = json.loads(result.body)
        assert body['_capabilities']['can_cancel'] is True
        assert result.status_code == 200

    def test_content_length_matches_body(self):
        original = self._make_response({'task_id': 'abc'})
        data = {'task_id': 'abc', '_capabilities': {'can_cancel': True}}
        result = _build_json_response(data, original)

        body_len = len(result.body)
        cl = result.headers.get('content-length')
        if cl is not None:
            assert int(cl) == body_len

    def test_preserves_status_code(self):
        original = Response(
            content=json.dumps({'x': 1}),
            status_code=202,
            media_type='application/json',
        )
        result = _build_json_response({'x': 1, 'extra': True}, original)
        assert result.status_code == 202


# ── _rewrite_artifact_path ────────────────────────────────────────

class TestRewriteArtifactPath:
    def test_list_by_workspace(self):
        result = _rewrite_artifact_path('/v1/workspaces/ws-1/artifacts')
        assert result == '/internal/v1/artifacts'

    def test_get_by_id(self):
        result = _rewrite_artifact_path('/v1/workspaces/ws-1/artifacts/art-1')
        assert result == '/internal/v1/artifacts/art-1'

    def test_list_by_run(self):
        result = _rewrite_artifact_path('/v1/workspaces/ws-1/runs/run-1/artifacts')
        assert result == '/internal/v1/artifacts'

    def test_trailing_slash_list(self):
        result = _rewrite_artifact_path('/v1/workspaces/ws-1/artifacts/')
        assert result == '/internal/v1/artifacts'

    def test_unknown_path_passthrough(self):
        result = _rewrite_artifact_path('/v1/workspaces/ws-1/members')
        assert result == '/v1/workspaces/ws-1/members'


# ── _artifact_query_params ────────────────────────────────────────

class TestArtifactQueryParams:
    def test_list_by_workspace(self):
        params = _artifact_query_params('/v1/workspaces/ws-1/artifacts')
        assert params == {'workspace_id': 'ws-1'}

    def test_get_by_id(self):
        params = _artifact_query_params('/v1/workspaces/ws-1/artifacts/art-1')
        assert params == {'workspace_id': 'ws-1'}

    def test_list_by_run(self):
        params = _artifact_query_params('/v1/workspaces/ws-1/runs/run-1/artifacts')
        assert params == {'workspace_id': 'ws-1', 'run_id': 'run-1'}

    def test_non_artifact_path(self):
        params = _artifact_query_params('/v1/workspaces/ws-1/members')
        assert params == {'workspace_id': 'ws-1'}

    def test_no_workspace(self):
        params = _artifact_query_params('/v1/tasks/t-1')
        assert params == {}
