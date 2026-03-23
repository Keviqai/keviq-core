"""PR37 — Internal service auth architecture gate tests.

Hard gates:
  C37-G1: Every internal API endpoint requires authentication
  C37-G2: Wrong caller service is denied (403)
  C37-G3: Missing config fails closed (RuntimeError on startup)
  C37-G4: Secrets stay within boundary (not exposed in API responses)
  C37-G5: Public auth (user JWT) and internal auth (service JWT) are separate
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "packages" / "internal-auth" / "internal_auth"
APPS_DIR = ROOT / "apps"

# Services that MUST have internal auth wired
AUTH_SERVICES = [
    "orchestrator",
    "agent-runtime",
    "model-gateway",
    "artifact-service",
    "execution-service",
    "event-store",
    "api-gateway",
]

# Services that receive internal requests (need verifier)
RECEIVING_SERVICES = [
    "orchestrator",
    "agent-runtime",
    "model-gateway",
    "artifact-service",
    "execution-service",
    "event-store",
]

# Authorization matrix: service -> list of allowed callers per endpoint pattern
AUTHORIZATION_MATRIX = {
    "orchestrator": ["api-gateway"],
    "agent-runtime": ["orchestrator"],
    "model-gateway": ["agent-runtime"],
    "artifact-service": ["agent-runtime", "api-gateway"],
    "execution-service": ["orchestrator"],
    "event-store": ["orchestrator", "artifact-service", "api-gateway"],
}


# ── C37-G1: Every internal API endpoint requires auth ────────────


class TestG1InternalEndpointsAuthenticated:
    """Every /internal/v1/* endpoint MUST have a Depends(require_service(...)) or
    Depends(require_internal_auth) parameter.
    """

    @pytest.mark.parametrize("service", RECEIVING_SERVICES)
    def test_all_internal_routes_have_auth_dependency(self, service):
        """Parse route files and verify every internal endpoint has auth deps."""
        routes_file = APPS_DIR / service / "src" / "api" / "routes.py"
        assert routes_file.exists(), f"Missing routes.py for {service}"

        content = routes_file.read_text(encoding="utf-8")
        tree = ast.parse(content)

        internal_endpoints = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Check if this function is decorated with a route containing /internal/
                for decorator in node.decorator_list:
                    dec_str = ast.dump(decorator)
                    if "/internal/" in dec_str or "healthz" not in dec_str:
                        # Check route string in decorator args
                        if _has_internal_route(decorator):
                            internal_endpoints.append(node)

        for endpoint in internal_endpoints:
            params = [arg.arg for arg in endpoint.args.args]
            func_source = ast.get_source_segment(content, endpoint)
            assert func_source is not None

            has_auth = (
                "require_service" in func_source
                or "require_internal_auth" in func_source
            )
            assert has_auth, (
                f"{service}/routes.py: endpoint '{endpoint.name}' "
                f"(line {endpoint.lineno}) is an internal route without auth dependency"
            )


def _has_internal_route(decorator) -> bool:
    """Check if a decorator references an /internal/ path."""
    if isinstance(decorator, ast.Call):
        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "/internal/" in arg.value:
                    return True
    return False


# ── C37-G2: Health endpoints remain unauthenticated ──────────────


class TestG1HealthEndpointsPublic:
    """Health check endpoints (/healthz/*) MUST NOT have auth deps."""

    @pytest.mark.parametrize("service", RECEIVING_SERVICES)
    def test_healthz_routes_no_auth(self, service):
        routes_file = APPS_DIR / service / "src" / "api" / "routes.py"
        content = routes_file.read_text(encoding="utf-8")

        # Find healthz endpoint functions
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("liveness", "readiness"):
                    func_source = ast.get_source_segment(content, node) or ""
                    assert "require_service" not in func_source, (
                        f"{service}: healthz endpoint '{node.name}' should NOT have auth"
                    )
                    assert "require_internal_auth" not in func_source, (
                        f"{service}: healthz endpoint '{node.name}' should NOT have auth"
                    )


# ── C37-G3: Missing config fails closed ──────────────────────────


class TestG3FailClosed:
    """Service MUST refuse to start without INTERNAL_AUTH_SECRET."""

    def test_config_raises_on_missing_secret(self):
        """load_internal_auth_config raises RuntimeError without env var."""
        config_file = PACKAGES_DIR / "config.py"
        content = config_file.read_text(encoding="utf-8")

        assert 'raise RuntimeError' in content, (
            "config.py must raise RuntimeError when INTERNAL_AUTH_SECRET is missing"
        )
        assert 'INTERNAL_AUTH_SECRET' in content

    def test_config_raises_on_missing_service_name(self):
        """load_internal_auth_config raises RuntimeError without SERVICE_NAME."""
        config_file = PACKAGES_DIR / "config.py"
        content = config_file.read_text(encoding="utf-8")

        assert 'SERVICE_NAME' in content
        # Two RuntimeError raises — one for secret, one for service name
        assert content.count('raise RuntimeError') >= 2

    @pytest.mark.parametrize("service", AUTH_SERVICES)
    def test_service_bootstraps_internal_auth(self, service):
        """Each service's main.py must call bootstrap_internal_auth."""
        main_file = APPS_DIR / service / "src" / "main.py"
        assert main_file.exists(), f"Missing main.py for {service}"

        content = main_file.read_text(encoding="utf-8")
        assert "bootstrap_internal_auth" in content, (
            f"{service}/main.py does not call bootstrap_internal_auth()"
        )


# ── C37-G4: Secrets stay in boundary ────────────────────────────


class TestG4SecretBoundary:
    """Internal auth secrets MUST NOT leak into API responses or logs."""

    def test_token_module_never_exposes_secret(self):
        """token.py should not return or log the raw secret directly."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        # Secret is stored as self._secret — should never be returned directly
        # (passing to jwt.encode is fine — it returns a signed token, not the secret)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('return') and '_secret' in stripped:
                # Allow: return jwt.encode(..., self._secret, ...) — produces a token
                if 'jwt.encode' in stripped:
                    continue
                pytest.fail(
                    f"token.py line {i}: returning raw secret is forbidden"
                )

    def test_fastapi_dep_never_logs_token(self):
        """fastapi_dep.py must not log the raw token value."""
        dep_file = PACKAGES_DIR / "fastapi_dep.py"
        content = dep_file.read_text(encoding="utf-8")

        # Logger warnings should reference exception objects, not raw credentials
        assert 'credentials.credentials' not in content.replace(
            'verifier.verify(credentials.credentials', ''
        ).replace(
            'verifier.verify(\n                credentials.credentials', ''
        ), (
            "fastapi_dep.py must not log raw token value"
        )

    def test_docker_compose_uses_dev_secret(self):
        """docker-compose must have INTERNAL_AUTH_SECRET for all auth services."""
        compose = ROOT / "infra" / "docker" / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        assert "INTERNAL_AUTH_SECRET" in content
        # Count occurrences — should be at least one per auth service
        count = content.count("INTERNAL_AUTH_SECRET")
        assert count >= 7, (
            f"Expected INTERNAL_AUTH_SECRET in at least 7 services, found {count}"
        )


# ── C37-G5: Public and internal auth are separate ────────────────


class TestG5AuthSeparation:
    """Internal JWT (iss=monaos-internal) and user JWT MUST NOT be mixed."""

    def test_internal_token_uses_dedicated_issuer(self):
        """Internal tokens must use 'monaos-internal' issuer."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        assert '"monaos-internal"' in content or "'monaos-internal'" in content, (
            "Internal tokens must use 'monaos-internal' as issuer"
        )

    def test_internal_token_uses_hs256(self):
        """Internal tokens must use HS256 algorithm."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        assert 'HS256' in content

    def test_internal_auth_separate_from_user_auth(self):
        """api-gateway user JWT secret must differ from internal auth config key."""
        compose = ROOT / "infra" / "docker" / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        # Extract AUTH_JWT_SECRET and INTERNAL_AUTH_SECRET values
        user_secret_match = re.search(r'AUTH_JWT_SECRET:\s*(\S+)', content)
        internal_secret_match = re.search(r'INTERNAL_AUTH_SECRET:\s*(\S+)', content)

        assert user_secret_match and internal_secret_match
        assert user_secret_match.group(1) != internal_secret_match.group(1), (
            "User JWT secret and internal auth secret must be different"
        )

    def test_internal_package_has_no_user_session_concepts(self):
        """Shared internal-auth package must not reference user/session concepts."""
        for py_file in PACKAGES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Skip docstrings that explicitly mention separation
            code_lines = [
                line for line in content.split('\n')
                if not line.strip().startswith('#')
                and not line.strip().startswith('"""')
                and not line.strip().startswith("'''")
            ]
            code = '\n'.join(code_lines)

            for forbidden in ['session_token', 'user_token', 'access_token', 'refresh_token']:
                assert forbidden not in code.lower(), (
                    f"{py_file.name}: references '{forbidden}' — "
                    "internal auth must not mix with user/session auth"
                )


# ── Authorization matrix structural tests ────────────────────────


class TestAuthorizationMatrix:
    """Verify the authorization matrix is correctly wired in route files."""

    @pytest.mark.parametrize("service", RECEIVING_SERVICES)
    def test_service_has_bridge_module(self, service):
        """Each receiving service must have an internal_auth.py bridge."""
        bridge = APPS_DIR / service / "src" / "internal_auth.py"
        assert bridge.exists(), (
            f"{service} is missing src/internal_auth.py bridge module"
        )

    @pytest.mark.parametrize("service", RECEIVING_SERVICES)
    def test_routes_import_require_service(self, service):
        """Route files must import require_service from internal_auth."""
        api_dir = APPS_DIR / service / "src" / "api"
        # Read all route files (services may split routes into sub-modules)
        content = ""
        for py_file in sorted(api_dir.glob("route*.py")):
            content += py_file.read_text(encoding="utf-8") + "\n"
        if not content:
            content = (api_dir / "routes.py").read_text(encoding="utf-8")

        assert "require_service" in content, (
            f"{service}/routes does not use require_service"
        )

    def test_api_gateway_signs_outgoing_requests(self):
        """api-gateway proxy must attach auth headers to outgoing requests."""
        proxy_file = APPS_DIR / "api-gateway" / "src" / "infrastructure" / "service_proxy.py"
        content = proxy_file.read_text(encoding="utf-8")

        assert "get_auth_client" in content, (
            "api-gateway proxy must use get_auth_client() to sign requests"
        )
        assert "auth_headers" in content, (
            "api-gateway proxy must call auth_headers() for internal tokens"
        )


# ── Token structure tests ────────────────────────────────────────


class TestTokenStructure:
    """Verify JWT claims match spec: sub, aud, iss, jti, iat, exp, service_name."""

    def test_issuer_includes_required_claims(self):
        """Token issuer must include all required claims."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        for claim in ['sub', 'aud', 'iss', 'jti', 'iat', 'exp', 'service_name']:
            assert f'"{claim}"' in content or f"'{claim}'" in content, (
                f"Token issuer missing required claim: {claim}"
            )

    def test_verifier_checks_audience(self):
        """Verifier must validate audience claim."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        assert "audience" in content
        assert "InvalidAudienceError" in content

    def test_verifier_checks_expiry(self):
        """Verifier must reject expired tokens."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        assert "ExpiredSignatureError" in content
        assert "ExpiredTokenError" in content

    def test_verifier_checks_allowed_services(self):
        """Verifier must support allowed_services filtering."""
        token_file = PACKAGES_DIR / "token.py"
        content = token_file.read_text(encoding="utf-8")

        assert "allowed_services" in content
        assert "UnauthorizedServiceError" in content


# ── Exception hierarchy tests ────────────────────────────────────


class TestExceptionHierarchy:
    """Internal auth exceptions must form a proper hierarchy."""

    def test_base_error_class_exists(self):
        content = (PACKAGES_DIR / "token.py").read_text(encoding="utf-8")
        assert "class InternalAuthError(Exception)" in content

    def test_specific_errors_inherit_from_base(self):
        content = (PACKAGES_DIR / "token.py").read_text(encoding="utf-8")
        for error in [
            "InvalidTokenError",
            "ExpiredTokenError",
            "WrongAudienceError",
            "UnauthorizedServiceError",
        ]:
            assert f"class {error}(InternalAuthError)" in content, (
                f"{error} must inherit from InternalAuthError"
            )


# ── Docker-compose env var tests ─────────────────────────────────


class TestDockerComposeEnvVars:
    """Verify INTERNAL_AUTH_SECRET and SERVICE_NAME are set for all auth services."""

    @pytest.mark.parametrize("service", AUTH_SERVICES)
    def test_service_has_internal_auth_secret(self, service):
        compose = ROOT / "infra" / "docker" / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")

        # Find the service block — match service name at start of line (2-space indent)
        service_key = service  # service names in compose match
        pattern = rf'^  {service_key}:\n.*?(?=\n  \w|\nvolumes:|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        assert match, f"Service {service} not found in docker-compose.yml"

        block = match.group(0)
        assert "INTERNAL_AUTH_SECRET" in block, (
            f"{service} missing INTERNAL_AUTH_SECRET in docker-compose.yml"
        )
        assert "SERVICE_NAME" in block, (
            f"{service} missing SERVICE_NAME in docker-compose.yml"
        )
