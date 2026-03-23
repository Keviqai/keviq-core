"""Architecture test: verify import boundaries for execution-service."""

import ast
import os

DOMAIN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '../../src/domain')
)
APP_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '../../src/application')
)

FRAMEWORK_MODULES = {'fastapi', 'sqlalchemy', 'docker', 'httpx', 'pydantic'}


def _collect_python_files(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    result = []
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith('.py'):
                result.append(os.path.join(dirpath, f))
    return result


def _extract_full_imports(filepath: str) -> list[str]:
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


def test_domain_does_not_import_infrastructure():
    """Domain layer must not import from infrastructure or application."""
    violations = []
    for f in _collect_python_files(DOMAIN_DIR):
        imports = _extract_full_imports(f)
        for imp in imports:
            if 'infrastructure' in imp or 'application' in imp:
                rel = os.path.relpath(f, DOMAIN_DIR)
                violations.append(f"{rel}: imports {imp}")
    assert violations == [], "\n".join(violations)


def test_domain_no_framework_imports():
    """Domain layer must be framework-free."""
    violations = []
    for f in _collect_python_files(DOMAIN_DIR):
        imports = _extract_full_imports(f)
        for imp in imports:
            top = imp.split('.')[0]
            if top in FRAMEWORK_MODULES:
                rel = os.path.relpath(f, DOMAIN_DIR)
                violations.append(f"{rel}: imports {top}")
    assert violations == [], "\n".join(violations)


def test_application_does_not_import_infrastructure():
    """Application layer must not import infrastructure directly."""
    violations = []
    for f in _collect_python_files(APP_DIR):
        imports = _extract_full_imports(f)
        for imp in imports:
            if 'infrastructure' in imp:
                rel = os.path.relpath(f, APP_DIR)
                violations.append(f"{rel}: imports {imp}")
    assert violations == [], "\n".join(violations)
