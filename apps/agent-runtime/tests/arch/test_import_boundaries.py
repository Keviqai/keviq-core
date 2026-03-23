"""Architecture tests: verify import boundaries for agent-runtime.

PR14 Gates:
- G14-1: AgentInvocation lifecycle is domain-owned (transitions via methods)
- G14-2: Execution contracts are transport-agnostic
- G14-3: Agent Runtime does not own Task/Run/Step lifecycle
"""

import ast
from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # apps/agent-runtime
DOMAIN_DIR = SERVICE_ROOT / "src" / "domain"
APP_DIR = SERVICE_ROOT / "src" / "application"

INFRA_PACKAGES = {"sqlalchemy", "psycopg2", "httpx", "fastapi", "uvicorn", "starlette"}
FRAMEWORK_PACKAGES = {"fastapi", "httpx", "sqlalchemy", "uvicorn", "starlette", "pydantic"}


def _collect_python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.name != "__init__.py" and p.exists()]


def _extract_imports(filepath: Path) -> list[str]:
    """Extract all imported module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    return imports


def _find_enclosing_function(tree: ast.AST, lineno: int) -> str:
    """Find the function name that contains the given line number."""
    enclosing = "<module>"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                enclosing = node.name
    return enclosing


# ── G14-1: Domain layer does not import infrastructure ───────────

def test_domain_does_not_import_infrastructure():
    """Domain layer must not import from infrastructure packages."""
    violations = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Domain imports infrastructure: {violations}"


def test_application_does_not_import_infrastructure():
    """Application layer must not import from infrastructure packages."""
    violations = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Application imports infrastructure: {violations}"


# ── G14-2: Execution contracts are transport-agnostic ────────────

def test_execution_contracts_no_framework_imports():
    """execution_contracts.py must not import any framework/transport package."""
    contracts_file = DOMAIN_DIR / "execution_contracts.py"
    assert contracts_file.exists(), "execution_contracts.py not found"

    imported = _extract_imports(contracts_file)
    framework_hits = [m for m in imported if m in FRAMEWORK_PACKAGES]
    assert not framework_hits, f"Contracts import framework packages: {framework_hits}"


def test_execution_contracts_no_forbidden_fields():
    """ExecutionRequest/Result/Failure must not contain task_status/run_status/step_status."""
    contracts_file = DOMAIN_DIR / "execution_contracts.py"
    source = contracts_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden = {"task_status", "run_status", "step_status"}
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in (
            "ExecutionRequest", "ExecutionResult", "ExecutionFailure",
        ):
            for item in ast.walk(node):
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if item.target.id in forbidden:
                        violations.append(f"{node.name}.{item.target.id}")

    assert not violations, f"Forbidden fields in contracts: {violations}"


# ── G14-3: Agent Runtime does not own Task/Run/Step lifecycle ────

def test_runtime_domain_no_orchestrator_imports():
    """agent-runtime domain must not import from orchestrator domain."""
    violations = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if "orchestrator" in mod.lower():
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Runtime domain imports orchestrator: {violations}"


def test_runtime_no_task_run_step_status_writes():
    """agent-runtime must not write to task_status, run_status, or step_status."""
    forbidden_patterns = {"task_status", "run_status", "step_status"}
    violations = []

    for layer_dir in (DOMAIN_DIR, APP_DIR):
        for pyfile in _collect_python_files(layer_dir):
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr in forbidden_patterns:
                            violations.append(f"{pyfile.name}:{node.lineno} assigns {target.attr}")
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg in forbidden_patterns:
                            violations.append(f"{pyfile.name}:{node.lineno} passes {kw.arg}")
    assert not violations, f"Runtime writes to forbidden status fields: {violations}"


# ── G14-1: AgentInvocation transitions are method-only ───────────

def test_invocation_status_only_set_via_transition():
    """invocation_status must only be assigned in __init__ and _transition methods."""
    invocation_file = DOMAIN_DIR / "agent_invocation.py"
    assert invocation_file.exists(), "agent_invocation.py not found"

    source = invocation_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "AgentInvocation":
            for item in ast.walk(node):
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and target.attr == "invocation_status"
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            func_name = _find_enclosing_function(tree, item.lineno)
                            if func_name not in ("__init__", "_transition"):
                                violations.append(f"line {item.lineno} in {func_name}")

    assert not violations, (
        f"invocation_status assigned outside __init__/_transition: {violations}"
    )
