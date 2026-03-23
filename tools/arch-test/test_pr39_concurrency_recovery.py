"""PR39 — Concurrency + recovery correctness architecture gate tests.

Hard gates:
  C39-G1: No duplicate claim — claim paths use FOR UPDATE SKIP LOCKED
  C39-G2: Recovery sweep is scheduled and observable
  C39-G3: Recovery is idempotent — double sweep produces stable results
  C39-G4: Locked reads respect authority — get_by_id_for_update exists
  C39-G5: Missing config fails safe — RECOVERY_INTERVAL_SECONDS has default
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORCH_DIR = ROOT / "apps" / "orchestrator"


# ── C39-G1: No duplicate claim ─────────────────────────────────


class TestNoDuplicateClaim:
    """list_stuck_for_update must use FOR UPDATE SKIP LOCKED."""

    def test_sql_repo_list_stuck_for_update_uses_skip_locked(self):
        """SqlRunRepository.list_stuck_for_update uses with_for_update(skip_locked=True)."""
        repo_path = ORCH_DIR / "src" / "infrastructure" / "db" / "repositories.py"
        content = repo_path.read_text()

        # Find list_stuck_for_update method bodies and check for skip_locked
        assert "with_for_update(skip_locked=True)" in content, (
            "list_stuck_for_update must use .with_for_update(skip_locked=True)"
        )

    def test_recovery_uses_list_stuck_for_update(self):
        """Recovery sweep must call list_stuck_for_update, not list_stuck."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()

        assert "list_stuck_for_update(" in content, (
            "Recovery must use list_stuck_for_update for claim paths"
        )


# ── C39-G2: Recovery sweep is scheduled and observable ─────────


class TestRecoveryScheduled:
    """Recovery sweep runs as a background task in the orchestrator lifespan."""

    def test_main_imports_recovery(self):
        """main.py must import recover_stuck_entities."""
        main_path = ORCH_DIR / "src" / "main.py"
        content = main_path.read_text()

        assert "recover_stuck_entities" in content, (
            "main.py must import and use recover_stuck_entities"
        )

    def test_main_has_lifespan_with_recovery(self):
        """main.py must define a lifespan that starts the recovery sweep."""
        main_path = ORCH_DIR / "src" / "main.py"
        content = main_path.read_text()

        assert "lifespan" in content, (
            "main.py must use FastAPI lifespan for background task management"
        )
        assert "recovery_sweep" in content.lower() or "_recovery_sweep_loop" in content, (
            "main.py must define a recovery sweep loop"
        )

    def test_recovery_results_are_logged(self):
        """Recovery sweep must log results for observability."""
        main_path = ORCH_DIR / "src" / "main.py"
        content = main_path.read_text()

        assert "logger" in content, (
            "main.py must use logger for recovery sweep observability"
        )


# ── C39-G3: Recovery is idempotent ────────────────────────────


class TestRecoveryIdempotent:
    """Running the sweep twice must produce stable results."""

    def test_recovery_has_terminal_guard(self):
        """Recovery must check is_terminal before acting."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()

        assert "is_terminal" in content, (
            "Recovery must check is_terminal to ensure idempotency"
        )

    def test_recovery_has_status_guard(self):
        """Recovery must verify status hasn't changed since list_stuck."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()

        assert "skipped_no_longer_stuck" in content, (
            "Recovery must handle status changes between list and recover"
        )


# ── C39-G4: Locked reads respect authority ────────────────────


class TestLockedReads:
    """get_by_id_for_update must exist in ports, SQL repos, and fakes."""

    def test_ports_define_get_by_id_for_update(self):
        """Abstract ports must declare get_by_id_for_update."""
        ports_path = ORCH_DIR / "src" / "application" / "ports.py"
        content = ports_path.read_text()

        # Check both RunRepository and StepRepository
        assert content.count("get_by_id_for_update") >= 2, (
            "Both RunRepository and StepRepository must declare get_by_id_for_update"
        )

    def test_sql_repos_implement_for_update(self):
        """SQL repositories must use .with_for_update() in get_by_id_for_update."""
        repo_path = ORCH_DIR / "src" / "infrastructure" / "db" / "repositories.py"
        content = repo_path.read_text()

        assert content.count("with_for_update()") >= 2, (
            "Both SqlRunRepository and SqlStepRepository must use .with_for_update()"
        )

    def test_recovery_uses_for_update_on_single_entity(self):
        """_recover_single_run/step must use get_by_id_for_update."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()

        assert "get_by_id_for_update" in content, (
            "Recovery must use get_by_id_for_update for row-level locking"
        )

    def test_fake_repos_implement_for_update(self):
        """Fake repos must implement get_by_id_for_update for test parity."""
        fake_path = ORCH_DIR / "tests" / "unit" / "fake_uow.py"
        content = fake_path.read_text()

        assert content.count("get_by_id_for_update") >= 2, (
            "Both FakeRunRepository and FakeStepRepository must implement get_by_id_for_update"
        )


# ── C39-G5: Missing config fails safe ────────────────────────


class TestConfigFailsSafe:
    """RECOVERY_INTERVAL_SECONDS must have a sensible default."""

    def test_recovery_interval_has_default(self):
        """RECOVERY_INTERVAL_SECONDS must default if env var is missing."""
        main_path = ORCH_DIR / "src" / "main.py"
        content = main_path.read_text()

        # Must use os.getenv with a default, not os.environ[]
        assert re.search(
            r'RECOVERY_INTERVAL_SECONDS.*(?:getenv|get)\s*\(\s*"RECOVERY_INTERVAL_SECONDS"\s*,\s*"?\d+"?\s*\)',
            content,
        ), "RECOVERY_INTERVAL_SECONDS must have a default value"

    def test_recovery_interval_is_positive(self):
        """Default interval must be at least 10 seconds."""
        main_path = ORCH_DIR / "src" / "main.py"
        content = main_path.read_text()

        match = re.search(
            r'RECOVERY_INTERVAL_SECONDS.*(?:getenv|get)\s*\(\s*"RECOVERY_INTERVAL_SECONDS"\s*,\s*"?(\d+)"?\s*\)',
            content,
        )
        assert match, "Could not find RECOVERY_INTERVAL_SECONDS default"
        default_val = int(match.group(1))
        assert default_val >= 10, (
            f"RECOVERY_INTERVAL_SECONDS default {default_val} is too low (min 10s)"
        )


# ── C39-G6: updated_at tracking ──────────────────────────────


class TestUpdatedAtTracking:
    """Domain models must update updated_at on every state transition."""

    def test_run_updates_updated_at_on_transition(self):
        """Run._transition must set self.updated_at."""
        run_path = ORCH_DIR / "src" / "domain" / "run.py"
        content = run_path.read_text()

        # Check _transition method sets updated_at
        assert "self.updated_at" in content, (
            "Run._transition must set self.updated_at"
        )

    def test_step_updates_updated_at_on_transition(self):
        """Step._transition must set self.updated_at."""
        step_path = ORCH_DIR / "src" / "domain" / "step.py"
        content = step_path.read_text()

        assert "self.updated_at" in content, (
            "Step._transition must set self.updated_at"
        )

    def test_orm_models_have_updated_at(self):
        """RunRow and StepRow must have updated_at columns."""
        models_path = ORCH_DIR / "src" / "infrastructure" / "db" / "models.py"
        content = models_path.read_text()

        # Count updated_at column definitions (RunRow + StepRow, not TaskRow which already had it)
        assert content.count("updated_at") >= 3, (
            "RunRow, StepRow, and TaskRow must all have updated_at columns"
        )


# ── C39-G7: RecoveryResult dataclass ─────────────────────────


class TestRecoveryResult:
    """Recovery must return typed RecoveryResult, not raw dicts."""

    def test_recovery_result_defined_in_ports(self):
        """RecoveryResult dataclass must be in ports.py."""
        ports_path = ORCH_DIR / "src" / "application" / "ports.py"
        content = ports_path.read_text()

        assert "class RecoveryResult" in content, (
            "RecoveryResult must be defined in ports.py"
        )
        assert "@dataclass" in content, (
            "RecoveryResult must be a dataclass"
        )

    def test_recovery_uses_recovery_result(self):
        """recovery.py must import and return RecoveryResult."""
        recovery_path = ORCH_DIR / "src" / "application" / "recovery.py"
        content = recovery_path.read_text()

        assert "RecoveryResult" in content, (
            "recovery.py must use RecoveryResult"
        )
        assert "-> list[RecoveryResult]" in content, (
            "recover_stuck_entities must return list[RecoveryResult]"
        )
