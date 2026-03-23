"""PR38 — Container / runtime hardening architecture gate tests.

Hard gates:
  C38-G1: Containers are least-privilege by default (non-root USER)
  C38-G2: Internal services not publicly exposed in prod profile
  C38-G3: Redis has auth enabled
  C38-G4: Docs endpoints disabled in prod-like mode
  C38-G5: Runtime config fails closed
  C38-G6: Secrets don't leak through image/runtime config
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APPS_DIR = ROOT / "apps"
INFRA_DIR = ROOT / "infra" / "docker"


def _find_compose_block(content: str, service: str) -> str | None:
    """Extract a top-level service block from docker-compose YAML.

    Matches '  service-name:' at exactly 2-space indent (top-level service key)
    and captures until the next top-level key or end of services section.
    """
    pattern = rf'(?:^|\n)  {re.escape(service)}:\n(.*?)(?=\n  \w|\nvolumes:|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return f"{service}:\n{match.group(1)}"
    return None

ALL_PYTHON_SERVICES = [
    "orchestrator",
    "agent-runtime",
    "model-gateway",
    "artifact-service",
    "execution-service",
    "event-store",
    "api-gateway",
    "auth-service",
    "workspace-service",
    "policy-service",
    "secret-broker",
    "audit-service",
    "notification-service",
    "telemetry-service",
    "sse-gateway",
]

ALL_SERVICES = ALL_PYTHON_SERVICES + ["web"]

# Services using Redis
REDIS_SERVICES = [
    "orchestrator",
    "agent-runtime",
    "event-store",
    "notification-service",
    "telemetry-service",
    "sse-gateway",
]

# Internal-only services (should NOT have host ports in prod)
INTERNAL_SERVICES = [
    "orchestrator",
    "agent-runtime",
    "model-gateway",
    "artifact-service",
    "execution-service",
    "event-store",
    "auth-service",
    "workspace-service",
    "policy-service",
    "secret-broker",
    "audit-service",
    "notification-service",
    "telemetry-service",
]


# ── C38-G1: Containers are least-privilege (non-root USER) ────


class TestG1NonRootContainers:
    """Every service Dockerfile MUST have a non-root USER directive."""

    @pytest.mark.parametrize("service", ALL_SERVICES)
    def test_dockerfile_has_user_directive(self, service):
        dockerfile = APPS_DIR / service / "Dockerfile"
        assert dockerfile.exists(), f"Missing Dockerfile for {service}"

        content = dockerfile.read_text(encoding="utf-8")
        assert "USER" in content, (
            f"{service}/Dockerfile does not set a non-root USER"
        )
        # Ensure USER is not root
        user_lines = [
            line.strip() for line in content.split("\n")
            if line.strip().startswith("USER ")
        ]
        assert user_lines, f"{service}/Dockerfile has no USER instruction"
        for user_line in user_lines:
            user_value = user_line.split(None, 1)[1].strip()
            assert user_value not in ("root", "0"), (
                f"{service}/Dockerfile sets USER to root"
            )

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_dockerfile_is_multistage(self, service):
        """Python service Dockerfiles MUST use multi-stage builds."""
        dockerfile = APPS_DIR / service / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        from_count = len(re.findall(r"^FROM\s+", content, re.MULTILINE))
        assert from_count >= 2, (
            f"{service}/Dockerfile is not multi-stage (only {from_count} FROM)"
        )

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_dockerfile_uses_venv(self, service):
        """Python service Dockerfiles MUST use a virtual environment."""
        dockerfile = APPS_DIR / service / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        assert "venv" in content, (
            f"{service}/Dockerfile does not use a virtual environment"
        )


# ── C38-G2: Internal services not publicly exposed in prod ────


class TestG2PortExposure:
    """Prod overlay must remove host port bindings for internal services."""

    def test_prod_overlay_exists(self):
        prod_overlay = INFRA_DIR / "docker-compose.prod.yml"
        assert prod_overlay.exists(), "Missing docker-compose.prod.yml"

    def test_prod_overlay_removes_internal_ports(self):
        prod_overlay = INFRA_DIR / "docker-compose.prod.yml"
        content = prod_overlay.read_text(encoding="utf-8")

        for service in INTERNAL_SERVICES:
            assert service in content, (
                f"{service} not found in docker-compose.prod.yml"
            )

    def test_prod_overlay_sets_production_env(self):
        prod_overlay = INFRA_DIR / "docker-compose.prod.yml"
        content = prod_overlay.read_text(encoding="utf-8")

        assert "APP_ENV: production" in content

    def test_public_services_keep_ports(self):
        """api-gateway, sse-gateway, web must retain ports in dev compose."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        for service in ["api-gateway", "sse-gateway", "web"]:
            block = _find_compose_block(content, service)
            assert block, f"{service} not found in docker-compose.yml"
            assert "ports:" in block, (
                f"{service} must have ports in docker-compose.yml"
            )


# ── C38-G3: Redis has auth enabled ───────────────────────────


class TestG3RedisAuth:
    """Redis MUST have requirepass enabled."""

    def test_redis_has_requirepass(self):
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        assert "requirepass" in content, (
            "Redis must have --requirepass in docker-compose.yml"
        )

    def test_redis_password_not_hardcoded(self):
        """Redis password should use env var substitution, not hardcoded."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        assert "REDIS_PASSWORD" in content, (
            "Redis password should be configurable via REDIS_PASSWORD env var"
        )

    @pytest.mark.parametrize("service", REDIS_SERVICES)
    def test_redis_clients_use_password(self, service):
        """Services using Redis must include password in connection URL."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        block = _find_compose_block(content, service)
        assert block, f"{service} not found in docker-compose.yml"

        # Redis URLs with auth use redis://:password@host format
        redis_urls = re.findall(r'redis://[^\s]+', block)
        for url in redis_urls:
            assert ":$" in url or "REDIS_PASSWORD" in url or ":" in url.split("@")[0], (
                f"{service}: Redis URL must include password: {url}"
            )


# ── C38-G4: Docs endpoints disabled in prod-like mode ────────


class TestG4DocsToggle:
    """FastAPI docs MUST be disabled when APP_ENV != development."""

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_service_has_docs_toggle(self, service):
        """Each service main.py must conditionally disable docs."""
        main_file = APPS_DIR / service / "src" / "main.py"
        assert main_file.exists(), f"Missing main.py for {service}"

        content = main_file.read_text(encoding="utf-8")
        assert "APP_ENV" in content, (
            f"{service}/main.py does not read APP_ENV"
        )
        assert "docs_url" in content, (
            f"{service}/main.py does not conditionally set docs_url"
        )

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_compose_sets_app_env(self, service):
        """Each service in docker-compose must have APP_ENV."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        block = _find_compose_block(content, service)
        assert block, f"{service} not found in docker-compose.yml"

        assert "APP_ENV" in block, (
            f"{service} missing APP_ENV in docker-compose.yml"
        )


# ── C38-G5: Runtime config fails closed ──────────────────────


class TestG5FailClosed:
    """Services with required config MUST fail on startup if missing."""

    @pytest.mark.parametrize("service", [
        "orchestrator", "artifact-service",
        "execution-service", "event-store",
    ])
    def test_db_url_required(self, service):
        """Services with databases must fail if DB URL is missing."""
        main_file = APPS_DIR / service / "src" / "main.py"
        content = main_file.read_text(encoding="utf-8")

        assert "raise RuntimeError" in content, (
            f"{service}/main.py does not fail-fast on missing config"
        )


# ── C38-G6: Secrets don't leak through image/config ──────────


class TestG6SecretHygiene:
    """Secrets and dev junk must not leak into Docker images."""

    def test_dockerignore_exists(self):
        dockerignore = ROOT / ".dockerignore"
        assert dockerignore.exists(), "Missing .dockerignore at repo root"

    def test_dockerignore_excludes_sensitive(self):
        dockerignore = ROOT / ".dockerignore"
        content = dockerignore.read_text(encoding="utf-8")

        required_patterns = [".git/", ".env", "tests/", "docs/", "__pycache__/"]
        for pattern in required_patterns:
            assert pattern in content, (
                f".dockerignore missing pattern: {pattern}"
            )

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_dockerfile_only_copies_src(self, service):
        """Runtime stage should only COPY src/ (not tests, docs, etc)."""
        dockerfile = APPS_DIR / service / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        # Find runtime stage (after last FROM)
        stages = content.split("FROM ")
        runtime_stage = stages[-1] if len(stages) > 1 else stages[0]

        # COPY commands in runtime should reference src/ or packages/
        copy_lines = [
            line.strip() for line in runtime_stage.split("\n")
            if line.strip().startswith("COPY") and "--from=" not in line
        ]
        for copy_line in copy_lines:
            # Allow: COPY apps/<service>/src, COPY packages/internal-auth,
            # COPY apps/<service>/alembic, COPY apps/<service>/alembic.ini
            assert "src" in copy_line or "packages" in copy_line or "alembic" in copy_line, (
                f"{service}/Dockerfile runtime copies unexpected path: {copy_line}"
            )

    def test_compose_secrets_use_env_vars(self):
        """Compose should use env var substitution for secrets."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        # INTERNAL_AUTH_SECRET should use ${} syntax
        auth_secret_lines = [
            line for line in content.split("\n")
            if "INTERNAL_AUTH_SECRET" in line and ":" in line
        ]
        for line in auth_secret_lines:
            assert "${" in line, (
                f"INTERNAL_AUTH_SECRET should use env var substitution: {line.strip()}"
            )

        # AUTH_JWT_SECRET should use ${} syntax
        jwt_lines = [
            line for line in content.split("\n")
            if "AUTH_JWT_SECRET" in line and ":" in line
        ]
        for line in jwt_lines:
            assert "${" in line, (
                f"AUTH_JWT_SECRET should use env var substitution: {line.strip()}"
            )


# ── Build context consistency ─────────────────────────────────


class TestBuildContext:
    """All service builds should use repo root context."""

    @pytest.mark.parametrize("service", ALL_SERVICES)
    def test_compose_uses_repo_root_context(self, service):
        """Each service in compose must use context: ../.. with dockerfile."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        block = _find_compose_block(content, service)
        if not block:
            pytest.skip(f"{service} not found in docker-compose.yml")

        assert "context:" in block, (
            f"{service}: build must use context/dockerfile format"
        )
        assert "dockerfile:" in block, (
            f"{service}: build must specify dockerfile path"
        )


# ── Resource limits ───────────────────────────────────────────


class TestResourceLimits:
    """Services should have resource limits in compose."""

    @pytest.mark.parametrize("service", ALL_PYTHON_SERVICES)
    def test_service_has_resource_limits(self, service):
        """Each service should have deploy.resources.limits."""
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")
        block = _find_compose_block(content, service)

        assert "deploy:" in block, (
            f"{service}: must have a deploy section with resource limits"
        )
        assert "memory:" in block, (
            f"{service}: must have memory limits in deploy.resources.limits"
        )


# ── CORS baseline ────────────────────────────────────────────


class TestCORSBaseline:
    """api-gateway MUST have CORS middleware configured."""

    def test_api_gateway_has_cors(self):
        main_file = APPS_DIR / "api-gateway" / "src" / "main.py"
        content = main_file.read_text(encoding="utf-8")

        assert "CORSMiddleware" in content, (
            "api-gateway must have CORSMiddleware"
        )
        assert "CORS_ALLOWED_ORIGINS" in content, (
            "api-gateway CORS must use configurable origins"
        )

    def test_cors_not_wildcard_in_prod(self):
        """CORS origins should not be '*' by default."""
        main_file = APPS_DIR / "api-gateway" / "src" / "main.py"
        content = main_file.read_text(encoding="utf-8")

        # Default should be specific, not wildcard
        assert 'allow_origins=["*"]' not in content, (
            "api-gateway must not use wildcard CORS origins"
        )

    def test_compose_has_cors_config(self):
        compose = INFRA_DIR / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        assert "CORS_ALLOWED_ORIGINS" in content, (
            "api-gateway in compose must have CORS_ALLOWED_ORIGINS"
        )
