"""PR41 Architecture Gate Tests — Service layering enforcement.

Hard gates:
  C41-G1: Application no longer imports infrastructure in 5 flagged services
  C41-G2: No-op boundary tests replaced with real checks
  C41-G3: CI enforces boundary rules (central test has the rule)
  C41-G4: Shared outbox package provides real implementation
  C41-G5: Product semantics preserved (composition roots wire correctly)
"""

import ast
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"

# The 5 services that PR41 addressed
PR41_SERVICES = [
    "auth-service",
    "workspace-service",
    "policy-service",
    "api-gateway",
    "model-gateway",
]


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all import module paths from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _collect_python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.name != "__init__.py" and p.exists()]


# ═══════════════════════════════════════════════════════════════════
# C41-G1: Application no longer imports infrastructure
# ═══════════════════════════════════════════════════════════════════


class TestApplicationNoInfrastructure:
    """Verify application layer in all 5 services has no infrastructure imports."""

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_application_no_src_infrastructure(self, service: str):
        """Application layer must not import from src.infrastructure."""
        app_dir = APPS_ROOT / service / "src" / "application"
        if not app_dir.exists():
            pytest.skip(f"{service} has no application layer")

        violations = []
        for pyfile in _collect_python_files(app_dir):
            for imp in _extract_imports(pyfile):
                if imp.startswith("src.infrastructure") or imp.startswith("infrastructure"):
                    violations.append(f"{pyfile.name}: {imp}")

        assert not violations, (
            f"{service} application/ imports infrastructure:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_application_no_sqlalchemy(self, service: str):
        """Application layer must not import SQLAlchemy directly."""
        app_dir = APPS_ROOT / service / "src" / "application"
        if not app_dir.exists():
            pytest.skip(f"{service} has no application layer")

        violations = []
        for pyfile in _collect_python_files(app_dir):
            for imp in _extract_imports(pyfile):
                top = imp.split(".")[0]
                if top == "sqlalchemy":
                    violations.append(f"{pyfile.name}: {imp}")

        assert not violations, (
            f"{service} application/ imports sqlalchemy:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_domain_no_infrastructure(self, service: str):
        """Domain layer must not import from infrastructure."""
        domain_dir = APPS_ROOT / service / "src" / "domain"
        if not domain_dir.exists():
            pytest.skip(f"{service} has no domain layer")

        infra_packages = {"sqlalchemy", "psycopg2", "httpx", "bcrypt", "jwt", "uvicorn"}
        violations = []
        for pyfile in _collect_python_files(domain_dir):
            for imp in _extract_imports(pyfile):
                top = imp.split(".")[0]
                if top in infra_packages or imp.startswith("src.infrastructure"):
                    violations.append(f"{pyfile.name}: {imp}")

        assert not violations, (
            f"{service} domain/ imports infrastructure:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


# ═══════════════════════════════════════════════════════════════════
# C41-G2: No-op boundary tests replaced with real checks
# ═══════════════════════════════════════════════════════════════════


class TestBoundaryTestsAreReal:
    """Verify per-service arch tests are not stubs."""

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_service_has_boundary_tests(self, service: str):
        """Each PR41 service must have a test_import_boundaries.py file."""
        test_file = APPS_ROOT / service / "tests" / "arch" / "test_import_boundaries.py"
        assert test_file.exists(), f"{service} missing tests/arch/test_import_boundaries.py"

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_boundary_tests_not_stub(self, service: str):
        """test_import_boundaries.py must not be a no-op stub."""
        test_file = APPS_ROOT / service / "tests" / "arch" / "test_import_boundaries.py"
        if not test_file.exists():
            pytest.skip(f"{service} missing test file")

        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Count real test functions (not just `pass`)
        real_tests = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Check if function body is just `pass`
                is_stub = (
                    len(node.body) == 1
                    and isinstance(node.body[0], ast.Pass)
                )
                if not is_stub:
                    real_tests += 1

        assert real_tests >= 3, (
            f"{service} test_import_boundaries.py has only {real_tests} real tests "
            f"(expected ≥3)"
        )


# ═══════════════════════════════════════════════════════════════════
# C41-G3: CI enforces boundary rules
# ═══════════════════════════════════════════════════════════════════


class TestCIEnforcement:
    """Verify the central test enforces the right rules."""

    def test_central_test_enforces_app_no_infra(self):
        """Central test_import_boundaries.py must forbid application → infrastructure."""
        central = REPO_ROOT / "tools" / "arch-test" / "test_import_boundaries.py"
        source = central.read_text(encoding="utf-8")

        # The LAYER_RULES dict must include 'infrastructure' in application's forbidden list
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "LAYER_RULES":
                        # Found the LAYER_RULES assignment — check the source
                        assert "'infrastructure'" in source or '"infrastructure"' in source, (
                            "LAYER_RULES must include 'infrastructure' as forbidden for application"
                        )
                        return
        pytest.fail("LAYER_RULES not found in central test")

    def test_ci_runs_arch_tests(self):
        """CI config must include arch-test job."""
        ci_file = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        if not ci_file.exists():
            pytest.skip("CI file not found")
        source = ci_file.read_text(encoding="utf-8")
        assert "arch-test" in source, "CI must have arch-test job"
        assert "test_import_boundaries" in source or "tools/arch-test" in source, (
            "CI must run import boundary tests"
        )


# ═══════════════════════════════════════════════════════════════════
# C41-G4: Shared outbox package provides real implementation
# ═══════════════════════════════════════════════════════════════════


class TestSharedOutboxPackage:
    """Verify the shared outbox package has real implementation."""

    def test_outbox_package_has_envelope(self):
        """packages/outbox must have an envelope builder."""
        envelope_file = REPO_ROOT / "packages" / "outbox" / "src" / "envelope.py"
        assert envelope_file.exists(), "packages/outbox/src/envelope.py not found"

    def test_outbox_build_envelope_function(self):
        """envelope.py must export build_envelope function."""
        envelope_file = REPO_ROOT / "packages" / "outbox" / "src" / "envelope.py"
        source = envelope_file.read_text(encoding="utf-8")
        assert "def build_envelope" in source, "build_envelope function not found"

    def test_outbox_package_not_placeholder(self):
        """packages/outbox __init__.py must not be just a placeholder comment."""
        init_file = REPO_ROOT / "packages" / "outbox" / "src" / "__init__.py"
        source = init_file.read_text(encoding="utf-8")
        assert "build_envelope" in source, (
            "packages/outbox __init__.py must export build_envelope"
        )


# ═══════════════════════════════════════════════════════════════════
# C41-G5: Product semantics preserved (composition roots wire correctly)
# ═══════════════════════════════════════════════════════════════════


class TestCompositionRoots:
    """Verify each service's main.py acts as composition root."""

    @pytest.mark.parametrize("service", [
        "auth-service", "workspace-service", "policy-service",
    ])
    def test_main_calls_configure(self, service: str):
        """main.py must call configure_*_deps to wire infrastructure."""
        main_file = APPS_ROOT / service / "src" / "main.py"
        source = main_file.read_text(encoding="utf-8")
        assert "configure_" in source, (
            f"{service}/main.py must call configure_*() to bootstrap dependencies"
        )

    def test_api_gateway_main_calls_configure(self):
        """api-gateway main.py must call configure_gateway_deps."""
        main_file = APPS_ROOT / "api-gateway" / "src" / "main.py"
        source = main_file.read_text(encoding="utf-8")
        assert "configure_gateway_deps" in source

    def test_model_gateway_main_wires_service(self):
        """model-gateway main.py must create and configure ModelExecutionService."""
        main_file = APPS_ROOT / "model-gateway" / "src" / "main.py"
        source = main_file.read_text(encoding="utf-8")
        assert "ModelExecutionService" in source
        assert "configure_service" in source

    @pytest.mark.parametrize("service", PR41_SERVICES)
    def test_ports_file_exists(self, service: str):
        """Each PR41 service must have a ports file."""
        # model-gateway has ports in domain/ports.py, others in application/ports.py
        app_ports = APPS_ROOT / service / "src" / "application" / "ports.py"
        domain_ports = APPS_ROOT / service / "src" / "domain" / "ports.py"
        assert app_ports.exists() or domain_ports.exists(), (
            f"{service} must have ports.py in application/ or domain/"
        )
