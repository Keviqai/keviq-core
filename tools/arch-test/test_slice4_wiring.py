"""Architecture tests for Slice 4 — PR22 Orchestrator ↔ Execution-Service Wiring.

G22-1: Orchestrator does not import Docker/backend execution classes.
G22-2: Orchestrator calls execution-service only via ExecutionServicePort.
G22-3: Correlation ID propagation in dispatch calls.
G22-4: Execution failure maps to step outcome (no silent swallow).
G22-5: No raw command path from orchestrator payload.
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


# ── G22-1: Orchestrator does not import Docker/backend ──────


class TestOrchestratorNoDirectBackend:
    """Orchestrator must not import Docker, sandbox backend, or
    execution-service infrastructure directly."""

    FORBIDDEN_MODULES = {'docker', 'docker.errors'}

    FORBIDDEN_IMPORT_PATTERNS = [
        'execution_service.src',
        'infrastructure.sandbox',
        'docker_execution_backend',
        'docker_backend',
    ]

    def test_orchestrator_does_not_import_docker(self):
        """No file in orchestrator should import the docker package."""
        orch_src = os.path.join(APPS_ROOT, 'orchestrator', 'src')
        violations = []
        for f in _collect_python_files(orch_src):
            imports = _extract_imports(f)
            for imp in imports:
                if imp == 'docker':
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports docker")

        assert violations == [], (
            f"Orchestrator must not import docker directly:\n"
            + "\n".join(violations)
        )

    def test_orchestrator_does_not_import_execution_service_internals(self):
        """Orchestrator must not import from execution-service source."""
        orch_src = os.path.join(APPS_ROOT, 'orchestrator', 'src')
        violations = []
        for f in _collect_python_files(orch_src):
            imports = _extract_full_imports(f)
            for imp in imports:
                for pattern in self.FORBIDDEN_IMPORT_PATTERNS:
                    if pattern in imp:
                        rel = os.path.relpath(f, APPS_ROOT)
                        violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Orchestrator must not import execution-service internals:\n"
            + "\n".join(violations)
        )


# ── G22-2: Orchestrator uses port, not concrete client ──────


class TestOrchestratorUsesPort:
    """Application layer must depend on ExecutionServicePort,
    not on HttpExecutionServiceClient directly."""

    def test_application_does_not_import_http_client(self):
        """Application layer files should not import the HTTP client."""
        app_dir = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application')
        violations = []
        for f in _collect_python_files(app_dir):
            imports = _extract_full_imports(f)
            for imp in imports:
                if 'execution_service_client' in imp or 'HttpExecutionServiceClient' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Application layer must use port, not concrete client:\n"
            + "\n".join(violations)
        )

    def test_execution_loop_uses_port_type(self):
        """execution_loop.py should reference ExecutionServicePort, not concrete."""
        loop_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'execution_loop.py',
        )
        if not os.path.exists(loop_file):
            pytest.skip("execution_loop.py not found")

        with open(loop_file, encoding='utf-8') as f:
            content = f.read()

        assert 'ExecutionServicePort' in content, (
            "execution_loop.py should use ExecutionServicePort type"
        )
        assert 'HttpExecutionServiceClient' not in content, (
            "execution_loop.py must not reference concrete HTTP client"
        )


# ── G22-5: No raw command from orchestrator ─────────────────


class TestNoRawCommandFromOrchestrator:
    """Orchestrator must not pass raw commands to execution-service.
    Only tool_name + tool_input through the registered tool interface."""

    RAW_COMMAND_PATTERNS = [
        re.compile(r'["\']command["\']'),
        re.compile(r'["\']raw_command["\']'),
        re.compile(r'["\']shell_command["\']'),
    ]

    def test_no_raw_command_in_execution_loop(self):
        """execution_loop.py should not construct raw commands."""
        loop_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'execution_loop.py',
        )
        if not os.path.exists(loop_file):
            pytest.skip("execution_loop.py not found")

        with open(loop_file, encoding='utf-8') as f:
            content = f.read()

        violations = []
        for pattern in self.RAW_COMMAND_PATTERNS:
            if pattern.search(content):
                violations.append(f"Found {pattern.pattern} in execution_loop.py")

        assert violations == [], (
            f"No raw command from orchestrator:\n" + "\n".join(violations)
        )

    def test_no_raw_command_in_client(self):
        """Execution service client should not accept raw commands."""
        client_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'infrastructure',
            'execution_service_client.py',
        )
        if not os.path.exists(client_file):
            pytest.skip("execution_service_client.py not found")

        with open(client_file, encoding='utf-8') as f:
            content = f.read()

        for pattern in self.RAW_COMMAND_PATTERNS:
            assert not pattern.search(content), (
                f"Client must not accept raw commands ({pattern.pattern})"
            )


# ── Layer boundary: orchestrator application vs infrastructure ──


class TestOrchestratorLayerBoundaries:
    """Application layer must not import infrastructure directly
    (except through bootstrap)."""

    def test_application_does_not_import_infrastructure(self):
        """No file in application/ should import from infrastructure/."""
        app_dir = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application')
        violations = []
        for f in _collect_python_files(app_dir):
            imports = _extract_full_imports(f)
            for imp in imports:
                if 'infrastructure' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Orchestrator application imports infrastructure:\n"
            + "\n".join(violations)
        )

    def test_domain_does_not_import_application(self):
        """No file in domain/ should import from application/."""
        domain_dir = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'domain')
        violations = []
        for f in _collect_python_files(domain_dir):
            imports = _extract_full_imports(f)
            for imp in imports:
                if 'application' in imp or 'infrastructure' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Orchestrator domain imports application/infrastructure:\n"
            + "\n".join(violations)
        )
