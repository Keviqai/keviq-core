"""Architecture tests for Slice 4 — Sandbox Manager + Tool Execution.

S4-G2: Sandbox manager does not own orchestrator lifecycle.
S4-G3: Sandbox input not user-controlled arbitrarily.
S4-G4: Sandbox contracts are transport-agnostic.
S4-G5: No cross-schema FK from execution-service to other services.
G21-1: Execution only through registered tools (no raw command in API).
G21-2: Docker exec uses argv list, not shell string.
G21-3: No orchestrator lifecycle ownership (same as S4-G2).
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))


def _collect_python_files(directory: str) -> list[str]:
    """Walk directory and return all .py files."""
    if not os.path.isdir(directory):
        return []
    result = []
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith('.py'):
                result.append(os.path.join(dirpath, f))
    return result


def _extract_imports(filepath: str) -> list[str]:
    """Extract top-level module names from imports."""
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split('.')[0])
    return imports


def _extract_full_imports(filepath: str) -> list[str]:
    """Extract full dotted import paths."""
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
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


# ── S4-G2: Sandbox manager does not own orchestrator lifecycle ──


class TestSandboxManagerDoesNotOwnOrchestratorLifecycle:
    """execution-service must NOT import or mutate orchestrator domain."""

    ORCHESTRATOR_DOMAIN_MODULES = {
        'src.domain.task', 'src.domain.run', 'src.domain.step',
    }

    # Status fields that belong to orchestrator only
    ORCHESTRATOR_STATUS_PATTERNS = [
        re.compile(r'task_status\s*='),
        re.compile(r'run_status\s*='),
        re.compile(r'step_status\s*='),
        re.compile(r'agent_invocation_status\s*='),
    ]

    def test_execution_service_does_not_import_orchestrator(self):
        """execution-service source must not import from orchestrator."""
        exec_src = os.path.join(APPS_ROOT, 'execution-service', 'src')
        orch_patterns = {'orchestrator', 'src.domain.task', 'src.domain.run', 'src.domain.step'}

        violations = []
        for f in _collect_python_files(exec_src):
            imports = _extract_full_imports(f)
            for imp in imports:
                for pattern in orch_patterns:
                    # Only flag orchestrator-specific imports, not generic ones
                    if 'orchestrator' in imp:
                        rel = os.path.relpath(f, APPS_ROOT)
                        violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"execution-service must not import orchestrator:\n"
            + "\n".join(violations)
        )

    def test_execution_service_does_not_mutate_orchestrator_status(self):
        """No code in execution-service should assign task/run/step/invocation status."""
        exec_src = os.path.join(APPS_ROOT, 'execution-service', 'src')

        violations = []
        for f in _collect_python_files(exec_src):
            with open(f, encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            for pattern in self.ORCHESTRATOR_STATUS_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: mutates orchestrator status ({matches[0].strip()})")

        assert violations == [], (
            f"execution-service must not mutate orchestrator lifecycle:\n"
            + "\n".join(violations)
        )


# ── S4-G3: Sandbox input not user-controlled ────────────────


class TestSandboxInputNotUserControlled:
    """Sandbox profiles must come from internal code, not user request."""

    def test_no_arbitrary_image_from_request(self):
        """No route or handler should pass user-supplied 'image' to Docker."""
        exec_src = os.path.join(APPS_ROOT, 'execution-service', 'src')
        api_dir = os.path.join(exec_src, 'api')
        app_dir = os.path.join(exec_src, 'application')

        violations = []
        for d in [api_dir, app_dir]:
            for f in _collect_python_files(d):
                with open(f, encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                # Check for body["image"] or body.get("image") patterns
                if re.search(r'body\[?.*["\']image["\']\]?', content):
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: passes user-supplied image")
                if re.search(r'body\.get\(["\']image["\']\)', content):
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: passes user-supplied image")

        assert violations == [], (
            f"No arbitrary image from request:\n" + "\n".join(violations)
        )

    def test_no_arbitrary_host_path_from_request(self):
        """No route or handler should pass user-supplied host paths."""
        exec_src = os.path.join(APPS_ROOT, 'execution-service', 'src')
        api_dir = os.path.join(exec_src, 'api')
        app_dir = os.path.join(exec_src, 'application')

        violations = []
        for d in [api_dir, app_dir]:
            for f in _collect_python_files(d):
                with open(f, encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                for pattern in [r'body\[?.*["\']host_path["\']\]?',
                                r'body\.get\(["\']mount["\']\)',
                                r'body\.get\(["\']volume["\']\)']:
                    if re.search(pattern, content):
                        rel = os.path.relpath(f, APPS_ROOT)
                        violations.append(f"{rel}: passes user-supplied host path")

        assert violations == [], (
            f"No arbitrary host path from request:\n" + "\n".join(violations)
        )


# ── S4-G4: Sandbox contracts are transport-agnostic ──────────


class TestSandboxContractsTransportAgnostic:
    """Domain contracts must not import framework libraries."""

    FRAMEWORK_MODULES = {'fastapi', 'sqlalchemy', 'docker', 'httpx', 'pydantic'}

    def test_contracts_no_framework_imports(self):
        contracts_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'domain', 'contracts.py',
        )
        if not os.path.exists(contracts_file):
            pytest.skip("contracts.py not found")

        imports = _extract_imports(contracts_file)
        violations = [i for i in imports if i in self.FRAMEWORK_MODULES]

        assert violations == [], (
            f"contracts.py imports framework modules: {violations}"
        )

    def test_domain_layer_no_framework_imports(self):
        """All files in domain/ must be framework-free."""
        domain_dir = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'domain',
        )
        violations = []
        for f in _collect_python_files(domain_dir):
            imports = _extract_imports(f)
            for imp in imports:
                if imp in self.FRAMEWORK_MODULES:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Domain layer imports framework modules:\n" + "\n".join(violations)
        )


# ── S4-G5: No cross-schema FK ───────────────────────────────


class TestNoCrossSchemaFK:
    """execution-service migrations must not reference other schemas."""

    OTHER_SCHEMAS = {'orchestrator_core', 'runtime_core', 'event_core', 'gateway_core'}

    def test_no_cross_schema_fk_in_migrations(self):
        migrations_dir = os.path.join(
            APPS_ROOT, 'execution-service', 'alembic', 'versions',
        )
        violations = []
        for f in _collect_python_files(migrations_dir):
            with open(f, encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            for schema in self.OTHER_SCHEMAS:
                if schema in content:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: references {schema}")

        assert violations == [], (
            f"Cross-schema FK detected:\n" + "\n".join(violations)
        )


# ── Layer boundary: application does not import infrastructure ─


class TestLayerBoundaries:
    """Application layer must not import infrastructure directly."""

    def test_application_does_not_import_infrastructure(self):
        app_dir = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'application',
        )
        violations = []
        for f in _collect_python_files(app_dir):
            imports = _extract_full_imports(f)
            for imp in imports:
                if 'infrastructure' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Application layer imports infrastructure:\n" + "\n".join(violations)
        )

    def test_domain_does_not_import_application(self):
        domain_dir = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'domain',
        )
        violations = []
        for f in _collect_python_files(domain_dir):
            imports = _extract_full_imports(f)
            for imp in imports:
                if 'application' in imp or 'infrastructure' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Domain layer imports application/infrastructure:\n" + "\n".join(violations)
        )


# ── G21-1: No raw command in API or service ──────────────────


class TestNoRawCommandInAPI:
    """API and application layers must not accept raw 'command' from body."""

    RAW_COMMAND_PATTERNS = [
        re.compile(r'body\[?.*["\']command["\']\]?'),
        re.compile(r'body\.get\(["\']command["\']\)'),
        re.compile(r'body\[?.*["\']raw_command["\']\]?'),
        re.compile(r'body\.get\(["\']raw_command["\']\)'),
    ]

    def test_no_raw_command_from_request(self):
        """No route or handler should accept a raw command field."""
        exec_src = os.path.join(APPS_ROOT, 'execution-service', 'src')
        api_dir = os.path.join(exec_src, 'api')
        app_dir = os.path.join(exec_src, 'application')

        violations = []
        for d in [api_dir, app_dir]:
            for f in _collect_python_files(d):
                with open(f, encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                for pattern in self.RAW_COMMAND_PATTERNS:
                    if pattern.search(content):
                        rel = os.path.relpath(f, APPS_ROOT)
                        violations.append(f"{rel}: accepts raw command from request")

        assert violations == [], (
            f"Raw command field in API/app:\n" + "\n".join(violations)
        )


# ── G21-2: Docker exec uses argv, not shell string ──────────


class TestDockerExecUsesArgv:
    """Docker execution backend must use argv lists, not shell strings."""

    @staticmethod
    def _has_shell_true_keyword(filepath: str) -> bool:
        """Check if any function call in the file uses shell=True as a keyword."""
        try:
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (kw.arg == 'shell'
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True):
                        return True
        return False

    def test_no_shell_true_in_execution_backend(self):
        """Docker execution backend must not use shell=True in code."""
        backend_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'infrastructure',
            'sandbox', 'docker_execution_backend.py',
        )
        if not os.path.exists(backend_file):
            pytest.skip("docker_execution_backend.py not found")

        assert not self._has_shell_true_keyword(backend_file), (
            "docker_execution_backend.py must not use shell=True"
        )

    def test_no_shell_true_in_tool_registry(self):
        """Tool registry must not use shell=True in code."""
        registry_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'application',
            'tool_registry.py',
        )
        if not os.path.exists(registry_file):
            pytest.skip("tool_registry.py not found")

        assert not self._has_shell_true_keyword(registry_file), (
            "tool_registry.py must not use shell=True"
        )
