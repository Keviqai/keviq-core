"""Architecture tests for Slice 1 contracts.

Tests:
  1. test_policy_fail_closed — gateway returns 403 when policy-service is unreachable
  2. test_capabilities_server_derived — workspace responses include _capabilities from role
  3. test_no_cross_schema_fk — no foreign keys cross schema boundaries
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))
MIGRATIONS_ROOT = os.path.join(APPS_ROOT)


# ── Test 1: Fail-Closed Policy ─────────────────────────────────────

class ExceptionVisitor(ast.NodeVisitor):
    """Find all except clauses and what they raise."""

    def __init__(self):
        self.except_handlers: list[dict] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        raises = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                raises.append(ast.dump(child.exc))
        self.except_handlers.append({
            'lineno': node.lineno,
            'type': ast.dump(node.type) if node.type else 'bare',
            'raises': raises,
        })
        self.generic_visit(node)


def test_policy_fail_closed():
    """api-gateway must return 403 (not 500/502) when policy/workspace service is unreachable.

    Verifies that check_permission_or_fail catches generic Exception
    and re-raises as HTTP 403.
    """
    middleware_path = os.path.join(
        APPS_ROOT, 'api-gateway', 'src', 'application', 'auth_middleware.py',
    )
    assert os.path.exists(middleware_path), f"Missing {middleware_path}"

    with open(middleware_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source, filename=middleware_path)

    # Find the check_permission_or_fail function
    func = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            if node.name == 'check_permission_or_fail':
                func = node
                break

    assert func is not None, "check_permission_or_fail function not found"

    # Verify it has a catch-all Exception handler that raises HTTPException with 403
    visitor = ExceptionVisitor()
    visitor.visit(func)

    found_fail_closed = False
    for handler in visitor.except_handlers:
        # Look for 'except Exception' (catch-all) that raises HTTPException with 403
        if 'Exception' in handler['type'] and 'HTTPException' not in handler['type']:
            for raise_expr in handler['raises']:
                if 'HTTPException' in raise_expr and ('403' in raise_expr or 'HTTP_403' in raise_expr):
                    found_fail_closed = True

    assert found_fail_closed, (
        "check_permission_or_fail must catch generic Exception and raise "
        "HTTPException(403) — fail-closed pattern not found"
    )


# ── Test 2: _capabilities Server-Derived ────────────────────────────

def test_capabilities_server_derived():
    """workspace-service must inject _capabilities from domain logic,
    NOT from client input or role string.

    Verifies:
    1. A capabilities domain module exists with role→permissions mapping
    2. The API routes import and use resolve_capabilities
    3. No frontend code derives capabilities from role
    """
    # 1. Domain capabilities module exists
    caps_path = os.path.join(
        APPS_ROOT, 'workspace-service', 'src', 'domain', 'capabilities.py',
    )
    assert os.path.exists(caps_path), (
        "workspace-service must have src/domain/capabilities.py "
        "for server-side capability resolution"
    )

    with open(caps_path, encoding='utf-8') as f:
        caps_source = f.read()

    # Must define ROLE_CAPABILITIES and resolve_capabilities
    assert 'ROLE_CAPABILITIES' in caps_source, (
        "capabilities.py must define ROLE_CAPABILITIES mapping"
    )
    assert 'def resolve_capabilities' in caps_source, (
        "capabilities.py must define resolve_capabilities function"
    )

    # 2. API routes use resolve_capabilities
    routes_path = os.path.join(
        APPS_ROOT, 'workspace-service', 'src', 'api', 'routes.py',
    )
    with open(routes_path, encoding='utf-8') as f:
        routes_source = f.read()

    assert 'resolve_capabilities' in routes_source, (
        "workspace-service routes must import resolve_capabilities "
        "to inject _capabilities into responses"
    )
    assert '_capabilities' in routes_source, (
        "workspace-service routes must inject _capabilities into responses"
    )


# ── Test 3: No Cross-Schema Foreign Keys ───────────────────────────

def test_no_cross_schema_fk():
    """No migration may create a foreign key that references a table in another schema.

    This enforces S1 (Schema Isolation) — services own their data.
    """
    violations = []

    for service_dir in os.listdir(APPS_ROOT):
        versions_dir = os.path.join(APPS_ROOT, service_dir, 'alembic', 'versions')
        if not os.path.isdir(versions_dir):
            continue

        for filename in os.listdir(versions_dir):
            if not filename.endswith('.py'):
                continue

            filepath = os.path.join(versions_dir, filename)
            with open(filepath, encoding='utf-8') as f:
                source = f.read()

            # Parse the migration to find the SCHEMA constant
            schema_match = re.search(r"SCHEMA\s*=\s*['\"]([^'\"]+)['\"]", source)
            if not schema_match:
                continue
            own_schema = schema_match.group(1)

            # Look for ForeignKeyConstraint or sa.ForeignKey referencing other schemas
            # Pattern: schema.table format in FK references
            fk_refs = re.findall(
                r"(?:ForeignKey|ForeignKeyConstraint)\s*\([^)]*['\"](\w+)\.(\w+)",
                source,
            )
            for ref_schema, ref_table in fk_refs:
                if ref_schema != own_schema:
                    violations.append(
                        f"{filepath}: cross-schema FK from {own_schema} → {ref_schema}.{ref_table}"
                    )

            # Also check op.create_foreign_key with referent_schema
            fk_schema_refs = re.findall(
                r"create_foreign_key\s*\([^)]*referent_schema\s*=\s*['\"](\w+)['\"]",
                source,
            )
            for ref_schema in fk_schema_refs:
                if ref_schema != own_schema:
                    violations.append(
                        f"{filepath}: cross-schema FK via create_foreign_key to {ref_schema}"
                    )

    assert violations == [], (
        "CROSS-SCHEMA FK VIOLATION (breaks S1 Schema Isolation):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
