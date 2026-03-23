"""PR43 gate tests — Hybrid / cloud deployment readiness.

D43-G1: Three deployment profile overlays exist (local, hardened, cloud)
D43-G2: No hardcoded dev secrets in hardened/cloud overlays
D43-G3: Execution backend is env-configurable; noop backend exists
D43-G4: Storage backend env var recognized in cloud overlay
D43-G5: All 15 services expose /healthz/info with deployment metadata
D43-G6: .env.cloud.example exists with all required config vars documented
"""

import os
import re

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
APPS_ROOT = os.path.join(REPO_ROOT, 'apps')
INFRA_DOCKER = os.path.join(REPO_ROOT, 'infra', 'docker')


def _read(relpath: str, root: str = APPS_ROOT) -> str:
    with open(os.path.join(root, relpath), encoding='utf-8') as f:
        return f.read()


def _read_infra(relpath: str) -> str:
    return _read(relpath, root=INFRA_DOCKER)


# ── D43-G1: Deployment profile overlays exist ───────────────────────

class TestDeploymentProfiles:
    """Three compose overlays must exist alongside base."""

    OVERLAYS = [
        'docker-compose.local.yml',
        'docker-compose.hardened.yml',
        'docker-compose.cloud.yml',
    ]

    @pytest.mark.parametrize('overlay', OVERLAYS)
    def test_overlay_file_exists(self, overlay):
        path = os.path.join(INFRA_DOCKER, overlay)
        assert os.path.isfile(path), f"Missing overlay: {overlay}"

    def test_base_compose_exists(self):
        path = os.path.join(INFRA_DOCKER, 'docker-compose.yml')
        assert os.path.isfile(path), "Base docker-compose.yml missing"

    @pytest.mark.parametrize('overlay,profile', [
        ('docker-compose.local.yml', 'local'),
        ('docker-compose.hardened.yml', 'hardened'),
        ('docker-compose.cloud.yml', 'cloud'),
    ])
    def test_overlay_sets_deployment_profile(self, overlay, profile):
        content = _read_infra(overlay)
        assert f'DEPLOYMENT_PROFILE: {profile}' in content or \
               f'DEPLOYMENT_PROFILE: ${{{profile}' in content, \
            f"{overlay} must set DEPLOYMENT_PROFILE to {profile}"


# ── D43-G2: No hardcoded dev secrets in hardened/cloud ───────────────

class TestNoDevSecrets:
    """Hardened and cloud overlays must not contain dev default secrets."""

    DEV_SECRETS = [
        'dev-secret-change-in-production',
        'dev-internal-auth-secret-change-in-production',
        'dev-redis-password',
        'superpassword',
    ]

    @pytest.mark.parametrize('overlay', [
        'docker-compose.hardened.yml',
        'docker-compose.cloud.yml',
    ])
    def test_no_hardcoded_dev_secrets(self, overlay):
        content = _read_infra(overlay)
        for secret in self.DEV_SECRETS:
            assert secret not in content, \
                f"Dev secret '{secret}' found in {overlay}"


# ── D43-G3: Execution backend env-configurable ──────────────────────

class TestExecutionBackendConfig:
    """Execution backend must be selectable via EXECUTION_BACKEND env var."""

    MAIN = 'execution-service/src/main.py'
    NOOP = 'execution-service/src/infrastructure/sandbox/noop_backend.py'

    def test_main_reads_execution_backend_env(self):
        src = _read(self.MAIN)
        assert 'EXECUTION_BACKEND' in src, \
            "execution-service main.py must read EXECUTION_BACKEND env var"

    def test_noop_backend_exists(self):
        path = os.path.join(APPS_ROOT, self.NOOP)
        assert os.path.isfile(path), "NoopSandboxBackend file must exist"

    def test_noop_backend_implements_ports(self):
        src = _read(self.NOOP)
        assert 'class NoopSandboxBackend' in src
        assert 'class NoopExecutionBackend' in src
        assert 'SandboxBackend' in src
        assert 'ToolExecutionBackend' in src

    def test_main_branches_on_backend_type(self):
        src = _read(self.MAIN)
        assert 'docker-local' in src, "Must handle docker-local backend"
        assert 'NoopSandboxBackend' in src or 'noop_backend' in src, \
            "Must import noop backend for non-docker profiles"

    def test_hardened_overlay_sets_noop(self):
        content = _read_infra('docker-compose.hardened.yml')
        assert 'EXECUTION_BACKEND: noop' in content, \
            "Hardened overlay must set EXECUTION_BACKEND to noop"

    def test_cloud_overlay_externalizes_backend(self):
        content = _read_infra('docker-compose.cloud.yml')
        assert 'EXECUTION_BACKEND' in content, \
            "Cloud overlay must include EXECUTION_BACKEND config"


# ── D43-G4: Storage backend env var in cloud overlay ─────────────────

class TestStorageBackendConfig:
    """Cloud overlay must support configurable storage backend."""

    def test_cloud_overlay_has_storage_backend(self):
        content = _read_infra('docker-compose.cloud.yml')
        assert 'ARTIFACT_STORAGE_BACKEND' in content, \
            "Cloud overlay must include ARTIFACT_STORAGE_BACKEND"

    def test_cloud_overlay_has_s3_config(self):
        content = _read_infra('docker-compose.cloud.yml')
        assert 'ARTIFACT_S3_BUCKET' in content, \
            "Cloud overlay must include S3 bucket config"

    def test_artifact_service_healthz_exposes_storage_backend(self):
        src = _read('artifact-service/src/api/routes.py')
        assert 'storage_backend' in src, \
            "artifact-service /healthz/info must expose storage_backend"


# ── D43-G5: All services expose /healthz/info ───────────────────────

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


class TestHealthzInfo:
    """All 15 services must have /healthz/info returning deployment metadata."""

    @pytest.mark.parametrize('service', ALL_SERVICES)
    def test_healthz_info_endpoint_exists(self, service):
        routes_path = f'{service}/src/api/routes.py'
        src = _read(routes_path)
        assert '/healthz/info' in src, \
            f"{service} must have /healthz/info endpoint"

    @pytest.mark.parametrize('service', ALL_SERVICES)
    def test_healthz_info_returns_service_name(self, service):
        routes_path = f'{service}/src/api/routes.py'
        src = _read(routes_path)
        assert 'deployment_profile' in src, \
            f"{service} /healthz/info must return deployment_profile"

    @pytest.mark.parametrize('service', ALL_SERVICES)
    def test_healthz_info_returns_app_env(self, service):
        routes_path = f'{service}/src/api/routes.py'
        src = _read(routes_path)
        assert 'app_env' in src, \
            f"{service} /healthz/info must return app_env"


# ── D43-G6: .env.cloud.example with required vars ───────────────────

class TestEnvCloudExample:
    """.env.cloud.example must document all required configuration."""

    ENV_EXAMPLE = '.env.cloud.example'

    REQUIRED_VARS = [
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'REDIS_PASSWORD',
        'AUTH_DB_URL',
        'ORCHESTRATOR_DB_URL',
        'EVENT_STORE_DB_URL',
        'EXECUTION_DB_URL',
        'ARTIFACT_DB_URL',
        'WORKSPACE_DB_URL',
        'AUTH_JWT_SECRET',
        'INTERNAL_AUTH_SECRET',
        'EVENT_BUS_URL',
        'EXECUTION_BACKEND',
        'ARTIFACT_STORAGE_BACKEND',
        'CORS_ALLOWED_ORIGINS',
    ]

    def test_env_example_exists(self):
        path = os.path.join(INFRA_DOCKER, self.ENV_EXAMPLE)
        assert os.path.isfile(path), ".env.cloud.example must exist"

    @pytest.mark.parametrize('var', REQUIRED_VARS)
    def test_required_var_documented(self, var):
        content = _read_infra(self.ENV_EXAMPLE)
        assert var in content, \
            f".env.cloud.example must document {var}"


# ── D43-G1 extra: Config package exists ──────────────────────────────

class TestConfigPackage:
    """Shared config validation package must exist."""

    def test_config_package_exists(self):
        path = os.path.join(REPO_ROOT, 'packages', 'config', 'src', '__init__.py')
        assert os.path.isfile(path), "packages/config/src/__init__.py must exist"

    def test_config_package_has_require_env(self):
        path = os.path.join(REPO_ROOT, 'packages', 'config', 'src', '__init__.py')
        with open(path, encoding='utf-8') as f:
            src = f.read()
        assert 'def require_env' in src
        assert 'def optional_env' in src

    def test_config_package_has_deployment_info(self):
        path = os.path.join(REPO_ROOT, 'packages', 'config', 'src', '__init__.py')
        with open(path, encoding='utf-8') as f:
            src = f.read()
        assert 'class DeploymentInfo' in src
        assert 'def get_deployment_info' in src
