"""Unit tests for auth middleware permission matching — task/run routes."""

from src.application.auth_middleware import has_permission, match_permission


class TestMatchPermissionTaskRoutes:
    def test_tasks_root_is_auth_only(self):
        perm, ws = match_permission('POST', '/v1/tasks')
        assert perm is None
        assert ws is None

    def test_get_task_by_id_is_auth_only(self):
        perm, ws = match_permission('GET', '/v1/tasks/abc-123')
        assert perm is None
        assert ws is None

    def test_cancel_task_is_auth_only(self):
        perm, ws = match_permission('POST', '/v1/tasks/abc-123/cancel')
        assert perm is None
        assert ws is None


class TestMatchPermissionRunRoutes:
    def test_get_run_is_auth_only(self):
        perm, ws = match_permission('GET', '/v1/runs/abc-123')
        assert perm is None
        assert ws is None

    def test_get_run_steps_is_auth_only(self):
        perm, ws = match_permission('GET', '/v1/runs/abc-123/steps')
        assert perm is None
        assert ws is None


class TestMatchPermissionWorkspaceRoutesUnchanged:
    """Verify workspace routes still work after adding task/run handling."""

    def test_workspace_view(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-123')
        assert perm == 'workspace:view'
        assert ws == 'ws-123'

    def test_workspace_members(self):
        perm, ws = match_permission('POST', '/v1/workspaces/ws-123/members')
        assert perm == 'workspace:manage_members'
        assert ws == 'ws-123'

    def test_workspace_policies(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-123/policies')
        assert perm == 'workspace:view'
        assert ws == 'ws-123'


class TestMatchPermissionArtifactRoutes:
    """Verify artifact query routes have pre-proxy workspace:view checks."""

    def test_list_artifacts(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-1/artifacts')
        assert perm == 'workspace:view'
        assert ws == 'ws-1'

    def test_get_artifact_by_id(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-1/artifacts/art-1')
        assert perm == 'workspace:view'
        assert ws == 'ws-1'

    def test_list_artifacts_by_run(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-1/runs/run-1/artifacts')
        assert perm == 'workspace:view'
        assert ws == 'ws-1'

    def test_post_artifacts_not_allowed(self):
        """POST to artifact paths should NOT match any permission (no write routes)."""
        perm, ws = match_permission('POST', '/v1/workspaces/ws-1/artifacts')
        assert perm is None

    def test_delete_artifacts_not_allowed(self):
        perm, ws = match_permission('DELETE', '/v1/workspaces/ws-1/artifacts/art-1')
        assert perm is None

    def test_trailing_slash(self):
        perm, ws = match_permission('GET', '/v1/workspaces/ws-1/artifacts/')
        assert perm == 'workspace:view'
        assert ws == 'ws-1'
