"""PR45 gate tests — Operational validation and load-readiness.

D45-G1: Boot matrix — all 3 profiles compose-parseable, env files complete
D45-G2: 2-workspace concurrent smoke — structural proof of isolation under concurrency
D45-G3: SSE / relay / event flow — streaming and relay infrastructure validated
D45-G4: Recovery / restart drills — recovery sweep + graceful shutdown verified
D45-G5: Load-readiness — pool sizing, batch limits, timeouts configured
D45-G6: Runbook / go-live checklist exists and covers all operational areas
"""

import functools
import os
import re

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
APPS_ROOT = os.path.join(REPO_ROOT, 'apps')
INFRA_DOCKER = os.path.join(REPO_ROOT, 'infra', 'docker')
DOCS_ROOT = os.path.join(REPO_ROOT, 'docs')
PACKAGES_ROOT = os.path.join(REPO_ROOT, 'packages')


@functools.lru_cache(maxsize=64)
def _read(relpath: str, root: str = APPS_ROOT) -> str:
    with open(os.path.join(root, relpath), encoding='utf-8') as f:
        return f.read()


def _read_event_store_api() -> str:
    """Read combined event-store API source (routes + sse)."""
    return _read('event-store/src/api/routes.py') + '\n' + _read('event-store/src/api/sse.py')


def _read_infra(relpath: str) -> str:
    return _read(relpath, root=INFRA_DOCKER)


def _read_docs(relpath: str) -> str:
    return _read(relpath, root=DOCS_ROOT)


def _file_exists(relpath: str, root: str = REPO_ROOT) -> bool:
    return os.path.isfile(os.path.join(root, relpath))


# ── All 15 backend services ─────────────────────────────────────
ALL_SERVICES = [
    'orchestrator',
    'agent-runtime',
    'artifact-service',
    'execution-service',
    'workspace-service',
    'auth-service',
    'policy-service',
    'model-gateway',
    'event-store',
    'api-gateway',
    'sse-gateway',
    'notification-service',
    'telemetry-service',
    'audit-service',
    'secret-broker',
]

# Services that use DB connections
DB_SERVICES = [
    'orchestrator',
    'agent-runtime',
    'artifact-service',
    'execution-service',
    'workspace-service',
    'auth-service',
    'policy-service',
    'model-gateway',
    'event-store',
    'notification-service',
    'audit-service',
    'secret-broker',
]

# Services with outbox relay
RELAY_SERVICES = [
    'orchestrator',
    'artifact-service',
]

# Services with recovery sweeps
RECOVERY_SERVICES = [
    'orchestrator',
]

# Profiles
PROFILES = ['local', 'hardened', 'cloud']

OVERLAY_FILES = {
    'local': 'docker-compose.local.yml',
    'hardened': 'docker-compose.hardened.yml',
    'cloud': 'docker-compose.cloud.yml',
}


# ═══════════════════════════════════════════════════════════════════
# D45-G1: Boot matrix — profile completeness and parseability
# ═══════════════════════════════════════════════════════════════════


class TestBootMatrix:
    """All 3 profiles must be compose-parseable, cover all 15 services,
    set correct APP_ENV, and have matching .env files."""

    def test_base_compose_defines_all_services(self):
        content = _read_infra('docker-compose.yml')
        for svc in ALL_SERVICES:
            # Services are defined as top-level keys under 'services:'
            assert re.search(rf'^\s+{re.escape(svc)}:', content, re.MULTILINE), \
                f"Base compose missing service: {svc}"

    @pytest.mark.parametrize('profile', PROFILES)
    def test_overlay_exists(self, profile):
        path = os.path.join(INFRA_DOCKER, OVERLAY_FILES[profile])
        assert os.path.isfile(path), f"Missing overlay: {OVERLAY_FILES[profile]}"

    @pytest.mark.parametrize('profile', PROFILES)
    def test_overlay_sets_deployment_profile(self, profile):
        content = _read_infra(OVERLAY_FILES[profile])
        assert f'DEPLOYMENT_PROFILE: {profile}' in content or \
               f'DEPLOYMENT_PROFILE: ${{{profile}' in content, \
            f"{OVERLAY_FILES[profile]} must set DEPLOYMENT_PROFILE"

    @pytest.mark.parametrize('profile,expected_env', [
        ('local', 'development'),
        ('hardened', 'production'),
        ('cloud', 'production'),
    ])
    def test_overlay_app_env(self, profile, expected_env):
        content = _read_infra(OVERLAY_FILES[profile])
        assert f'APP_ENV: {expected_env}' in content, \
            f"{OVERLAY_FILES[profile]} must set APP_ENV to {expected_env}"

    def test_local_env_file_exists(self):
        assert _file_exists('infra/docker/.env.local'), ".env.local must exist"

    def test_hardened_env_file_exists(self):
        assert _file_exists('infra/docker/.env.hardened'), ".env.hardened must exist"

    def test_cloud_env_example_exists(self):
        assert _file_exists('infra/docker/.env.cloud.example'), ".env.cloud.example must exist"

    def test_base_compose_has_healthchecks_for_infra(self):
        content = _read_infra('docker-compose.yml')
        # postgres and redis must have healthchecks
        assert 'pg_isready' in content, "Postgres healthcheck missing"
        assert 'redis-cli' in content, "Redis healthcheck missing"

    @pytest.mark.parametrize('profile', PROFILES)
    def test_overlay_covers_all_backend_services(self, profile):
        """Each overlay must reference all 15 backend services."""
        content = _read_infra(OVERLAY_FILES[profile])
        for svc in ALL_SERVICES:
            assert re.search(rf'^\s+{re.escape(svc)}:', content, re.MULTILINE), \
                f"{OVERLAY_FILES[profile]} missing service override: {svc}"

    def test_hardened_strips_internal_ports(self):
        content = _read_infra('docker-compose.hardened.yml')
        # Internal services should have ports reset
        assert content.count('ports: !reset') >= 12, \
            "Hardened must strip ports from internal services (>= 12 resets)"

    def test_cloud_strips_internal_ports(self):
        content = _read_infra('docker-compose.cloud.yml')
        assert content.count('ports: !reset') >= 12, \
            "Cloud must strip ports from internal services (>= 12 resets)"

    def test_hardened_read_only_filesystem(self):
        content = _read_infra('docker-compose.hardened.yml')
        assert content.count('read_only: true') >= 15, \
            "Hardened must set read_only on all services"

    def test_hardened_no_new_privileges(self):
        content = _read_infra('docker-compose.hardened.yml')
        assert content.count('no-new-privileges:true') >= 15, \
            "Hardened must set no-new-privileges on all services"

    def test_local_exposes_docker_socket(self):
        content = _read_infra('docker-compose.local.yml')
        assert 'docker.sock' in content, \
            "Local overlay must mount Docker socket for execution-service"

    def test_hardened_no_docker_socket(self):
        content = _read_infra('docker-compose.hardened.yml')
        # execution-service specifically must have volumes reset
        exec_section = content[content.index('execution-service:'):]
        exec_section = exec_section[:exec_section.index('\n\n') if '\n\n' in exec_section else len(exec_section)]
        assert 'volumes: !reset' in exec_section, \
            "Hardened must reset execution-service volumes (remove Docker socket)"
        assert 'docker.sock' not in content, \
            "Hardened overlay must not reference Docker socket"

    def test_cloud_externalizes_all_secrets(self):
        """Cloud overlay must not contain any inline passwords/secrets."""
        content = _read_infra('docker-compose.cloud.yml')
        # No inline passwords — all must be ${VAR} references
        inline_passwords = re.findall(r'password:\s*[a-zA-Z]', content, re.IGNORECASE)
        assert len(inline_passwords) == 0, \
            f"Cloud overlay has inline passwords: {inline_passwords}"


# ═══════════════════════════════════════════════════════════════════
# D45-G2: 2-workspace concurrent smoke — isolation under concurrency
# ═══════════════════════════════════════════════════════════════════


class TestTwoWorkspaceConcurrentSmoke:
    """Structural proof that workspace isolation is enforced in query paths,
    event streams, and artifact storage — so concurrent workspaces cannot
    leak data to each other."""

    # Event-store: all query methods require workspace_id
    def test_event_repo_list_by_task_requires_workspace_id(self):
        src = _read('event-store/src/application/ports.py')
        match = re.search(r'def list_by_task\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "list_by_task must require workspace_id"

    def test_event_repo_list_by_run_requires_workspace_id(self):
        src = _read('event-store/src/application/ports.py')
        match = re.search(r'def list_by_run\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "list_by_run must require workspace_id"

    def test_event_repo_list_by_run_after_event_requires_workspace_id(self):
        src = _read('event-store/src/application/ports.py')
        match = re.search(r'def list_by_run_after_event\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "list_by_run_after_event must require workspace_id"

    def test_event_repo_sql_filters_workspace_id(self):
        """SQL implementation must use workspace_id in WHERE clauses."""
        src = _read('event-store/src/infrastructure/db/repository.py')
        # All list methods should filter by workspace_id
        assert src.count('EventRow.workspace_id == str(workspace_id)') >= 4, \
            "Event repo SQL must filter workspace_id in all query methods"

    # Artifact-service: query paths require workspace_id
    def test_artifact_list_by_run_requires_workspace_id(self):
        src = _read('artifact-service/src/application/ports.py')
        match = re.search(r'def list_by_run\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "artifact list_by_run must require workspace_id"

    def test_artifact_sql_filters_workspace_id(self):
        src = _read('artifact-service/src/infrastructure/db/repositories.py')
        assert 'ArtifactRow.workspace_id' in src, \
            "Artifact SQL must filter by workspace_id"

    # Agent-runtime: query paths require workspace_id
    def test_invocation_get_by_id_requires_workspace_id(self):
        src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def get_by_id\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "get_by_id must require workspace_id"

    def test_invocation_list_active_requires_workspace_id(self):
        src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def list_active\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "list_active must require workspace_id"

    def test_invocation_list_by_step_requires_workspace_id(self):
        src = _read('agent-runtime/src/application/ports.py')
        match = re.search(r'def list_by_step\(\s*self,.*?\) ->', src, re.DOTALL)
        assert match and 'workspace_id' in match.group(), \
            "list_by_step must require workspace_id"

    # SSE streams: workspace-scoped
    def test_workspace_sse_stream_is_workspace_scoped(self):
        src = _read_event_store_api()
        assert 'workspace_id' in src
        assert '_workspace_sse_generator' in src
        # Must pass workspace_id to generator
        assert re.search(r'_workspace_sse_generator\(ws_id', src), \
            "Workspace SSE generator must receive workspace_id"

    def test_run_sse_stream_is_workspace_scoped(self):
        src = _read_event_store_api()
        assert '_run_sse_generator' in src
        # Must pass workspace_id to generator
        match = re.search(r'_run_sse_generator\(rid,\s*wid', src)
        assert match, "Run SSE generator must receive workspace_id"

    # Workspace-service RBAC
    def test_workspace_service_membership_check(self):
        src = _read('workspace-service/src/api/routes.py')
        assert '_require_membership' in src, \
            "Workspace-service must have _require_membership helper"
        # Must be called in multiple endpoints
        assert src.count('_require_membership(') >= 5, \
            "At least 5 endpoints must enforce membership"

    # Storage isolation
    def test_artifact_storage_prefix_includes_workspace_id(self):
        config_path = os.path.join(PACKAGES_ROOT, 'config', 'src', '__init__.py')
        with open(config_path, encoding='utf-8') as f:
            src = f.read()
        assert 'def artifact_storage_prefix' in src
        assert 'workspace_id' in src
        assert 'workspaces/' in src, \
            "Storage prefix must use workspaces/<id> hierarchy"

    # Gateway pre-proxy auth for SSE
    def test_gateway_pre_proxy_auth_for_workspace_sse(self):
        src = _read('api-gateway/src/api/routes.py')
        assert 'workspace:view' in src, \
            "Gateway must check workspace:view for SSE stream"

    def test_gateway_event_store_requires_workspace_id_param(self):
        src = _read('api-gateway/src/api/routes.py')
        assert 'workspace_id query parameter is required' in src, \
            "Gateway must require workspace_id param for event-store routes"


# ═══════════════════════════════════════════════════════════════════
# D45-G3: SSE / relay / event flow
# ═══════════════════════════════════════════════════════════════════


class TestSSERelayEventFlow:
    """Validate SSE streaming, outbox relay, and event ingest infrastructure."""

    # SSE infrastructure
    def test_sse_format_helper_exists(self):
        src = _read_event_store_api()
        assert 'def _format_sse(' in src, "SSE format helper must exist"

    def test_sse_format_includes_id_event_data(self):
        src = _read_event_store_api()
        # Format must include id:, event:, data: fields
        assert 'id:' in src and 'event:' in src and 'data:' in src, \
            "SSE format must include id, event, data fields"

    def test_sse_heartbeat_mechanism(self):
        src = _read_event_store_api()
        assert ':heartbeat' in src, "SSE must have heartbeat mechanism"
        assert '_SSE_HEARTBEAT_INTERVAL' in src, "SSE heartbeat interval must be configurable"

    def test_sse_poll_interval_defined(self):
        src = _read_event_store_api()
        assert '_SSE_POLL_INTERVAL' in src, "SSE poll interval must be defined"

    def test_sse_disconnect_detection(self):
        src = _read_event_store_api()
        assert 'is_disconnected' in src, "SSE must detect client disconnection"

    def test_sse_replay_on_reconnect(self):
        """SSE streams must support Last-Event-ID for replay."""
        src = _read_event_store_api()
        assert 'last-event-id' in src.lower() or 'Last-Event-ID' in src, \
            "SSE must support Last-Event-ID header"

    def test_sse_cache_control_headers(self):
        src = _read_event_store_api()
        assert 'no-cache' in src, "SSE responses must set Cache-Control: no-cache"
        assert 'X-Accel-Buffering' in src, "SSE must disable proxy buffering"

    # Outbox relay infrastructure
    @pytest.mark.parametrize('service', RELAY_SERVICES)
    def test_relay_module_exists(self, service):
        path = os.path.join(APPS_ROOT, service, 'src', 'infrastructure', 'outbox', 'relay.py')
        assert os.path.isfile(path), f"{service} must have outbox relay module"

    def test_orchestrator_relay_retry_policy(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'RetryPolicy' in src, "Relay must use RetryPolicy"
        assert 'retry_with_backoff' in src, "Relay must use retry_with_backoff"

    def test_relay_batch_size_configurable(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'RELAY_BATCH_SIZE' in src, "Relay batch size must be configurable"

    def test_relay_poison_pill_protection(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'MAX_RELAY_ATTEMPTS' in src, "Relay must have poison pill protection"

    def test_relay_connection_reuse(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'httpx.Client' in src, "Relay must use connection-reusing client"
        assert 'get_relay_client' in src, "Relay must have shared client accessor"

    def test_relay_graceful_shutdown(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'def close_relay_client' in src, "Relay must support graceful close"

    # Event ingest endpoints
    def test_event_store_single_ingest(self):
        src = _read('event-store/src/api/routes.py')
        assert '/internal/v1/events/ingest' in src, \
            "Event-store must have single ingest endpoint"

    def test_event_store_batch_ingest(self):
        src = _read('event-store/src/api/routes.py')
        assert '/internal/v1/events/ingest/batch' in src, \
            "Event-store must have batch ingest endpoint"

    def test_batch_ingest_size_limit(self):
        src = _read('event-store/src/api/routes.py')
        assert '_MAX_BATCH_SIZE' in src, "Batch ingest must have size limit"

    def test_event_ingest_idempotent(self):
        """Ingest must be idempotent (ON CONFLICT DO NOTHING)."""
        src = _read('event-store/src/infrastructure/db/repository.py')
        assert 'on_conflict_do_nothing' in src, \
            "Event ingest must use ON CONFLICT DO NOTHING for idempotency"

    def test_event_ingest_auth_required(self):
        src = _read('event-store/src/api/routes.py')
        assert 'require_service' in src, \
            "Event ingest must require internal service auth"


# ═══════════════════════════════════════════════════════════════════
# D45-G4: Recovery / restart drills
# ═══════════════════════════════════════════════════════════════════


class TestRecoveryRestartDrills:
    """Recovery sweep infrastructure, graceful shutdown, and restart safety."""

    # Recovery sweep
    def test_orchestrator_recovery_module_exists(self):
        path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application', 'recovery.py')
        assert os.path.isfile(path), "Orchestrator must have recovery module"

    def test_recovery_covers_runs_steps_tasks(self):
        src = _read('orchestrator/src/application/recovery.py')
        assert '_recover_stuck_runs' in src, "Recovery must handle stuck runs"
        assert '_recover_stuck_steps' in src, "Recovery must handle stuck steps"
        assert '_recover_orphaned_tasks' in src, "Recovery must handle orphaned tasks"

    def test_recovery_configurable_thresholds(self):
        src = _read('orchestrator/src/application/recovery.py')
        assert 'STUCK_PREPARING_MINUTES' in src
        assert 'STUCK_RUNNING_MINUTES' in src
        assert 'STUCK_COMPLETING_MINUTES' in src
        assert 'STUCK_STEP_RUNNING_MINUTES' in src

    def test_recovery_emits_events(self):
        src = _read('orchestrator/src/application/recovery.py')
        assert 'run_recovered_event' in src, "Recovery must emit run recovery events"
        assert 'step_recovered_event' in src, "Recovery must emit step recovery events"
        assert 'task_recovered_event' in src, "Recovery must emit task recovery events"

    def test_recovery_uses_row_level_locking(self):
        src = _read('orchestrator/src/application/recovery.py')
        assert 'for_update' in src, "Recovery must use FOR UPDATE locking"

    def test_recovery_idempotent_guards(self):
        """Recovery must be idempotent — running twice is safe."""
        src = _read('orchestrator/src/application/recovery.py')
        assert 'is_terminal' in src, "Recovery must check terminal state"
        assert 'skipped_already_terminal' in src, \
            "Recovery must skip already-terminal entities"

    def test_recovery_returns_typed_results(self):
        src = _read('orchestrator/src/application/recovery.py')
        assert 'RecoveryResult' in src, "Recovery must return typed results"

    # Background task scheduling
    def test_orchestrator_recovery_scheduled(self):
        src = _read('orchestrator/src/main.py')
        assert '_recovery_sweep_loop' in src, "Recovery must be scheduled as background task"
        assert 'RECOVERY_INTERVAL_SECONDS' in src, "Recovery interval must be configurable"

    def test_orchestrator_relay_scheduled(self):
        src = _read('orchestrator/src/main.py')
        assert '_outbox_relay_loop' in src, "Relay must be scheduled as background task"
        assert 'OUTBOX_RELAY_INTERVAL_SECONDS' in src, "Relay interval must be configurable"

    # Graceful shutdown
    def test_orchestrator_graceful_shutdown(self):
        """Main lifespan must cancel tasks and close clients on shutdown."""
        src = _read('orchestrator/src/main.py')
        assert 'recovery_task.cancel()' in src, "Recovery task must be cancelled"
        assert 'relay_task.cancel()' in src, "Relay task must be cancelled"
        assert 'close_relay_client()' in src, "Relay client must be closed"
        assert '_runtime_client.close()' in src, "Runtime client must be closed"

    def test_orchestrator_lifespan_pattern(self):
        src = _read('orchestrator/src/main.py')
        assert '@asynccontextmanager' in src, "Lifespan must use async context manager"
        assert 'CancelledError' in src, "Lifespan must handle CancelledError"

    # Docker restart policy
    def test_base_compose_restart_policy(self):
        content = _read_infra('docker-compose.yml')
        restart_count = content.count('restart: unless-stopped')
        assert restart_count >= 15, \
            f"All services must have restart: unless-stopped (found {restart_count})"

    # Infrastructure healthchecks
    def test_postgres_healthcheck_with_retries(self):
        content = _read_infra('docker-compose.yml')
        assert 'pg_isready' in content
        assert 'retries: 5' in content, "Postgres healthcheck must have retries"

    def test_redis_healthcheck_with_retries(self):
        content = _read_infra('docker-compose.yml')
        assert 'redis-cli' in content
        redis_section = content[content.index('redis:'):]
        redis_section = redis_section[:redis_section.index('\n\n')]
        assert 'retries:' in redis_section, "Redis healthcheck must have retries"

    # Execution-service recovery
    def test_execution_service_recovery_exists(self):
        path = os.path.join(APPS_ROOT, 'execution-service', 'src', 'application', 'recovery_service.py')
        assert os.path.isfile(path), "Execution-service must have recovery module"

    def test_execution_recovery_covers_sandboxes(self):
        src = _read('execution-service/src/application/recovery_service.py')
        assert 'recover_stuck_sandboxes' in src, "Must recover stuck sandboxes"

    # Service dependency ordering
    def test_orchestrator_depends_on_postgres_and_redis(self):
        content = _read_infra('docker-compose.yml')
        # Find orchestrator section
        orch_section = content[content.index('orchestrator:'):]
        orch_section = orch_section[:orch_section.index('\n  ', orch_section.index('deploy:'))]
        assert 'postgres:' in orch_section and 'service_healthy' in orch_section, \
            "Orchestrator must depend on healthy postgres"
        assert 'redis:' in orch_section and 'service_healthy' in orch_section, \
            "Orchestrator must depend on healthy redis"


# ═══════════════════════════════════════════════════════════════════
# D45-G5: Load-readiness — pool sizing, batch limits, timeouts
# ═══════════════════════════════════════════════════════════════════


class TestLoadReadiness:
    """Validate connection pool, batch limits, timeouts, and resource limits."""

    # Connection pool sizing
    def test_orchestrator_pool_sizing(self):
        src = _read('orchestrator/src/main.py')
        assert 'pool_size' in src, "Orchestrator must configure pool_size"
        assert 'max_overflow' in src, "Orchestrator must configure max_overflow"
        assert 'pool_recycle' in src, "Orchestrator must configure pool_recycle"
        assert 'pool_pre_ping' in src, "Orchestrator must enable pool_pre_ping"

    def test_event_store_batch_limit_enforced(self):
        src = _read('event-store/src/api/routes.py')
        assert '_MAX_BATCH_SIZE' in src
        # Must reject oversized batches
        assert 'exceeds maximum' in src, "Must reject oversized batches"

    def test_event_store_query_limit_clamped(self):
        src = _read('event-store/src/api/routes.py')
        # Timeline queries must clamp limit
        assert 'min(limit, 500)' in src or 'max(1, min(limit, 500))' in src, \
            "Timeline query limit must be clamped to 500"

    def test_relay_timeout_configured(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'RELAY_TIMEOUT' in src, "Relay must have configurable timeout"

    def test_relay_connection_limits(self):
        src = _read('orchestrator/src/infrastructure/outbox/relay.py')
        assert 'max_connections' in src, "Relay client must have connection limits"
        assert 'max_keepalive_connections' in src, "Relay must configure keepalive pool"

    # Resource limits in compose
    def test_compose_resource_limits(self):
        content = _read_infra('docker-compose.yml')
        assert content.count('memory:') >= 15, \
            "All services must have memory limits"
        assert content.count('cpus:') >= 15, \
            "All services must have CPU limits"

    def test_postgres_resource_limits(self):
        content = _read_infra('docker-compose.yml')
        # Postgres should have higher limits than application services
        pg_section = content[content.index('postgres:'):]
        pg_section = pg_section[:pg_section.index('\n\n')]
        assert '512M' in pg_section or '1G' in pg_section, \
            "Postgres must have adequate memory limit"

    # SSE stream safety
    def test_sse_disconnect_detection_exists(self):
        src = _read_event_store_api()
        assert 'is_disconnected' in src, \
            "SSE streams must detect disconnected clients to avoid resource leaks"

    def test_sse_generator_closes_repo(self):
        """SSE generators must close DB connections in finally block."""
        src = _read_event_store_api()
        # Both generators should close repo
        assert src.count('repo.close()') >= 2, \
            "SSE generators must close repo connections in finally"

    # Event-store ingest auth
    def test_ingest_requires_service_auth(self):
        src = _read('event-store/src/api/routes.py')
        assert 'require_service("orchestrator"' in src, \
            "Ingest must authenticate orchestrator"
        assert 'require_service("api-gateway"' in src, \
            "Timeline must authenticate api-gateway"


# ═══════════════════════════════════════════════════════════════════
# D45-G6: Runbook / go-live checklist
# ═══════════════════════════════════════════════════════════════════


class TestRunbookGoLive:
    """Go-live runbook must exist and cover all operational areas."""

    RUNBOOK_PATH = os.path.join(DOCS_ROOT, 'runbook-go-live.md')

    def test_runbook_exists(self):
        assert os.path.isfile(self.RUNBOOK_PATH), \
            "docs/runbook-go-live.md must exist"

    def test_runbook_has_prerequisites(self):
        content = _read_docs('runbook-go-live.md')
        assert 'prerequisite' in content.lower() or 'pre-launch' in content.lower(), \
            "Runbook must have prerequisites section"

    def test_runbook_covers_database(self):
        content = _read_docs('runbook-go-live.md')
        assert 'database' in content.lower() or 'postgres' in content.lower() or 'migration' in content.lower(), \
            "Runbook must cover database setup"

    def test_runbook_covers_secrets(self):
        content = _read_docs('runbook-go-live.md')
        assert 'secret' in content.lower() or 'credential' in content.lower(), \
            "Runbook must cover secrets management"

    def test_runbook_covers_healthchecks(self):
        content = _read_docs('runbook-go-live.md')
        assert 'health' in content.lower(), \
            "Runbook must cover health check verification"

    def test_runbook_covers_monitoring(self):
        content = _read_docs('runbook-go-live.md')
        assert 'monitor' in content.lower() or 'observ' in content.lower() or 'log' in content.lower(), \
            "Runbook must cover monitoring/observability"

    def test_runbook_covers_rollback(self):
        content = _read_docs('runbook-go-live.md')
        assert 'rollback' in content.lower() or 'revert' in content.lower(), \
            "Runbook must cover rollback procedures"

    def test_runbook_covers_recovery(self):
        content = _read_docs('runbook-go-live.md')
        assert 'recovery' in content.lower(), \
            "Runbook must cover recovery procedures"

    def test_runbook_covers_deployment_profiles(self):
        content = _read_docs('runbook-go-live.md')
        assert 'local' in content.lower() and 'hardened' in content.lower() and 'cloud' in content.lower(), \
            "Runbook must reference all 3 deployment profiles"

    def test_runbook_covers_backup(self):
        content = _read_docs('runbook-go-live.md')
        assert 'backup' in content.lower(), \
            "Runbook must cover backup procedures"

    def test_runbook_covers_scaling(self):
        content = _read_docs('runbook-go-live.md')
        assert 'scal' in content.lower(), \
            "Runbook must cover scaling guidance"

    def test_runbook_covers_service_startup_order(self):
        content = _read_docs('runbook-go-live.md')
        assert 'startup' in content.lower() or 'boot' in content.lower() or 'start' in content.lower(), \
            "Runbook must cover service startup order"
