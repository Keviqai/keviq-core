"""Architecture tests for PR16 hard gates.

G16-1: Runtime only owns AgentInvocation lifecycle (no task/run/step status writes)
G16-2: Model access only via ModelGatewayPort (no provider SDK, no provider credentials)
G16-3: Execution result is persisted truth
G16-4: Runtime lifecycle is observable (outbox events exist)
"""

import ast
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # apps/agent-runtime
DOMAIN_DIR = SERVICE_ROOT / "src" / "domain"
APP_DIR = SERVICE_ROOT / "src" / "application"
INFRA_DIR = SERVICE_ROOT / "src" / "infrastructure"

PROVIDER_PACKAGES = {"openai", "anthropic", "cohere", "together"}
INFRA_PACKAGES = {"sqlalchemy", "psycopg2", "httpx", "fastapi", "uvicorn", "starlette"}


def _collect_python_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*.py") if p.name != "__init__.py" and p.exists()]


def _extract_imports(filepath: Path) -> list[str]:
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


def _extract_full_imports(filepath: Path) -> list[str]:
    """Extract full import paths (not just top-level module)."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"))
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


# ── G16-1: Runtime does not own Task/Run/Step lifecycle ──────────

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


def test_domain_does_not_import_orchestrator():
    """agent-runtime domain must not import from orchestrator."""
    violations = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if "orchestrator" in mod.lower():
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Runtime domain imports orchestrator: {violations}"


# ── G16-2: Model access only via ModelGatewayPort ────────────────

def test_runtime_does_not_import_provider_sdk():
    """agent-runtime must not import any LLM provider SDK."""
    violations = []
    for layer_dir in (DOMAIN_DIR, APP_DIR, INFRA_DIR):
        for pyfile in _collect_python_files(layer_dir):
            imported = _extract_imports(pyfile)
            for mod in imported:
                if mod in PROVIDER_PACKAGES:
                    violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Runtime imports provider SDK: {violations}"


def test_runtime_does_not_import_model_gateway_infra():
    """agent-runtime must not import from model-gateway infrastructure."""
    violations = []
    for layer_dir in (DOMAIN_DIR, APP_DIR, INFRA_DIR):
        for pyfile in _collect_python_files(layer_dir):
            full_imports = _extract_full_imports(pyfile)
            for mod in full_imports:
                if "model_gateway" in mod.lower() and "infrastructure" in mod.lower():
                    violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Runtime imports model-gateway infra: {violations}"


def test_domain_does_not_import_infrastructure():
    """Domain layer must not import from infrastructure packages."""
    violations = []
    for pyfile in _collect_python_files(DOMAIN_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Domain imports infrastructure: {violations}"


def test_application_does_not_import_infrastructure_directly():
    """Application layer must not import sqlalchemy/httpx/fastapi directly."""
    app_packages = {"fastapi", "uvicorn", "starlette", "psycopg2", "sqlalchemy", "httpx"}
    violations = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in app_packages:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Application imports forbidden infra: {violations}"


# ── G16-3: Execution result is persisted truth ───────────────────

def test_repository_implementation_exists():
    """DbAgentInvocationRepository must exist and implement the port."""
    repo_file = INFRA_DIR / "db" / "invocation_repository.py"
    assert repo_file.exists(), "invocation_repository.py not found"

    source = repo_file.read_text(encoding="utf-8")
    assert "AgentInvocationRepository" in source, "Must implement AgentInvocationRepository"
    assert "class DbAgentInvocationRepository" in source, "Class must exist"
    assert "agent_invocations" in source, "Must target agent_invocations table"


def test_repository_uses_correct_schema():
    """Repository must use agent_runtime schema."""
    repo_file = INFRA_DIR / "db" / "invocation_repository.py"
    source = repo_file.read_text(encoding="utf-8")
    assert "agent_runtime" in source, "Must use agent_runtime schema"


# ── G16-4: Runtime lifecycle is observable ────────────────────────

def test_outbox_writer_exists():
    """OutboxWriter must exist and write to outbox table."""
    outbox_file = INFRA_DIR / "outbox" / "outbox_writer.py"
    assert outbox_file.exists(), "outbox_writer.py not found"

    source = outbox_file.read_text(encoding="utf-8")
    assert "outbox" in source.lower(), "Must reference outbox table"
    assert "INSERT INTO" in source, "Must perform INSERT"


def test_runtime_no_model_gateway_core_writes():
    """agent-runtime must not write to model_gateway_core schema."""
    violations = []
    for layer_dir in (DOMAIN_DIR, APP_DIR, INFRA_DIR):
        for pyfile in _collect_python_files(layer_dir):
            source = pyfile.read_text(encoding="utf-8", errors="ignore")
            if "model_gateway_core" in source:
                violations.append(f"{pyfile.name} references model_gateway_core")
    assert not violations, f"Runtime writes to model_gateway_core: {violations}"


# ── Contracts transport-agnostic ─────────────────────────────────

def test_execution_contracts_no_framework_imports():
    """execution_contracts.py must not import any framework package."""
    contracts_file = DOMAIN_DIR / "execution_contracts.py"
    assert contracts_file.exists()

    framework = {"fastapi", "httpx", "sqlalchemy", "uvicorn", "starlette", "pydantic"}
    imported = _extract_imports(contracts_file)
    framework_hits = [m for m in imported if m in framework]
    assert not framework_hits, f"Contracts import framework: {framework_hits}"
