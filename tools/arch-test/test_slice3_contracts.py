"""Architecture tests for Slice 3 contracts — 4 Hard Gates.

S3-G1: Orchestrator remains lifecycle authority.
       Only orchestrator/src/domain/ mutates task_status, run_status, step_status.
       agent-runtime, model-gateway, and all other services do NOT.
       (Extends PP1 + S2-G1 with Slice 3 services.)

S3-G2: Real execution is the production happy path.
       No simulated executor in production code path.
       Routes use run_real_execution; bootstrap configures real dispatcher.

S3-G3: Model-gateway is the only provider boundary.
       No direct provider SDK import outside model-gateway.
       No provider credentials (API keys) outside model-gateway.
       agent-runtime calls model-gateway via HTTP, not direct import.

S3-G4: Read surfaces remain correct.
       event-store is read-plane only (no orchestrator imports, no status writes).
       Query endpoints are GET-only.
       Query serialization exposes error/failure info for real execution.
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))

PROVIDER_PACKAGES = {'openai', 'anthropic', 'cohere', 'together', 'google'}
PROVIDER_CREDENTIAL_PATTERNS = [
    re.compile(r'OPENAI_API_KEY', re.IGNORECASE),
    re.compile(r'ANTHROPIC_API_KEY', re.IGNORECASE),
    re.compile(r'COHERE_API_KEY', re.IGNORECASE),
    re.compile(r'TOGETHER_API_KEY', re.IGNORECASE),
    re.compile(r'PROVIDER_API_KEY', re.IGNORECASE),
]


def _collect_python_files(directory: str) -> list[str]:
    """Walk directory and return all .py files (including __init__.py)."""
    if not os.path.isdir(directory):
        return []
    result = []
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith('.py'):
                result.append(os.path.join(dirpath, f))
    return result


def _extract_imports(filepath: str) -> list[str]:
    """Extract top-level module names from imports."""
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split('.')[0])
    return imports


def _extract_full_imports(filepath: str) -> list[str]:
    """Extract full import paths."""
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


# ===================================================================
# S3-G1: Orchestrator remains lifecycle authority
# ===================================================================

def test_s3g1_pp1_still_holds():
    """S3-G1: PP1 enforcement — no status mutation outside orchestrator/src/domain/.

    Re-invokes the PP1 scanner across all apps/ to ensure Slice 3 services
    (agent-runtime, model-gateway) don't violate lifecycle authority.
    """
    from test_pp1_state_transition_authority import _find_violations

    violations = _find_violations()
    assert violations == [], (
        "S3-G1 VIOLATION (PP1) — status mutation outside orchestrator/src/domain/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g1_agent_runtime_no_lifecycle_writes():
    """S3-G1: agent-runtime must not write to task_status, run_status, step_status."""
    from test_pp1_state_transition_authority import _scan_python_file

    runtime_src = os.path.join(APPS_ROOT, 'agent-runtime', 'src')
    violations = []
    for filepath in _collect_python_files(runtime_src):
        violations.extend(_scan_python_file(filepath))

    assert violations == [], (
        "S3-G1 VIOLATION — agent-runtime writes to lifecycle status fields:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g1_model_gateway_no_lifecycle_writes():
    """S3-G1: model-gateway must not write to task_status, run_status, step_status."""
    from test_pp1_state_transition_authority import _scan_python_file

    gateway_src = os.path.join(APPS_ROOT, 'model-gateway', 'src')
    violations = []
    for filepath in _collect_python_files(gateway_src):
        violations.extend(_scan_python_file(filepath))

    assert violations == [], (
        "S3-G1 VIOLATION — model-gateway writes to lifecycle status fields:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g1_transition_methods_only_in_orchestrator_domain():
    """S3-G1: Task/Run/Step transition tables exist only in orchestrator/src/domain/.

    Note: _transition methods for non-lifecycle entities (e.g. InvocationStatus
    in agent-runtime) are allowed — only TASK/RUN/STEP transition tables are scoped.
    """
    allowed_prefix = os.path.normpath(
        os.path.join(APPS_ROOT, 'orchestrator', 'src', 'domain'),
    )

    violations = []
    for dirpath, _, filenames in os.walk(APPS_ROOT):
        norm_dir = os.path.normpath(dirpath)
        if norm_dir.startswith(allowed_prefix):
            continue
        if 'tests' in norm_dir.split(os.sep):
            continue
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                source = f.read()

            # Only flag transition tables for TASK/RUN/STEP (PP1 scope)
            if re.search(r'_(?:TASK|RUN|STEP)_TRANSITIONS\s*[=:{]', source):
                violations.append(
                    f"{filepath}: defines lifecycle transition table"
                )

    assert violations == [], (
        "S3-G1 VIOLATION — lifecycle transition logic outside orchestrator/src/domain/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g1_execution_loop_calls_domain_transitions():
    """S3-G1: execution_loop.py must call domain transition methods for all lifecycle states."""
    loop_file = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application', 'execution_loop.py')
    assert os.path.exists(loop_file), "execution_loop.py not found"

    with open(loop_file, encoding='utf-8') as f:
        source = f.read()

    required_calls = [
        ('task.start()', 'Task pending->running'),
        ('task.complete()', 'Task running->completed'),
        ('task.fail()', 'Task running->failed'),
        ('run.complete()', 'Run running->completed'),
        ('run.fail(', 'Run running->failed'),
        ('run.time_out()', 'Run running->timed_out'),
        ('step.complete(', 'Step running->completed'),
        ('step.fail(', 'Step running->failed'),
    ]
    missing = []
    for call, desc in required_calls:
        if call not in source:
            missing.append(f"Missing {call} ({desc})")

    assert missing == [], (
        "S3-G1 VIOLATION — execution_loop missing domain transition calls:\n"
        + "\n".join(f"  {m}" for m in missing)
    )


# ===================================================================
# S3-G2: Real execution is the production happy path
# ===================================================================

def test_s3g2_routes_use_real_execution():
    """S3-G2: Production routes import run_real_execution, not run_simulated_execution."""
    routes_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py')
    assert os.path.exists(routes_path)

    with open(routes_path, encoding='utf-8') as f:
        source = f.read()

    assert 'run_real_execution' in source, (
        "S3-G2 VIOLATION — routes must use run_real_execution"
    )
    assert 'run_simulated_execution' not in source, (
        "S3-G2 VIOLATION — routes must NOT reference run_simulated_execution"
    )
    assert 'simulated_loop' not in source, (
        "S3-G2 VIOLATION — routes must NOT import from simulated_loop"
    )


def test_s3g2_routes_import_execution_loop():
    """S3-G2: Routes must import from execution_loop module."""
    routes_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py')
    full_imports = _extract_full_imports(routes_path)

    assert any('execution_loop' in m for m in full_imports), (
        "S3-G2 VIOLATION — routes must import from execution_loop"
    )
    assert not any('simulated_loop' in m for m in full_imports), (
        "S3-G2 VIOLATION — routes must NOT import from simulated_loop"
    )


def test_s3g2_bootstrap_configures_real_dispatcher():
    """S3-G2: Bootstrap must configure a real ExecutionDispatchPort (not simulated)."""
    bootstrap_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application', 'bootstrap.py')
    assert os.path.exists(bootstrap_path)

    with open(bootstrap_path, encoding='utf-8') as f:
        source = f.read()

    assert 'configure_dispatcher' in source, "Must define configure_dispatcher"
    assert 'get_dispatcher' in source, "Must define get_dispatcher"
    # Check imports, not raw text — comments mentioning "simulated" are fine
    bootstrap_imports = _extract_full_imports(bootstrap_path)
    assert not any('simulated' in m for m in bootstrap_imports), (
        "S3-G2 VIOLATION — bootstrap must not import simulated execution modules"
    )


def test_s3g2_main_wires_runtime_client():
    """S3-G2: main.py must wire HttpRuntimeClient as the dispatcher."""
    main_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'main.py')
    assert os.path.exists(main_path)

    with open(main_path, encoding='utf-8') as f:
        source = f.read()

    assert 'HttpRuntimeClient' in source, (
        "S3-G2 VIOLATION — main.py must instantiate HttpRuntimeClient"
    )
    assert 'configure_dispatcher' in source, (
        "S3-G2 VIOLATION — main.py must call configure_dispatcher"
    )
    assert 'AGENT_RUNTIME_URL' in source, (
        "S3-G2 VIOLATION — main.py must read AGENT_RUNTIME_URL"
    )


def test_s3g2_no_simulated_execution_in_production():
    """S3-G2: No production code (non-test) should IMPORT simulated execution.

    The simulated_loop.py module may still exist (Slice 2 legacy), but no other
    production module may import from it. Docstring/comment references are allowed.
    """
    violations = []
    prod_dirs = [
        os.path.join(APPS_ROOT, 'orchestrator', 'src'),
    ]
    for prod_dir in prod_dirs:
        for filepath in _collect_python_files(prod_dir):
            # Skip the simulated_loop module itself (legacy file)
            if os.path.basename(filepath) == 'simulated_loop.py':
                continue
            full_imports = _extract_full_imports(filepath)
            for mod in full_imports:
                if 'simulated_loop' in mod or 'run_simulated_execution' in mod:
                    violations.append(f"{filepath}: imports {mod}")

    assert violations == [], (
        "S3-G2 VIOLATION — simulated execution imported in production code:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ===================================================================
# S3-G3: Model-gateway is the only provider boundary
# ===================================================================

def test_s3g3_no_provider_sdk_outside_model_gateway():
    """S3-G3: No service outside model-gateway may import provider SDKs."""
    gateway_prefix = os.path.normpath(os.path.join(APPS_ROOT, 'model-gateway'))

    violations = []
    for dirpath, _, filenames in os.walk(APPS_ROOT):
        norm_dir = os.path.normpath(dirpath)
        if norm_dir.startswith(gateway_prefix):
            continue
        if 'tests' in norm_dir.split(os.sep):
            continue
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            imports = _extract_imports(filepath)
            for mod in imports:
                if mod in PROVIDER_PACKAGES:
                    violations.append(f"{filepath}: imports provider SDK '{mod}'")

    assert violations == [], (
        "S3-G3 VIOLATION — provider SDK import outside model-gateway:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g3_no_provider_credentials_outside_model_gateway():
    """S3-G3: No service outside model-gateway may reference provider API key env vars."""
    gateway_prefix = os.path.normpath(os.path.join(APPS_ROOT, 'model-gateway'))

    violations = []
    for dirpath, _, filenames in os.walk(APPS_ROOT):
        norm_dir = os.path.normpath(dirpath)
        if norm_dir.startswith(gateway_prefix):
            continue
        if 'tests' in norm_dir.split(os.sep):
            continue
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                source = f.read()
            for pattern in PROVIDER_CREDENTIAL_PATTERNS:
                if pattern.search(source):
                    violations.append(
                        f"{filepath}: references provider credential ({pattern.pattern})"
                    )

    assert violations == [], (
        "S3-G3 VIOLATION — provider credentials referenced outside model-gateway:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g3_agent_runtime_calls_gateway_via_http():
    """S3-G3: agent-runtime must access model-gateway via HTTP, not direct import."""
    runtime_src = os.path.join(APPS_ROOT, 'agent-runtime', 'src')
    violations = []

    for filepath in _collect_python_files(runtime_src):
        full_imports = _extract_full_imports(filepath)
        for mod in full_imports:
            # Must not import model-gateway internal modules
            if 'model_gateway' in mod.lower() and any(
                layer in mod.lower()
                for layer in ('infrastructure', 'domain', 'application', 'api')
            ):
                violations.append(
                    f"{filepath}: directly imports model-gateway module '{mod}'"
                )

    assert violations == [], (
        "S3-G3 VIOLATION — agent-runtime imports model-gateway internals:\n"
        + "\n".join(f"  {v}" for v in violations)
    )

    # Verify gateway_client.py exists and uses httpx
    client_file = os.path.join(runtime_src, 'infrastructure', 'gateway_client.py')
    assert os.path.exists(client_file), (
        "S3-G3 — agent-runtime must have infrastructure/gateway_client.py"
    )
    with open(client_file, encoding='utf-8') as f:
        source = f.read()
    assert 'httpx' in source, "gateway_client must use httpx for HTTP calls"


def test_s3g3_orchestrator_calls_runtime_via_http():
    """S3-G3: orchestrator must access agent-runtime via HTTP, not direct import."""
    orch_src = os.path.join(APPS_ROOT, 'orchestrator', 'src')
    violations = []

    for filepath in _collect_python_files(orch_src):
        full_imports = _extract_full_imports(filepath)
        for mod in full_imports:
            if 'agent_runtime' in mod.lower() and any(
                layer in mod.lower()
                for layer in ('infrastructure', 'domain', 'application', 'api')
            ):
                violations.append(
                    f"{filepath}: directly imports agent-runtime module '{mod}'"
                )

    assert violations == [], (
        "S3-G3 VIOLATION — orchestrator imports agent-runtime internals:\n"
        + "\n".join(f"  {v}" for v in violations)
    )

    # Positive verification: runtime_client.py must exist and use httpx
    client_file = os.path.join(orch_src, 'infrastructure', 'runtime_client.py')
    assert os.path.exists(client_file), (
        "S3-G3 — orchestrator must have infrastructure/runtime_client.py"
    )
    with open(client_file, encoding='utf-8') as f:
        source = f.read()
    assert 'httpx' in source, (
        "S3-G3 VIOLATION — runtime_client must use httpx for HTTP calls"
    )


def test_s3g3_model_gateway_is_sole_provider_adapter():
    """S3-G3: Only model-gateway/src/infrastructure/providers/ contains provider adapters."""
    gateway_providers = os.path.join(APPS_ROOT, 'model-gateway', 'src', 'infrastructure', 'providers')
    assert os.path.isdir(gateway_providers), (
        "model-gateway must have infrastructure/providers/ directory"
    )

    # Verify at least one provider adapter exists
    provider_files = _collect_python_files(gateway_providers)
    assert len(provider_files) > 0, (
        "model-gateway/src/infrastructure/providers/ must contain at least one provider adapter"
    )

    # Verify provider adapters implement ModelProviderPort
    has_provider_impl = False
    for filepath in provider_files:
        with open(filepath, encoding='utf-8') as f:
            source = f.read()
        if 'ModelProviderPort' in source:
            has_provider_impl = True
    assert has_provider_impl, (
        "At least one provider adapter must implement ModelProviderPort"
    )


# ===================================================================
# S3-G4: Read surfaces remain correct
# ===================================================================

def test_s3g4_event_store_no_orchestrator_imports():
    """S3-G4: event-store must never import from orchestrator."""
    event_store_src = os.path.join(APPS_ROOT, 'event-store', 'src')
    violations = []

    for filepath in _collect_python_files(event_store_src):
        try:
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read(), filename=filepath)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if 'orchestrator' in alias.name:
                            violations.append(f"{filepath}:{node.lineno} — imports {alias.name}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    if 'orchestrator' in node.module:
                        violations.append(f"{filepath}:{node.lineno} — imports from {node.module}")
        except SyntaxError:
            pass

    assert violations == [], (
        "S3-G4 VIOLATION — event-store imports from orchestrator:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g4_event_store_no_status_writes():
    """S3-G4: event-store must never write to status fields."""
    from test_pp1_state_transition_authority import _scan_python_file

    event_store_src = os.path.join(APPS_ROOT, 'event-store', 'src')
    violations = []
    for filepath in _collect_python_files(event_store_src):
        violations.extend(_scan_python_file(filepath))

    assert violations == [], (
        "S3-G4 VIOLATION — event-store writes to status fields:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g4_query_endpoints_are_get_only():
    """S3-G4: Orchestrator query endpoints must be GET-only."""
    routes_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py')
    with open(routes_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source, filename=routes_path)

    query_paths = {
        '/internal/v1/tasks/{task_id}',
        '/internal/v1/runs/{run_id}',
        '/internal/v1/runs/{run_id}/steps',
    }

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            method = dec.func.attr
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path = dec.args[0].value
            if path in query_paths and method != 'get':
                violations.append(
                    f"{routes_path}:{node.lineno} — "
                    f"query endpoint {path} uses {method.upper()}, expected GET"
                )

    assert violations == [], (
        "S3-G4 VIOLATION — query endpoints use non-GET methods:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s3g4_query_serialization_exposes_error_info():
    """S3-G4: Query helpers must expose error/failure information for real execution."""
    queries_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'application', 'queries.py')
    assert os.path.exists(queries_path)

    with open(queries_path, encoding='utf-8') as f:
        source = f.read()

    # run_to_dict must include error_summary
    assert 'error_summary' in source, (
        "S3-G4 VIOLATION — run_to_dict must expose error_summary"
    )
    # step_to_dict must include error_detail
    assert 'error_detail' in source, (
        "S3-G4 VIOLATION — step_to_dict must expose error_detail"
    )
    # step_to_dict must include output_snapshot
    assert 'output_snapshot' in source, (
        "S3-G4 VIOLATION — step_to_dict must expose output_snapshot"
    )


def test_s3g4_command_endpoints_return_202():
    """S3-G4: Command (POST) endpoints on orchestrator must return 202 Accepted."""
    from test_slice2_contracts import CommandEndpointVisitor

    routes_path = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py')
    assert os.path.exists(routes_path), f"Missing {routes_path}"
    with open(routes_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source, filename=routes_path)
    visitor = CommandEndpointVisitor(routes_path)
    visitor.visit(tree)

    assert visitor.violations == [], (
        "S3-G4 VIOLATION — command endpoints not returning 202:\n"
        + "\n".join(f"  {v}" for v in visitor.violations)
    )


# ===================================================================
# Self-tests: prove detection methods work
# ===================================================================

def test_s3g3_detector_catches_provider_import(tmp_path):
    """Self-test: detects provider SDK import in non-gateway service."""
    code = '''\
import openai

client = openai.Client()
'''
    test_file = tmp_path / "bad_service.py"
    test_file.write_text(code)

    imports = _extract_imports(str(test_file))
    provider_hits = [m for m in imports if m in PROVIDER_PACKAGES]
    assert len(provider_hits) == 1
    assert 'openai' in provider_hits


def test_s3g3_detector_passes_clean_service(tmp_path):
    """Self-test: clean service without provider imports passes."""
    code = '''\
import httpx
from uuid import UUID

def call_gateway():
    pass
'''
    test_file = tmp_path / "clean_service.py"
    test_file.write_text(code)

    imports = _extract_imports(str(test_file))
    provider_hits = [m for m in imports if m in PROVIDER_PACKAGES]
    assert len(provider_hits) == 0


def test_s3g3_detector_catches_credential_reference(tmp_path):
    """Self-test: detects provider credential env var reference."""
    code = '''\
import os
api_key = os.environ["OPENAI_API_KEY"]
'''
    test_file = tmp_path / "leaky_service.py"
    test_file.write_text(code)

    with open(str(test_file), encoding='utf-8') as f:
        source = f.read()

    hits = [p for p in PROVIDER_CREDENTIAL_PATTERNS if p.search(source)]
    assert len(hits) >= 1
