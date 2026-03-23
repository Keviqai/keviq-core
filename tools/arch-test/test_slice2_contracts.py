"""Architecture tests for Slice 2 contracts — 3 Hard Gates.

S2-G1: Only orchestrator/src/domain/ mutates task_status, run_status, step_status.
       (Extends PP1 — already tested in test_pp1_state_transition_authority.py.
        This test adds verification that the state machine transition methods
        exist ONLY in orchestrator domain objects.)

S2-G2: Command API endpoints return 202 Accepted, never final result.
       Verifies via AST that POST endpoints on orchestrator use HTTP_202_ACCEPTED.

S2-G3: Read-plane separation — query endpoints (GET) and event-store timeline
       endpoints never mutate status fields; event-store routes never write to
       orchestrator tables.
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))


# ═══════════════════════════════════════════════════════════════════
# S2-G1: Lifecycle Authority (supplement to PP1)
# ═══════════════════════════════════════════════════════════════════

def test_s2g1_transition_methods_only_in_orchestrator_domain():
    """S2-G1: Task/Run/Step transition tables and _transition methods that
    reference lifecycle status fields must only exist in orchestrator/src/domain/.

    Other services may define their own _transition methods for non-lifecycle
    entities (e.g. InvocationStatus in agent-runtime) — those are not flagged.
    """
    allowed_prefix = os.path.normpath(
        os.path.join(APPS_ROOT, 'orchestrator', 'src', 'domain'),
    )

    lifecycle_keywords = {'task_status', 'run_status', 'step_status',
                          'TaskStatus', 'RunStatus', 'StepStatus'}

    violations = []
    for dirpath, _, filenames in os.walk(APPS_ROOT):
        norm_dir = os.path.normpath(dirpath)
        if norm_dir.startswith(allowed_prefix):
            continue
        # Also allow test files (they import domain objects for testing)
        if 'tests' in norm_dir.split(os.sep):
            continue
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                source = f.read()
            # Check for transition table definitions (not mere imports of enum values)
            if re.search(r'_(?:TASK|RUN|STEP)_TRANSITIONS\s*[=:{]', source):
                violations.append(
                    f"{filepath}: defines lifecycle transition table"
                )
            # Check for _transition method definitions that reference lifecycle fields
            # (skip _transition methods for non-lifecycle entities like InvocationStatus)
            has_lifecycle_ref = any(kw in source for kw in lifecycle_keywords)
            if has_lifecycle_ref:
                try:
                    tree = ast.parse(source, filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name == '_transition':
                                violations.append(
                                    f"{filepath}:{node.lineno}: defines _transition method"
                                )
                except SyntaxError:
                    pass

    assert violations == [], (
        "S2-G1 VIOLATION — lifecycle transition logic outside orchestrator/src/domain/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s2g1_domain_objects_exist():
    """S2-G1: orchestrator/src/domain/ must define Task, Run, Step with state machines."""
    for module_name, class_name, status_enum in [
        ('task.py', 'Task', 'TaskStatus'),
        ('run.py', 'Run', 'RunStatus'),
        ('step.py', 'Step', 'StepStatus'),
    ]:
        filepath = os.path.join(APPS_ROOT, 'orchestrator', 'src', 'domain', module_name)
        assert os.path.exists(filepath), f"Missing {filepath}"

        with open(filepath, encoding='utf-8') as f:
            source = f.read()

        assert f'class {class_name}' in source, (
            f"{module_name} must define class {class_name}"
        )
        assert f'class {status_enum}' in source, (
            f"{module_name} must define enum {status_enum}"
        )
        assert '_transition' in source, (
            f"{module_name} must define _transition method for state machine"
        )


# ═══════════════════════════════════════════════════════════════════
# S2-G2: Command APIs return 202 Accepted
# ═══════════════════════════════════════════════════════════════════

class CommandEndpointVisitor(ast.NodeVisitor):
    """Find POST endpoint decorators and their status_code kwargs."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: list[str] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_endpoint(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_endpoint(node)
        self.generic_visit(node)

    def _check_endpoint(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            # router.post(...)
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != 'post':
                continue

            # Get the path argument (first positional arg)
            path = None
            if decorator.args:
                first = decorator.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    path = first.value

            if not path:
                continue

            # Skip internal ingest endpoints (event-store receives data, not commands)
            if '/ingest' in path:
                continue
            # Skip outbox relay trigger (internal maintenance)
            if '/outbox/' in path:
                continue

            # This is a command POST endpoint — check status_code
            status_code = None
            for kw in decorator.keywords:
                if kw.arg == 'status_code':
                    status_code = self._extract_status_code(kw.value)

            if status_code != 202:
                self.violations.append(
                    f"{self.filepath}:{node.lineno} — POST {path} "
                    f"has status_code={status_code}, expected 202"
                )

    def _extract_status_code(self, node: ast.AST) -> int | None:
        """Extract numeric status code from various AST forms."""
        # Direct integer: status_code=202
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        # status.HTTP_202_ACCEPTED → extract 202 via regex
        if isinstance(node, ast.Attribute):
            m = re.match(r'HTTP_(\d{3})_', node.attr)
            if m:
                return int(m.group(1))
        return None


def test_s2g2_command_endpoints_return_202():
    """S2-G2: All command (POST) endpoints on orchestrator must return 202 Accepted.

    Command endpoints create intent, not final results. The orchestrator
    acknowledges receipt and processing happens asynchronously.
    """
    routes_path = os.path.join(
        APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py',
    )
    assert os.path.exists(routes_path), f"Missing {routes_path}"

    with open(routes_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source, filename=routes_path)
    visitor = CommandEndpointVisitor(routes_path)
    visitor.visit(tree)

    assert visitor.violations == [], (
        "S2-G2 VIOLATION — command endpoints not returning 202:\n"
        + "\n".join(f"  {v}" for v in visitor.violations)
    )


def test_s2g2_command_responses_never_contain_final_state():
    """S2-G2: Orchestrator command endpoint responses must not include
    final entity state (task_status, run_status in response body).

    Command responses should be acknowledgements only: task_id + status: accepted.
    """
    routes_path = os.path.join(
        APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py',
    )

    with open(routes_path, encoding='utf-8') as f:
        source = f.read()

    tree = ast.parse(source, filename=routes_path)

    # Find all POST endpoint function bodies and check their return dicts
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        is_post = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == 'post':
                    path = ''
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        path = dec.args[0].value
                    # Skip non-command endpoints
                    if '/ingest' not in path and '/outbox/' not in path:
                        is_post = True

        if not is_post:
            continue

        # Walk the function body for return statements with dict literals
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                for key in child.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value in ('task_status', 'run_status', 'step_status'):
                            violations.append(
                                f"{routes_path}:{child.lineno} — "
                                f"command response contains '{key.value}'"
                            )

    assert violations == [], (
        "S2-G2 VIOLATION — command responses leak final state:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ═══════════════════════════════════════════════════════════════════
# S2-G3: Read-Plane Separation
# ═══════════════════════════════════════════════════════════════════

def test_s2g3_event_store_no_orchestrator_imports():
    """S2-G3: event-store service must never import from orchestrator.

    Event store is a read-plane service. It must not depend on orchestrator
    domain objects or infrastructure.
    """
    event_store_src = os.path.join(APPS_ROOT, 'event-store', 'src')
    violations = []

    for dirpath, _, filenames in os.walk(event_store_src):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                source = f.read()

            try:
                tree = ast.parse(source, filename=filepath)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if 'orchestrator' in alias.name:
                                violations.append(
                                    f"{filepath}:{node.lineno} — imports {alias.name}"
                                )
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if 'orchestrator' in node.module:
                            violations.append(
                                f"{filepath}:{node.lineno} — imports from {node.module}"
                            )
            except SyntaxError:
                pass

    assert violations == [], (
        "S2-G3 VIOLATION — event-store imports from orchestrator:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s2g3_event_store_no_status_writes():
    """S2-G3: event-store code must never write to status fields.

    Event store is append-only for events. It must not mutate
    task_status, run_status, or step_status.
    """
    from test_pp1_state_transition_authority import _scan_python_file

    event_store_src = os.path.join(APPS_ROOT, 'event-store', 'src')
    violations = []

    for dirpath, _, filenames in os.walk(event_store_src):
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            violations.extend(_scan_python_file(filepath))

    assert violations == [], (
        "S2-G3 VIOLATION — event-store writes to status fields:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s2g3_query_endpoints_are_get_only():
    """S2-G3: Orchestrator query endpoints (get_task, get_run, get_steps)
    must be GET methods only. They must not accept POST/PATCH/PUT.

    This ensures the read-plane is cleanly separated from the command-plane.
    """
    routes_path = os.path.join(
        APPS_ROOT, 'orchestrator', 'src', 'api', 'routes.py',
    )

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
            method = dec.func.attr  # get, post, patch, etc.
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path = dec.args[0].value

            if path in query_paths and method != 'get':
                violations.append(
                    f"{routes_path}:{node.lineno} — "
                    f"query endpoint {path} uses {method.upper()}, expected GET"
                )

    assert violations == [], (
        "S2-G3 VIOLATION — query endpoints use non-GET methods:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_s2g3_gateway_routes_event_store_correctly():
    """S2-G3: api-gateway must route timeline/SSE to event-store, not orchestrator.

    This verifies the read-plane (event-store) is correctly separated from
    the command-plane (orchestrator) at the gateway routing level.
    """
    routing_path = os.path.join(
        APPS_ROOT, 'api-gateway', 'src', 'api', 'routing.py',
    )

    with open(routing_path, encoding='utf-8') as f:
        source = f.read()

    # route_to_service must exist
    assert 'route_to_service' in source, (
        "api-gateway must define route_to_service for routing logic"
    )

    # Timeline paths must route to event-store
    assert "'event-store'" in source or '"event-store"' in source, (
        "api-gateway must route to 'event-store' service"
    )

    # Verify timeline routing to event-store (specific path patterns)
    assert '/timeline' in source, (
        "api-gateway must handle /timeline routes (event-store read-plane)"
    )

    # Verify SSE stream routing (specific path pattern)
    assert 'events/stream' in source or "events' and parts[5] == 'stream'" in source, (
        "api-gateway must handle events/stream routes (event-store read-plane)"
    )


# ═══════════════════════════════════════════════════════════════════
# Self-tests: prove detection methods work
# ═══════════════════════════════════════════════════════════════════

def test_s2g2_detector_catches_non_202_post(tmp_path):
    """Self-test: CommandEndpointVisitor catches POST endpoints without 202."""
    code = '''\
from fastapi import APIRouter, status
router = APIRouter()

@router.post("/internal/v1/things", status_code=status.HTTP_201_CREATED)
async def create_thing():
    return {"id": "123"}
'''
    test_file = tmp_path / "bad_routes.py"
    test_file.write_text(code)

    tree = ast.parse(code, filename=str(test_file))
    visitor = CommandEndpointVisitor(str(test_file))
    visitor.visit(tree)

    assert len(visitor.violations) == 1
    assert '201' in visitor.violations[0]


def test_s2g2_detector_passes_202_post(tmp_path):
    """Self-test: CommandEndpointVisitor passes POST endpoints with 202."""
    code = '''\
from fastapi import APIRouter, status
router = APIRouter()

@router.post("/internal/v1/things", status_code=status.HTTP_202_ACCEPTED)
async def create_thing():
    return {"status": "accepted"}
'''
    test_file = tmp_path / "good_routes.py"
    test_file.write_text(code)

    tree = ast.parse(code, filename=str(test_file))
    visitor = CommandEndpointVisitor(str(test_file))
    visitor.visit(tree)

    assert len(visitor.violations) == 0
