"""Import boundary enforcement for all backend services.

Rules enforced:
  1. domain/ must NOT import from infrastructure/ or api/
  2. application/ must NOT import from api/ or infrastructure/
  3. api/ must NOT import from infrastructure/ (should go through application/)
  4. No service may import from another service's internal modules

These rules enforce the layered architecture per doc 16.
"""

import ast
import os
import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))

# Services with Python backends (skip 'web' which is TS)
PYTHON_SERVICES = [
    d for d in os.listdir(APPS_ROOT)
    if os.path.isdir(os.path.join(APPS_ROOT, d))
    and os.path.isfile(os.path.join(APPS_ROOT, d, 'pyproject.toml'))
]

# Forbidden import patterns per layer
# Key = source layer, Value = list of forbidden target layers
LAYER_RULES = {
    'domain': ['infrastructure', 'api'],
    'application': ['api', 'infrastructure'],
    'api': ['infrastructure'],
}

# Known pre-existing violations tracked for future cleanup.
# Format: (service, source_layer, forbidden_layer, filename)
# These services use composition-in-routes pattern from Phase A/B that predates
# the ports/bootstrap pattern. They should be migrated in a future PR.
_KNOWN_VIOLATIONS: set[tuple[str, str, str, str]] = {
    # orchestrator: api/routes.py imports outbox relay for diagnostics
    ('orchestrator', 'api', 'infrastructure', 'routes.py'),
    # orchestrator: api/routes_brief.py imports audit_clients for BackgroundTasks
    ('orchestrator', 'api', 'infrastructure', 'routes_brief.py'),
    # orchestrator: api/approval_routes.py imports notification/service clients for BackgroundTasks
    ('orchestrator', 'api', 'infrastructure', 'approval_routes.py'),
    # orchestrator: api/tool_approval_routes.py imports notification clients for BackgroundTasks
    ('orchestrator', 'api', 'infrastructure', 'tool_approval_routes.py'),
    # agent-runtime: api/routes.py builds service with real infra deps
    ('agent-runtime', 'api', 'infrastructure', 'routes.py'),
    # artifact-service: api/routes.py imports outbox relay (now in routes_internal.py)
    ('artifact-service', 'api', 'infrastructure', 'routes.py'),
    ('artifact-service', 'api', 'infrastructure', 'routes_internal.py'),
}


class ImportCollector(ast.NodeVisitor):
    """Collect all import strings from a Python file."""

    def __init__(self):
        self.imports: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.append((node.lineno, node.module))


def _get_imports(filepath: str) -> list[tuple[int, str]]:
    """Parse a Python file and return all import module paths."""
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return []
    collector = ImportCollector()
    collector.visit(tree)
    return collector.imports


def _check_layer_boundaries(service: str) -> list[str]:
    """Check that layers within a service respect import boundaries."""
    violations = []
    svc_root = os.path.join(APPS_ROOT, service, 'src')

    for source_layer, forbidden_targets in LAYER_RULES.items():
        layer_dir = os.path.join(svc_root, source_layer)
        if not os.path.isdir(layer_dir):
            continue

        for dirpath, _, filenames in os.walk(layer_dir):
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                filepath = os.path.join(dirpath, filename)
                imports = _get_imports(filepath)

                for lineno, module in imports:
                    for forbidden in forbidden_targets:
                        if (module.startswith(f'src.{forbidden}')
                            or module.startswith(f'{forbidden}.')
                            or module == forbidden):
                            violations.append(
                                f"{filepath}:{lineno} — "
                                f"{source_layer}/ imports from {forbidden}/: "
                                f"'{module}'"
                            )
    return violations


def _check_cross_service_imports(service: str) -> list[str]:
    """Check that a service doesn't import from other services' internal modules."""
    violations = []
    svc_root = os.path.join(APPS_ROOT, service, 'src')
    if not os.path.isdir(svc_root):
        return violations

    other_services = [s for s in PYTHON_SERVICES if s != service]

    for dirpath, _, filenames in os.walk(svc_root):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            imports = _get_imports(filepath)

            for lineno, module in imports:
                for other in other_services:
                    other_snake = other.replace('-', '_')
                    if (module.startswith(f'apps.{other}')
                        or module.startswith(f'apps.{other_snake}')):
                        violations.append(
                            f"{filepath}:{lineno} — "
                            f"cross-service import: '{module}' (from {service} to {other})"
                        )
    return violations


def _filter_known_violations(service: str, violations: list[str]) -> list[str]:
    """Remove pre-existing known violations that are tracked for future cleanup."""
    filtered = []
    for v in violations:
        skip = False
        for svc, src_layer, forbidden, filename in _KNOWN_VIOLATIONS:
            if (service == svc
                    and f"{src_layer}/ imports from {forbidden}/" in v
                    and f"{filename}:" in v):
                skip = True
                break
        if not skip:
            filtered.append(v)
    return filtered


@pytest.mark.parametrize('service', PYTHON_SERVICES)
def test_layer_boundaries(service: str):
    """Each service's layers must respect import boundaries."""
    violations = _check_layer_boundaries(service)
    violations = _filter_known_violations(service, violations)
    assert violations == [], (
        f"LAYER BOUNDARY VIOLATION in {service}:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


@pytest.mark.parametrize('service', PYTHON_SERVICES)
def test_no_cross_service_imports(service: str):
    """No service may import from another service's internal modules."""
    violations = _check_cross_service_imports(service)
    assert violations == [], (
        f"CROSS-SERVICE IMPORT VIOLATION from {service}:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
