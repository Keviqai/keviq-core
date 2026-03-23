"""Architecture tests for Slice 4 — PR23 Reliability Hardening.

G23-1: Claim path does not use generic upsert for execution ownership.
G23-2: Recovery service lives in execution-service app layer, not orchestrator.
G23-3: Client parses non-JSON safely (exception hierarchy exists).
G23-4: Orchestrator does not hardcode "completed" as termination reason.
G23-5: Layering from PR20–PR22 is not broken.
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


def _read_file(filepath: str) -> str:
    """Read file contents safely."""
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        return f.read()


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


# ── G23-1: Claim path uses explicit method, not generic upsert ──


class TestClaimPathNotGenericUpsert:
    """tool_execution_service must use claim_for_execution, not
    manual load + mark_executing + save."""

    def test_tool_execution_service_uses_claim(self):
        """Service should call claim_for_execution instead of manual transition."""
        svc_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'application',
            'tool_execution_service.py',
        )
        if not os.path.exists(svc_file):
            pytest.skip("tool_execution_service.py not found")

        content = _read_file(svc_file)
        assert 'claim_for_execution' in content, (
            "tool_execution_service should use claim_for_execution for atomic claim"
        )

    def test_repository_has_claim_method(self):
        """SqlSandboxRepository must implement claim_for_execution."""
        repo_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'infrastructure',
            'db', 'repositories.py',
        )
        if not os.path.exists(repo_file):
            pytest.skip("repositories.py not found")

        content = _read_file(repo_file)
        assert 'claim_for_execution' in content, (
            "Repository must implement claim_for_execution"
        )
        assert 'with_for_update' in content, (
            "claim_for_execution should use SELECT FOR UPDATE"
        )


# ── G23-2: Recovery service in execution-service, not orchestrator ──


class TestRecoveryServiceLocation:
    """Recovery logic must live in execution-service application layer."""

    def test_recovery_service_exists_in_execution_service(self):
        recovery_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'application',
            'recovery_service.py',
        )
        assert os.path.exists(recovery_file), (
            "recovery_service.py should exist in execution-service application layer"
        )

    def test_orchestrator_has_no_sandbox_recovery_service(self):
        """Orchestrator must not have sandbox-level recovery — that belongs
        in execution-service.  Orchestrator *may* have its own recovery.py
        for stuck tasks/runs/steps (added in PR24)."""
        orch_app = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application')
        violations = []
        for f in _collect_python_files(orch_app):
            basename = os.path.basename(f).lower()
            if basename == 'recovery_service.py':
                rel = os.path.relpath(f, APPS_ROOT)
                violations.append(rel)

        assert violations == [], (
            f"Orchestrator must not have sandbox recovery_service: {violations}"
        )


# ── G23-3: Client has exception hierarchy for protocol errors ──


class TestClientExceptionHierarchy:
    """Orchestrator client must have typed exceptions for protocol errors."""

    def test_exception_classes_exist(self):
        client_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'infrastructure',
            'execution_service_client.py',
        )
        if not os.path.exists(client_file):
            pytest.skip("execution_service_client.py not found")

        content = _read_file(client_file)

        required_exceptions = [
            'ExecutionServiceProtocolError',
            'ExecutionServiceUnavailable',
            'ExecutionServiceRejected',
        ]
        for exc_name in required_exceptions:
            assert exc_name in content, (
                f"Client must define {exc_name} exception class"
            )

    def test_provision_sandbox_guards_json(self):
        """provision_sandbox must guard resp.json() with try/except."""
        client_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'infrastructure',
            'execution_service_client.py',
        )
        if not os.path.exists(client_file):
            pytest.skip("execution_service_client.py not found")

        content = _read_file(client_file)

        # Should not have bare resp.json() without try/except in provision_sandbox
        # We check that ProtocolError is raised on parse failure
        assert 'ExecutionServiceProtocolError' in content
        assert 'non-json' in content.lower() or 'non_json' in content.lower()


# ── G23-4: No hardcoded "completed" termination reason ──────


class TestNoHardcodedTerminationReason:
    """Orchestrator must not hardcode 'completed' as termination reason."""

    def test_execution_loop_uses_reason_mapping(self):
        loop_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'execution_loop.py',
        )
        if not os.path.exists(loop_file):
            pytest.skip("execution_loop.py not found")

        content = _read_file(loop_file)

        # Must have a mapping function
        assert '_map_termination_reason' in content, (
            "execution_loop.py should have _map_termination_reason helper"
        )

        # The terminate_sandbox call should NOT use hardcoded reason="completed"
        # Pattern: terminate_sandbox(sandbox_id, reason="completed")
        hardcoded_pattern = re.compile(
            r'terminate_sandbox\([^)]*reason\s*=\s*["\']completed["\']',
        )
        assert not hardcoded_pattern.search(content), (
            "terminate_sandbox must not use hardcoded reason='completed'"
        )


# ── G23-5: PR20-PR22 layering not broken ────────────────────


class TestLayeringPreserved:
    """Verify PR20–PR22 arch constraints still hold."""

    def test_orchestrator_does_not_import_docker(self):
        orch_src = os.path.join(APPS_ROOT, 'orchestrator', 'src')
        violations = []
        for f in _collect_python_files(orch_src):
            imports = _extract_full_imports(f)
            for imp in imports:
                if imp.split('.')[0] == 'docker':
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Orchestrator must not import docker:\n" + "\n".join(violations)
        )

    def test_orchestrator_app_does_not_import_infrastructure(self):
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

    def test_recovery_does_not_import_orchestrator(self):
        recovery_file = os.path.join(
            APPS_ROOT, 'execution-service', 'src', 'application',
            'recovery_service.py',
        )
        if not os.path.exists(recovery_file):
            pytest.skip("recovery_service.py not found")

        imports = _extract_full_imports(recovery_file)
        violations = [imp for imp in imports if 'orchestrator' in imp]
        assert violations == [], (
            f"Recovery service must not import orchestrator: {violations}"
        )
