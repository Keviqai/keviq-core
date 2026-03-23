"""Architecture tests: verify import boundaries and schema ownership for artifact-service.

Gates:
- G26-1: artifact-service sole write authority for artifact_core
- G26-4: lineage append-only (no UPDATE/DELETE on edges)
- G26-5: no signed URL / download / publish scope (Slice 5 boundary)
- No cross-schema FK outside artifact_core
- Domain does not import infrastructure
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = SERVICE_ROOT / "src"
DOMAIN_DIR = SRC_DIR / "domain"
MIGRATION_DIR = SERVICE_ROOT / "alembic" / "versions"
REPO_ROOT = SERVICE_ROOT.parent.parent  # Keviq Core root


def _get_python_files(directory: Path) -> list[Path]:
    """Get all .py files recursively."""
    return list(directory.rglob("*.py"))


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── G26-1: Schema Ownership ──────────────────────────────────


class TestSchemaOwnership:
    """artifact_core schema must only be written by artifact-service."""

    def test_no_artifact_core_writes_outside_artifact_service(self):
        """No service other than artifact-service should write to artifact_core schema."""
        apps_dir = REPO_ROOT / "apps"
        violations = []

        for service_dir in apps_dir.iterdir():
            if not service_dir.is_dir():
                continue
            if service_dir.name == "artifact-service":
                continue

            src_dir = service_dir / "src"
            if not src_dir.exists():
                continue

            for py_file in src_dir.rglob("*.py"):
                content = _read_file(py_file)
                # Check for direct SQL writes to artifact_core
                if "artifact_core" in content:
                    # Allow reads (SELECT) but flag writes
                    lower = content.lower()
                    for keyword in ["insert", "update", "delete", "create table", "alter table", "drop table"]:
                        if keyword in lower and "artifact_core" in content:
                            violations.append(
                                f"{py_file.relative_to(REPO_ROOT)}: "
                                f"references artifact_core with {keyword.upper()}"
                            )

        assert violations == [], (
            f"G26-1 violation: services outside artifact-service write to artifact_core:\n"
            + "\n".join(violations)
        )

    def test_migrations_only_use_artifact_core_schema(self):
        """artifact-service migrations must only touch artifact_core schema."""
        for mig_file in MIGRATION_DIR.glob("*.py"):
            if mig_file.name == ".gitkeep":
                continue
            content = _read_file(mig_file)
            if "schema=" in content:
                # Every schema= reference should be artifact_core
                import re
                schemas = re.findall(r"schema=['\"]([^'\"]+)['\"]", content)
                for schema in schemas:
                    assert schema == "artifact_core", (
                        f"Migration {mig_file.name} references schema "
                        f"{schema!r}, expected only 'artifact_core'"
                    )


# ── No Cross-Schema FK ───────────────────────────────────────


class TestNoCrossSchemaFK:
    """artifact_core should not have FKs to other schemas."""

    def test_no_cross_schema_fk_in_migrations(self):
        """All ForeignKeyConstraint references must be within artifact_core."""
        for mig_file in MIGRATION_DIR.glob("*.py"):
            if mig_file.name == ".gitkeep":
                continue
            content = _read_file(mig_file)
            if "ForeignKeyConstraint" not in content:
                continue

            import re
            # Find FK target references like 'schema.table.column'
            # Match both literal strings and f-string patterns
            fk_targets = re.findall(
                r"ForeignKeyConstraint\([^)]*\[([^\]]+)\]",
                content,
                re.DOTALL,
            )
            for target_group in fk_targets:
                # Parse the target column references
                refs = re.findall(r"['\"]([^'\"]+)['\"]", target_group)
                for ref in refs:
                    if "." in ref:
                        schema = ref.split(".")[0]
                        # Skip f-string variable references like {SCHEMA}
                        if schema.startswith("{") and schema.endswith("}"):
                            # Resolve the variable from the migration source
                            var_name = schema[1:-1]
                            var_match = re.search(
                                rf"{var_name}\s*=\s*['\"]([^'\"]+)['\"]", content,
                            )
                            if var_match:
                                schema = var_match.group(1)
                            else:
                                continue  # Cannot resolve — skip
                        assert schema == "artifact_core", (
                            f"Migration {mig_file.name} has cross-schema FK "
                            f"to {schema!r}, expected only artifact_core"
                        )


# ── G26-4: Lineage Append-Only ───────────────────────────────


class TestLineageAppendOnly:
    """No UPDATE or DELETE operations on artifact_lineage_edges in application code."""

    def test_no_update_delete_on_lineage_edges_in_src(self):
        """Source code must not UPDATE or DELETE lineage edges (L2: append-only)."""
        violations = []

        for py_file in SRC_DIR.rglob("*.py"):
            content = _read_file(py_file)
            lower = content.lower()
            if "lineage_edge" in lower or "artifact_lineage" in lower:
                for keyword in ["update", "delete"]:
                    # Simple heuristic: flag if keyword appears near lineage reference
                    # Ignore comments and docstrings for false positives
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped.startswith('"""'):
                            continue
                        if keyword in stripped.lower() and (
                            "lineage_edge" in stripped.lower()
                            or "artifact_lineage" in stripped.lower()
                        ):
                            violations.append(
                                f"{py_file.relative_to(SERVICE_ROOT)}:{i}: "
                                f"{keyword.upper()} on lineage edges"
                            )

        assert violations == [], (
            f"G26-4 violation: lineage edges must be append-only:\n"
            + "\n".join(violations)
        )


# ── Domain Import Boundaries ─────────────────────────────────


class TestDomainBoundaries:
    """Domain layer must not import from infrastructure or application layers."""

    def test_domain_does_not_import_infrastructure(self):
        """Domain modules must not import from src.infrastructure."""
        violations = []

        for py_file in DOMAIN_DIR.rglob("*.py"):
            content = _read_file(py_file)
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "infrastructure" in node.module or "src.infrastructure" in node.module:
                        violations.append(
                            f"{py_file.relative_to(SERVICE_ROOT)}:{node.lineno}: "
                            f"imports {node.module}"
                        )

        assert violations == [], (
            f"Domain imports infrastructure:\n" + "\n".join(violations)
        )

    def test_domain_does_not_import_application(self):
        """Domain modules must not import from src.application."""
        violations = []

        for py_file in DOMAIN_DIR.rglob("*.py"):
            content = _read_file(py_file)
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "application" in node.module or "src.application" in node.module:
                        violations.append(
                            f"{py_file.relative_to(SERVICE_ROOT)}:{node.lineno}: "
                            f"imports {node.module}"
                        )

        assert violations == [], (
            f"Domain imports application:\n" + "\n".join(violations)
        )

    def test_domain_does_not_import_api(self):
        """Domain modules must not import from src.api."""
        violations = []

        for py_file in DOMAIN_DIR.rglob("*.py"):
            content = _read_file(py_file)
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("src.api"):
                        violations.append(
                            f"{py_file.relative_to(SERVICE_ROOT)}:{node.lineno}: "
                            f"imports {node.module}"
                        )

        assert violations == [], (
            f"Domain imports API:\n" + "\n".join(violations)
        )


# ── G26-5: No Delivery Scope ─────────────────────────────────


class TestNoDeliveryScope:
    """Slice 5 must not introduce download/signed-URL/publish endpoints."""

    def test_no_signed_url_in_routes(self):
        """No signed URL generation in current routes."""
        routes_file = SRC_DIR / "api" / "routes.py"
        if not routes_file.exists():
            return
        content = _read_file(routes_file)
        lower = content.lower()
        assert "signed_url" not in lower, "G26-5: signed URL found in routes"
        assert "download" not in lower, "G26-5: download endpoint found in routes"
        assert "presign" not in lower, "G26-5: presigned URL found in routes"
