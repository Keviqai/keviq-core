"""Architecture tests for PR17 hard gates.

G17-1: Orchestrator remains state authority — only orchestrator mutates
       task/run/step status. Agent-runtime does NOT.
G17-2: Simulated execution is no longer the main path — production routes
       use run_real_execution, not run_simulated_execution.
G17-3: Real execution is visible through existing read surfaces —
       query module exposes task/run/step data including failure info.

Additional: no direct provider call outside model-gateway,
            no cross-schema FK, no simulated executor in production path.
"""

import ast
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # apps/orchestrator
DOMAIN_DIR = SERVICE_ROOT / "src" / "domain"
APP_DIR = SERVICE_ROOT / "src" / "application"
INFRA_DIR = SERVICE_ROOT / "src" / "infrastructure"
API_DIR = SERVICE_ROOT / "src" / "api"

PROVIDER_PACKAGES = {"openai", "anthropic", "cohere", "together"}
INFRA_PACKAGES = {"sqlalchemy", "psycopg2", "httpx", "fastapi", "uvicorn", "starlette"}


def _collect_python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
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


# ── G17-1: Orchestrator remains state authority ─────────────────

def test_orchestrator_owns_task_run_step_status():
    """execution_loop.py must mutate task/run/step status via domain methods."""
    loop_file = APP_DIR / "execution_loop.py"
    assert loop_file.exists(), "execution_loop.py not found"

    source = loop_file.read_text(encoding="utf-8")
    # Must call domain transition methods
    assert "task.start()" in source, "Must call task.start()"
    assert "task.complete()" in source, "Must call task.complete()"
    assert "task.fail()" in source, "Must call task.fail()"
    assert "run.complete()" in source, "Must call run.complete()"
    assert "run.fail(" in source, "Must call run.fail()"
    assert "run.time_out()" in source, "Must call run.time_out()"
    assert "step.complete(" in source, "Must call step.complete()"
    assert "step.fail(" in source, "Must call step.fail()"


def test_execution_loop_does_not_import_agent_runtime():
    """Orchestrator execution loop must not import from agent-runtime domain."""
    violations = []
    for pyfile in _collect_python_files(APP_DIR):
        full_imports = _extract_full_imports(pyfile)
        for mod in full_imports:
            if "agent_runtime" in mod.lower() and "domain" in mod.lower():
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Orchestrator app layer imports agent-runtime domain: {violations}"


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
    violations = []
    for pyfile in _collect_python_files(APP_DIR):
        imported = _extract_imports(pyfile)
        for mod in imported:
            if mod in INFRA_PACKAGES:
                violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Application imports forbidden infra: {violations}"


# ── G17-2: Simulated execution no longer main path ─────────────

def test_production_routes_use_real_execution():
    """API routes must import run_real_execution, not run_simulated_execution."""
    routes_file = API_DIR / "routes.py"
    assert routes_file.exists(), "routes.py not found"

    source = routes_file.read_text(encoding="utf-8")
    assert "run_real_execution" in source, "Routes must use run_real_execution"
    assert "run_simulated_execution" not in source, "Routes must NOT use run_simulated_execution"


def test_routes_import_execution_loop_not_simulated():
    """Routes must import from execution_loop, not simulated_loop."""
    routes_file = API_DIR / "routes.py"
    full_imports = _extract_full_imports(routes_file)
    assert any("execution_loop" in m for m in full_imports), \
        "Routes must import from execution_loop"
    assert not any("simulated_loop" in m for m in full_imports), \
        "Routes must NOT import from simulated_loop"


def test_bootstrap_configures_dispatcher():
    """Bootstrap must expose configure_dispatcher and get_dispatcher."""
    bootstrap_file = APP_DIR / "bootstrap.py"
    assert bootstrap_file.exists(), "bootstrap.py not found"

    source = bootstrap_file.read_text(encoding="utf-8")
    assert "configure_dispatcher" in source, "Must define configure_dispatcher"
    assert "get_dispatcher" in source, "Must define get_dispatcher"


# ── G17-3: Real execution visible through read surfaces ────────

def test_query_module_exposes_task_run_step():
    """Query module must expose task/run/step read functions."""
    queries_file = APP_DIR / "queries.py"
    assert queries_file.exists(), "queries.py not found"

    source = queries_file.read_text(encoding="utf-8")
    assert "get_task_with_latest_run" in source, "Must expose task query"
    assert "get_run" in source, "Must expose run query"
    assert "get_run_steps" in source, "Must expose steps query"


def test_query_surfaces_include_error_info():
    """Query serialization must include error/failure fields for visibility."""
    queries_file = APP_DIR / "queries.py"
    source = queries_file.read_text(encoding="utf-8")
    # Run dict must include error_summary
    assert "error_summary" in source, "run_to_dict must expose error_summary"


# ── Additional: no provider SDK, no cross-schema FK ────────────

def test_orchestrator_does_not_import_provider_sdk():
    """Orchestrator must not import any LLM provider SDK directly."""
    violations = []
    for layer_dir in (DOMAIN_DIR, APP_DIR, INFRA_DIR):
        for pyfile in _collect_python_files(layer_dir):
            imported = _extract_imports(pyfile)
            for mod in imported:
                if mod in PROVIDER_PACKAGES:
                    violations.append(f"{pyfile.name} imports {mod}")
    assert not violations, f"Orchestrator imports provider SDK: {violations}"


def test_orchestrator_does_not_reference_agent_runtime_schema():
    """Orchestrator infra must not reference agent_runtime schema (S1 isolation)."""
    violations = []
    for pyfile in _collect_python_files(INFRA_DIR):
        source = pyfile.read_text(encoding="utf-8", errors="ignore")
        if "agent_runtime" in source and "schema" in source.lower():
            violations.append(f"{pyfile.name} references agent_runtime schema")
    assert not violations, f"Orchestrator references agent_runtime schema: {violations}"


def test_runtime_client_uses_http_not_direct_import():
    """HttpRuntimeClient must use HTTP (httpx), not direct import of agent-runtime code."""
    client_file = INFRA_DIR / "runtime_client.py"
    assert client_file.exists(), "runtime_client.py not found"

    source = client_file.read_text(encoding="utf-8")
    assert "httpx" in source, "Must use httpx for HTTP calls"

    full_imports = _extract_full_imports(client_file)
    for mod in full_imports:
        assert "agent_runtime" not in mod.lower(), \
            f"runtime_client must NOT import agent-runtime code: {mod}"


# ── Events: failure/timeout events exist ────────────────────────

def test_failure_timeout_events_defined():
    """Event factories must include failure and timeout event helpers."""
    events_file = APP_DIR / "events.py"
    assert events_file.exists(), "events.py not found"

    source = events_file.read_text(encoding="utf-8")
    assert "task_failed_event" in source, "Must define task_failed_event"
    assert "run_failed_event" in source, "Must define run_failed_event"
    assert "run_timed_out_event" in source, "Must define run_timed_out_event"
    assert "step_failed_event" in source, "Must define step_failed_event"


def test_outbox_events_emitted_in_execution_loop():
    """Execution loop must emit outbox events for all lifecycle transitions."""
    loop_file = APP_DIR / "execution_loop.py"
    source = loop_file.read_text(encoding="utf-8")

    required_events = [
        "task_started_event",
        "run_queued_event",
        "run_started_event",
        "step_started_event",
        "step_completed_event",
        "step_failed_event",
        "run_completing_event",
        "run_completed_event",
        "run_failed_event",
        "run_timed_out_event",
        "task_completed_event",
        "task_failed_event",
    ]
    for evt in required_events:
        assert evt in source, f"execution_loop must use {evt}"
