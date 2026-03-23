"""Architecture tests: verify import boundaries for policy-service.

Ensures clean-architecture layering:
- Domain layer has zero infrastructure imports (no sqlalchemy, psycopg2, etc.)
- Application layer has zero infrastructure imports
- Application ports.py and bootstrap.py exist and contain no infra imports
- Infrastructure adapters implement their corresponding ports
"""

import ast
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # apps/policy-service
DOMAIN_DIR = SERVICE_ROOT / "src" / "domain"
APP_DIR = SERVICE_ROOT / "src" / "application"
INFRA_DIR = SERVICE_ROOT / "src" / "infrastructure"

# Packages that must never appear in domain or application layers
INFRA_PACKAGES = {
    "sqlalchemy", "psycopg2", "httpx", "fastapi", "uvicorn", "starlette",
    "bcrypt", "jwt",
}

# ── Helpers ──────────────────────────────────────────────────────


def _collect_python_files(directory: Path) -> list[Path]:
    """Return all .py files under *directory*, excluding __init__.py."""
    if not directory.exists():
        return []
    return [p for p in directory.rglob("*.py") if p.name != "__init__.py" and p.exists()]


def _extract_imports(filepath: Path) -> list[str]:
    """Extract top-level imported module names from a Python file via AST."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
            imports.append(node.module)
    return imports


def _extract_imports_raw(filepath: Path) -> list[str]:
    """Extract full dotted import paths (not split) from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


# ── Tests ────────────────────────────────────────────────────────


def test_domain_does_not_import_infrastructure():
    """Domain layer must not import sqlalchemy or any infrastructure package."""
    violations: list[str] = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            top = mod.split(".")[0]
            if top in INFRA_PACKAGES:
                violations.append(f"{pyfile.relative_to(SERVICE_ROOT)} imports {mod}")
    assert not violations, f"Domain imports infrastructure: {violations}"


def test_application_does_not_import_infrastructure_packages():
    """Application layer must not import sqlalchemy, httpx, etc."""
    violations: list[str] = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            top = mod.split(".")[0]
            if top in INFRA_PACKAGES:
                violations.append(f"{pyfile.relative_to(SERVICE_ROOT)} imports {mod}")
    assert not violations, f"Application imports infrastructure packages: {violations}"


def test_application_does_not_import_src_infrastructure():
    """Application layer must not import from src.infrastructure.*."""
    violations: list[str] = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports_raw(pyfile)
        for mod in imported:
            if mod.startswith("src.infrastructure"):
                violations.append(f"{pyfile.relative_to(SERVICE_ROOT)} imports {mod}")
    assert not violations, f"Application imports src.infrastructure: {violations}"


def test_ports_exist_and_clean():
    """Application ports.py must exist and contain no infrastructure imports."""
    ports_file = APP_DIR / "ports.py"
    assert ports_file.exists(), "application/ports.py not found"

    imported = _extract_imports(ports_file)
    infra_hits = [m for m in imported if m.split(".")[0] in INFRA_PACKAGES]
    assert not infra_hits, f"ports.py imports infrastructure: {infra_hits}"


def test_bootstrap_exists_and_clean():
    """Application bootstrap.py must exist and contain no infrastructure imports."""
    bootstrap_file = APP_DIR / "bootstrap.py"
    assert bootstrap_file.exists(), "application/bootstrap.py not found"

    imported = _extract_imports(bootstrap_file)
    infra_hits = [m for m in imported if m.split(".")[0] in INFRA_PACKAGES]
    assert not infra_hits, f"bootstrap.py imports infrastructure: {infra_hits}"


def test_policy_repository_adapter_implements_port():
    """PolicyRepository adapter in infrastructure must implement the port."""
    adapter_file = INFRA_DIR / "db" / "policy_repository.py"
    assert adapter_file.exists(), "infrastructure/db/policy_repository.py not found"

    source = adapter_file.read_text(encoding="utf-8")
    assert "PolicyRepository" in source, "Must reference PolicyRepository port"

    raw_imports = _extract_imports_raw(adapter_file)
    port_imported = any("application.ports" in m for m in raw_imports)
    assert port_imported, "Adapter must import from application.ports"
