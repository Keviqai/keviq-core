"""Architecture tests for Slice 4 — PR24 Recovery Observability & Sweep Foundation.

G24-1: Execution-service has idx_sandboxes_stuck migration.
G24-2: Orchestrator has recovery indexes migration (runs + steps).
G24-3: terminate_sandbox returns bool (not None).
G24-4: _NIL_UUID is extracted as module constant (no repeated UUID literals).
G24-5: Orchestrator recovery sweep exists and emits recovery-specific events.
G24-6: Recovery events are distinct from normal lifecycle events.
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))


def _read_file(filepath: str) -> str:
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        return f.read()


# ── G24-1: idx_sandboxes_stuck migration exists ───────────────


class TestExecutionServiceStuckIndex:
    def test_migration_creates_idx_sandboxes_stuck(self):
        migrations_dir = os.path.join(
            APPS_ROOT, 'execution-service', 'alembic', 'versions',
        )
        if not os.path.isdir(migrations_dir):
            pytest.skip("execution-service migrations not found")

        found = False
        for f in os.listdir(migrations_dir):
            if f.endswith('.py'):
                content = _read_file(os.path.join(migrations_dir, f))
                if 'idx_sandboxes_stuck' in content:
                    found = True
                    assert 'sandbox_status' in content
                    break

        assert found, "Migration creating idx_sandboxes_stuck not found"


# ── G24-2: Orchestrator recovery indexes ──────────────────────


class TestOrchestratorRecoveryIndexes:
    def test_migration_creates_run_status_index(self):
        migrations_dir = os.path.join(
            APPS_ROOT, 'orchestrator', 'alembic', 'versions',
        )
        if not os.path.isdir(migrations_dir):
            pytest.skip("orchestrator migrations not found")

        found = False
        for f in os.listdir(migrations_dir):
            if f.endswith('.py'):
                content = _read_file(os.path.join(migrations_dir, f))
                if 'idx_runs_status_created' in content:
                    found = True
                    assert 'run_status' in content
                    break

        assert found, "Migration creating idx_runs_status_created not found"

    def test_migration_creates_step_status_index(self):
        migrations_dir = os.path.join(
            APPS_ROOT, 'orchestrator', 'alembic', 'versions',
        )
        if not os.path.isdir(migrations_dir):
            pytest.skip("orchestrator migrations not found")

        found = False
        for f in os.listdir(migrations_dir):
            if f.endswith('.py'):
                content = _read_file(os.path.join(migrations_dir, f))
                if 'idx_steps_status_created' in content:
                    found = True
                    assert 'step_status' in content
                    break

        assert found, "Migration creating idx_steps_status_created not found"


# ── G24-3: terminate_sandbox returns bool ─────────────────────


class TestTerminateSandboxReturnsBool:
    def test_client_terminate_returns_bool(self):
        client_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'infrastructure',
            'execution_service_client.py',
        )
        if not os.path.exists(client_file):
            pytest.skip("execution_service_client.py not found")

        content = _read_file(client_file)

        # Method signature may span multiple lines; check -> bool near terminate_sandbox
        assert re.search(
            r'def terminate_sandbox\b[\s\S]*?->\s*bool', content,
        ), "terminate_sandbox must return bool"

        # Should have both True and False return paths
        assert 'return True' in content
        assert 'return False' in content

    def test_port_terminate_returns_bool(self):
        ports_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'ports.py',
        )
        if not os.path.exists(ports_file):
            pytest.skip("ports.py not found")

        content = _read_file(ports_file)
        assert re.search(
            r'def terminate_sandbox\b[\s\S]*?->\s*bool', content,
        ), "ExecutionServicePort.terminate_sandbox must return bool"


# ── G24-4: _NIL_UUID extracted (no repeated UUID literals) ───


class TestNilUuidExtracted:
    def test_no_repeated_nil_uuid_literals(self):
        client_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'infrastructure',
            'execution_service_client.py',
        )
        if not os.path.exists(client_file):
            pytest.skip("execution_service_client.py not found")

        content = _read_file(client_file)

        # Must have _NIL_UUID constant
        assert '_NIL_UUID' in content, "Must extract _NIL_UUID constant"

        # Should not have more than 1 occurrence of the full zero UUID string
        zero_uuid = '00000000-0000-0000-0000-000000000000'
        count = content.count(zero_uuid)
        assert count <= 1, (
            f"Found {count} occurrences of zero UUID literal; "
            "should use _NIL_UUID constant instead"
        )


# ── G24-5: Orchestrator recovery sweep exists ─────────────────


class TestOrchestratorRecoverySweep:
    def test_recovery_module_exists(self):
        recovery_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'recovery.py',
        )
        assert os.path.exists(recovery_file), (
            "orchestrator must have recovery.py in application layer"
        )

    def test_recovery_is_idempotent_by_design(self):
        """Recovery code must have guard checks for already-terminal entities."""
        recovery_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'recovery.py',
        )
        if not os.path.exists(recovery_file):
            pytest.skip("recovery.py not found")

        content = _read_file(recovery_file)

        assert 'is_terminal' in content, (
            "Recovery must check is_terminal before acting"
        )
        assert 'skipped_already_terminal' in content, (
            "Recovery must have skipped_already_terminal guard"
        )
        assert 'skipped_no_longer_stuck' in content, (
            "Recovery must have skipped_no_longer_stuck guard"
        )

    def test_recovery_does_not_import_infrastructure(self):
        recovery_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'recovery.py',
        )
        if not os.path.exists(recovery_file):
            pytest.skip("recovery.py not found")

        try:
            with open(recovery_file, encoding='utf-8') as f:
                tree = ast.parse(f.read())
        except SyntaxError:
            pytest.skip("recovery.py has syntax errors")

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert 'infrastructure' not in node.module, (
                    f"recovery.py must not import infrastructure: {node.module}"
                )


# ── G24-6: Recovery events are distinct ──────────────────────


class TestRecoveryEventsDistinct:
    def test_recovery_event_factories_exist(self):
        events_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'events.py',
        )
        if not os.path.exists(events_file):
            pytest.skip("events.py not found")

        content = _read_file(events_file)

        required = [
            'run_recovered_event',
            'step_recovered_event',
            'task_recovered_event',
        ]
        for name in required:
            assert name in content, f"events.py must define {name}"

    def test_recovery_events_use_recovered_type(self):
        """Recovery events must use .recovered suffix, not reuse .failed."""
        events_file = os.path.join(
            APPS_ROOT, 'orchestrator', 'src', 'application', 'events.py',
        )
        if not os.path.exists(events_file):
            pytest.skip("events.py not found")

        content = _read_file(events_file)

        for entity in ('run', 'step', 'task'):
            assert f'"{entity}.recovered"' in content, (
                f"Recovery event for {entity} must use event_type '{entity}.recovered'"
            )
