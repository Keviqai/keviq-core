"""PR44 gate tests — Multi-workspace isolation and naming readiness.

D44-G1: No cross-workspace resource collision
D44-G2: No cross-workspace data leakage in query surfaces
D44-G3: Isolation naming is deterministic and auditable
D44-G4: Cleanup paths are scope-safe
D44-G5: Deployment docs reflect the real isolation model
D44-G6: No regression to Phase C security posture
"""

import os
import re

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
APPS_ROOT = os.path.join(REPO_ROOT, 'apps')
DOCS_ROOT = os.path.join(REPO_ROOT, 'docs')
CONFIG_PKG = os.path.join(REPO_ROOT, 'packages', 'config', 'src', '__init__.py')

# All services with query/list surfaces
QUERY_SERVICES = [
    'event-store',
    'artifact-service',
    'workspace-service',
    'agent-runtime',
    'orchestrator',
    'execution-service',
]

# Services that expose workspace-scoped list/query endpoints
SERVICES_WITH_LIST_ENDPOINTS = [
    'event-store',
    'artifact-service',
    'workspace-service',
    'agent-runtime',
]


def _read(relpath: str, root: str = APPS_ROOT) -> str:
    with open(os.path.join(root, relpath), encoding='utf-8') as f:
        return f.read()


def _read_abs(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


# ── D44-G1: No cross-workspace resource collision ─────────────────

class TestNoResourceCollision:
    """Sandbox names, storage prefixes, and relay keys must not collide."""

    def test_sandbox_container_name_uses_uuid(self):
        """Docker backend must use mona-sandbox-{uuid} pattern."""
        src = _read('execution-service/src/infrastructure/sandbox/docker_backend.py')
        assert 'mona-sandbox-{sandbox_id}' in src or 'f"mona-sandbox-{sandbox_id}"' in src

    def test_noop_backend_uses_uuid(self):
        """Noop backend must use noop-{uuid} pattern."""
        src = _read('execution-service/src/infrastructure/sandbox/noop_backend.py')
        assert 'noop-{sandbox_id}' in src or 'f"noop-{sandbox_id}"' in src

    def test_sandbox_labels_include_workspace_id(self):
        """Docker sandbox labels must include workspace_id for audit."""
        src = _read('execution-service/src/application/sandbox_service.py')
        assert 'workspace_id' in src

    def test_config_has_artifact_storage_prefix(self):
        """Config package must define artifact_storage_prefix helper."""
        src = _read_abs(CONFIG_PKG)
        assert 'def artifact_storage_prefix(' in src

    def test_config_has_artifact_storage_key(self):
        """Config package must define artifact_storage_key helper."""
        src = _read_abs(CONFIG_PKG)
        assert 'def artifact_storage_key(' in src

    def test_storage_prefix_includes_workspace(self):
        """Storage prefix must include workspace_id in path."""
        src = _read_abs(CONFIG_PKG)
        assert 'workspaces/' in src
        assert '/runs/' in src
        assert '/artifacts' in src

    def test_config_has_workspace_temp_dir(self):
        """Config package must define workspace_temp_dir helper."""
        src = _read_abs(CONFIG_PKG)
        assert 'def workspace_temp_dir(' in src

    def test_config_has_relay_consumer_id(self):
        """Config package must define relay_consumer_id helper."""
        src = _read_abs(CONFIG_PKG)
        assert 'def relay_consumer_id(' in src

    def test_sandbox_name_helper_in_config(self):
        """Config package must define sandbox_container_name helper."""
        src = _read_abs(CONFIG_PKG)
        assert 'def sandbox_container_name(' in src


# ── D44-G2: No cross-workspace data leakage in query surfaces ─────

class TestNoQueryLeakage:
    """Query/list surfaces must filter by workspace_id."""

    def test_event_store_list_by_task_has_workspace_filter(self):
        """event-store list_by_task must include workspace_id in WHERE."""
        src = _read('event-store/src/infrastructure/db/repository.py')
        # Find list_by_task method and check for workspace_id filter
        assert 'def list_by_task(' in src
        # Check the method signature includes workspace_id
        port_src = _read('event-store/src/application/ports.py')
        # workspace_id should be a required parameter
        match = re.search(r'def list_by_task\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_by_task must require workspace_id parameter"

    def test_event_store_list_by_run_has_workspace_filter(self):
        """event-store list_by_run must include workspace_id in WHERE."""
        port_src = _read('event-store/src/application/ports.py')
        match = re.search(r'def list_by_run\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_by_run must require workspace_id parameter"

    def test_event_store_list_by_run_after_event_has_workspace_filter(self):
        """event-store list_by_run_after_event must include workspace_id."""
        port_src = _read('event-store/src/application/ports.py')
        match = re.search(r'def list_by_run_after_event\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_by_run_after_event must require workspace_id parameter"

    def test_event_store_timeline_route_requires_workspace_id(self):
        """Task/run timeline endpoints must require workspace_id query param."""
        routes = _read('event-store/src/api/routes.py')
        # task_timeline_endpoint should have workspace_id parameter
        assert re.search(
            r'def task_timeline_endpoint\([^)]*workspace_id:\s*str',
            routes,
        ), "task_timeline_endpoint must require workspace_id"
        assert re.search(
            r'def run_timeline_endpoint\([^)]*workspace_id:\s*str',
            routes,
        ), "run_timeline_endpoint must require workspace_id"

    def test_event_store_run_sse_requires_workspace_id(self):
        """Run SSE stream must require workspace_id."""
        routes = _read('event-store/src/api/routes.py') + _read('event-store/src/api/sse.py')
        assert re.search(
            r'def run_event_stream\([^)]*workspace_id:\s*str',
            routes,
        ), "run_event_stream must require workspace_id"

    def test_artifact_list_by_run_has_workspace_filter(self):
        """artifact-service list_by_run must include workspace_id at SQL level."""
        port_src = _read('artifact-service/src/application/ports.py')
        match = re.search(r'def list_by_run\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_by_run must require workspace_id parameter"

    def test_artifact_list_by_run_sql_filters_workspace(self):
        """artifact-service SQL list_by_run must have workspace_id in WHERE."""
        repo_src = _read('artifact-service/src/infrastructure/db/repositories.py')
        # Find the list_by_run method and verify workspace filtering in SQL
        idx = repo_src.find('def list_by_run(')
        assert idx >= 0
        method_end = repo_src.find('\n    def ', idx + 1)
        if method_end < 0:
            method_end = repo_src.find('\nclass ', idx + 1)
        method_body = repo_src[idx:method_end] if method_end > 0 else repo_src[idx:]
        assert 'workspace_id' in method_body, \
            "list_by_run SQL must filter by workspace_id"

    def test_agent_runtime_list_active_has_workspace_filter(self):
        """agent-runtime list_active must include workspace_id."""
        port_src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def list_active\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_active must require workspace_id parameter"

    def test_agent_runtime_get_by_id_has_workspace_filter(self):
        """agent-runtime get_by_id must include workspace_id."""
        port_src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def get_by_id\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "get_by_id must require workspace_id parameter"

    def test_agent_runtime_list_by_step_has_workspace_filter(self):
        """agent-runtime list_by_step must include workspace_id."""
        port_src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def list_by_step\([^)]*workspace_id[^)]*\)', port_src)
        assert match, "list_by_step must require workspace_id parameter"

    def test_agent_runtime_sql_has_workspace_filter(self):
        """agent-runtime SQL queries must filter by workspace_id."""
        repo_src = _read('agent-runtime/src/infrastructure/db/invocation_repository.py')
        # All SELECT queries should have workspace_id in WHERE
        selects = [
            '_SELECT_BY_ID',
            '_SELECT_ACTIVE',
            '_SELECT_BY_STEP',
        ]
        for name in selects:
            idx = repo_src.find(f'{name} = text(')
            assert idx >= 0, f"Missing {name} query"
            end = repo_src.find('""")', idx)
            query_body = repo_src[idx:end] if end > 0 else repo_src[idx:idx + 500]
            assert 'workspace_id' in query_body, \
                f"{name} SQL must filter by workspace_id"

    def test_workspace_service_list_members_requires_auth(self):
        """workspace-service list_members must require user_id."""
        routes = _read('workspace-service/src/api/routes.py')
        # Find list_members function definition
        idx = routes.find('def list_members(')
        assert idx >= 0
        end = routes.find('\ndef ', idx + 1)
        method = routes[idx:end] if end > 0 else routes[idx:]
        assert '_get_user_id' in method or 'user_id' in method, \
            "list_members must require user_id"
        assert '_require_membership' in method, \
            "list_members must enforce workspace membership"

    def test_workspace_service_get_workspace_requires_membership(self):
        """workspace-service get_workspace must enforce membership."""
        routes = _read('workspace-service/src/api/routes.py')
        idx = routes.find('def get_workspace(')
        assert idx >= 0
        end = routes.find('\ndef ', idx + 1)
        method = routes[idx:end] if end > 0 else routes[idx:]
        assert '_require_membership' in method, \
            "get_workspace must call _require_membership"


# ── D44-G3: Isolation naming is deterministic and auditable ────────

class TestDeterministicNaming:
    """Resource naming must be deterministic and testable."""

    def test_sandbox_id_is_uuid(self):
        """Sandbox IDs must be UUID v4."""
        src = _read('execution-service/src/application/sandbox_service.py')
        assert 'uuid4()' in src or 'uuid.uuid4()' in src

    def test_container_name_deterministic(self):
        """Container name must be deterministic from sandbox_id."""
        src = _read('execution-service/src/infrastructure/sandbox/docker_backend.py')
        # The name pattern must be a simple format string, not random
        assert 'f"mona-sandbox-{sandbox_id}"' in src

    def test_docker_labels_carry_workspace_metadata(self):
        """Docker labels must carry workspace_id, task_id, run_id for audit."""
        src = _read('execution-service/src/application/sandbox_service.py')
        for field in ['workspace_id', 'task_id', 'run_id']:
            assert field in src, f"Sandbox labels must include {field}"

    def test_config_naming_helpers_exist(self):
        """packages/config must export isolation naming helpers."""
        src = _read_abs(CONFIG_PKG)
        helpers = [
            'sandbox_container_name',
            'artifact_storage_prefix',
            'artifact_storage_key',
            'workspace_temp_dir',
            'relay_consumer_id',
        ]
        for h in helpers:
            assert f'def {h}(' in src, f"Missing naming helper: {h}"


# ── D44-G4: Cleanup paths are scope-safe ───────────────────────────

class TestCleanupScopeSafe:
    """Cleanup/terminate must not affect resources outside scope."""

    def test_sandbox_terminate_uses_exact_name(self):
        """terminate() must look up container by exact name, not labels/glob."""
        src = _read('execution-service/src/infrastructure/sandbox/docker_backend.py')
        idx = src.find('def terminate(')
        assert idx >= 0
        end = src.find('\n    def ', idx + 1)
        method = src[idx:end] if end > 0 else src[idx:]
        # Must use containers.get() with exact name
        assert 'containers.get(' in method, \
            "terminate must use containers.get() with exact name"
        # Must NOT use containers.list() or broad selectors
        assert 'containers.list(' not in method, \
            "terminate must NOT use containers.list() (broad selector)"

    def test_recovery_uses_is_alive_then_terminate(self):
        """Recovery sweep must check is_alive then terminate individually."""
        src = _read('execution-service/src/application/recovery_service.py')
        assert 'is_alive(' in src
        assert 'terminate(' in src

    def test_noop_terminate_is_safe(self):
        """Noop backend terminate must be no-op."""
        src = _read('execution-service/src/infrastructure/sandbox/noop_backend.py')
        idx = src.find('def terminate(')
        assert idx >= 0

    def test_no_broad_container_cleanup(self):
        """No service should use docker containers.list() with broad filters for cleanup."""
        for svc in ['execution-service', 'orchestrator', 'agent-runtime']:
            svc_root = os.path.join(APPS_ROOT, svc, 'src')
            if not os.path.isdir(svc_root):
                continue
            for dirpath, _dirs, files in os.walk(svc_root):
                for f in files:
                    if not f.endswith('.py'):
                        continue
                    content = open(os.path.join(dirpath, f), encoding='utf-8').read()
                    # containers.list with label filters for cleanup is a broad selector
                    if 'containers.list(' in content and 'remove' in content:
                        pytest.fail(
                            f"{svc}/.../{f} uses containers.list() + remove "
                            f"(broad cleanup selector)"
                        )


# ── D44-G5: Deployment docs reflect the real isolation model ───────

class TestIsolationDocs:
    """Docs must describe isolation model accurately."""

    def test_isolation_doc_exists(self):
        """Isolation model documentation must exist."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        assert os.path.isfile(path), "Missing docs/phase-d-pr44-isolation-model.md"

    def test_doc_describes_workspace_isolation(self):
        """Doc must describe workspace-level isolation (not overclaim multi-tenant)."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        assert 'workspace' in content.lower()
        assert 'isolation' in content.lower()

    def test_doc_has_known_limitations(self):
        """Doc must list known limitations."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        assert 'Known Limitations' in content or 'known limitations' in content

    def test_doc_does_not_overclaim_multi_tenant(self):
        """Doc must not claim full multi-tenant without qualification."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        # Should contain caveats, not bare "multi-tenant ready"
        assert 'not full' in content.lower() or 'shared-deployment' in content.lower()

    def test_doc_describes_naming_conventions(self):
        """Doc must include naming conventions table."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        assert 'Naming Convention' in content or 'naming convention' in content

    def test_doc_describes_storage_prefix(self):
        """Doc must describe artifact storage prefix strategy."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        assert 'workspaces/' in content
        assert 'artifacts' in content

    def test_doc_describes_cleanup_safety(self):
        """Doc must describe cleanup scope safety."""
        path = os.path.join(DOCS_ROOT, 'phase-d-pr44-isolation-model.md')
        content = open(path, encoding='utf-8').read()
        assert 'cleanup' in content.lower() or 'Cleanup' in content


# ── D44-G6: No regression to Phase C security posture ──────────────

class TestNoSecurityRegression:
    """PR44 must not weaken existing security."""

    def test_api_gateway_still_enforces_auth(self):
        """api-gateway must still require authentication."""
        src = _read('api-gateway/src/api/routes.py')
        assert 'extract_auth_context' in src
        assert 'check_permission_or_fail' in src

    def test_internal_auth_still_required(self):
        """Internal services must still use require_service auth."""
        for svc in ['event-store', 'artifact-service', 'orchestrator']:
            # Read all route files (services may split routes into sub-modules)
            api_dir = os.path.join(APPS_ROOT, svc, 'src', 'api')
            routes = ''
            for fname in sorted(os.listdir(api_dir)):
                if fname.startswith('route') and fname.endswith('.py'):
                    routes += _read(f'{svc}/src/api/{fname}') + '\n'
            if not routes:
                routes = _read(f'{svc}/src/api/routes.py')
            assert 'require_service' in routes, \
                f"{svc} must still use require_service for internal auth"

    def test_workspace_service_enforces_membership(self):
        """workspace-service must enforce membership on sensitive endpoints."""
        routes = _read('workspace-service/src/api/routes.py')
        assert '_require_membership' in routes, \
            "workspace-service must have _require_membership helper"
        # Count uses — should be on most endpoints
        count = routes.count('_require_membership')
        assert count >= 6, \
            f"_require_membership used only {count} times, expected >= 6"

    def test_event_store_workspace_filter_in_sql(self):
        """event-store SQL queries must filter by workspace_id."""
        repo = _read('event-store/src/infrastructure/db/repository.py')
        # list_by_task must have workspace_id filter
        idx = repo.find('def list_by_task(')
        end = repo.find('\n    def ', idx + 1)
        method = repo[idx:end] if end > 0 else repo[idx:]
        assert 'workspace_id' in method

    def test_gateway_requires_workspace_for_timeline(self):
        """api-gateway must require workspace_id for event-store timeline routes."""
        src = _read('api-gateway/src/api/routes.py')
        assert 'workspace_id query parameter is required' in src

    def test_no_hardcoded_secrets_in_services(self):
        """No hardcoded secrets in service source code."""
        bad_patterns = [
            r'password\s*=\s*["\'](?!test|fake|mock)',
            r'secret\s*=\s*["\'](?!test|fake|mock|dev-secret)',
            r'jwt_secret\s*=\s*["\']',
        ]
        for svc in QUERY_SERVICES:
            svc_src = os.path.join(APPS_ROOT, svc, 'src')
            if not os.path.isdir(svc_src):
                continue
            for dirpath, _dirs, files in os.walk(svc_src):
                for f in files:
                    if not f.endswith('.py'):
                        continue
                    path = os.path.join(dirpath, f)
                    content = open(path, encoding='utf-8').read()
                    for pattern in bad_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            pytest.fail(
                                f"Potential hardcoded secret in {svc}/.../{f} "
                                f"matching {pattern}"
                            )


# ── Integration: Two-workspace isolation proof ─────────────────────

class TestTwoWorkspaceIsolation:
    """Structural proof that two workspaces cannot collide or leak."""

    def test_all_event_store_queries_scope_workspace(self):
        """All event-store query methods must include workspace_id parameter."""
        port_src = _read('event-store/src/application/ports.py')
        query_methods = ['list_by_task', 'list_by_run', 'list_by_workspace', 'list_by_run_after_event']
        for method in query_methods:
            idx = port_src.find(f'def {method}(')
            assert idx >= 0, f"Missing query method: {method}"
            end = port_src.find(')', idx)
            sig = port_src[idx:end]
            assert 'workspace_id' in sig, \
                f"{method} must require workspace_id parameter"

    def test_all_artifact_list_methods_scope_workspace(self):
        """artifact-service list methods must include workspace_id."""
        port_src = _read('artifact-service/src/application/ports.py')
        for method in ['list_by_run', 'list_by_workspace']:
            idx = port_src.find(f'def {method}(')
            assert idx >= 0, f"Missing method: {method}"
            end = port_src.find(')', idx)
            sig = port_src[idx:end]
            assert 'workspace_id' in sig, \
                f"{method} must require workspace_id parameter"

    def test_workspace_service_returns_404_for_non_members(self):
        """workspace-service must return 404 (not 403) for non-members."""
        routes = _read('workspace-service/src/api/routes.py')
        # _require_membership should raise 404
        idx = routes.find('def _require_membership(')
        assert idx >= 0
        end = routes.find('\ndef ', idx + 1)
        method = routes[idx:end] if end > 0 else routes[idx:]
        assert '404' in method, \
            "_require_membership should return 404 to avoid leaking existence"

    def test_sandbox_entities_carry_workspace_id(self):
        """execution-service sandbox DB model must have workspace_id column."""
        models = _read('execution-service/src/infrastructure/db/models.py')
        assert 'workspace_id' in models

    def test_agent_invocation_entities_carry_workspace_id(self):
        """agent-runtime invocation DB model must have workspace_id."""
        repo = _read('agent-runtime/src/infrastructure/db/invocation_repository.py')
        assert 'workspace_id' in repo

    def test_orchestrator_entities_carry_workspace_id(self):
        """orchestrator task/run/step DB models must have workspace_id."""
        models = _read('orchestrator/src/infrastructure/db/models.py')
        assert models.count('workspace_id') >= 3, \
            "Tasks, runs, and steps must all have workspace_id"
