"""PP1: Only orchestrator/src/domain/ may mutate lifecycle status fields.

Detection methods:
  1. AST: Direct attribute assignments (task.task_status = ...)
  2. AST: Dict-style writes (obj['task_status'] = ...)
  3. AST: ORM .update() / .filter().update() with status field in kwargs
  4. Regex: SQL strings containing UPDATE...SET...*_status (single + multiline)

Known limitations (documented, not claimed):
  - Cannot detect status mutations via fully dynamic key construction
    (e.g., setattr(obj, field_name, value) where field_name is a variable)
  - Cannot detect mutations through external libraries that wrap attribute access
  - Multiline SQL detection relies on string content within a single Python string
    literal, not across separate string concatenations

Only orchestrator/src/domain/ is allowed to perform these mutations.
"""

import ast
import os
import re
import pytest

# Fields that represent lifecycle state (PP1 scope)
STATUS_FIELDS = {'task_status', 'run_status', 'step_status'}

# SQL patterns that indicate status mutation (applied to full file content)
SQL_STATUS_PATTERNS = [
    # Multiline-capable: UPDATE...SET...*_status across lines within a string
    re.compile(
        r"""(['\"]{3}|['\"]).*(UPDATE\b.*?\bSET\b.*?\b(?:task_status|run_status|step_status)\b)""",
        re.IGNORECASE | re.DOTALL,
    ),
]

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))

# This path is the ONLY allowed location for status mutations
ALLOWED_PREFIX = os.path.normpath(os.path.join(APPS_ROOT, 'orchestrator', 'src', 'domain'))


class StatusMutationVisitor(ast.NodeVisitor):
    """AST visitor that detects status field mutations."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: list[str] = []

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._check_target(target, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        self._check_target(node.target, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.target and node.value:
            self._check_target(node.target, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detect ORM-style .update(task_status=...) calls."""
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'update':
            for kw in node.keywords:
                if kw.arg in STATUS_FIELDS:
                    self.violations.append(
                        f"{self.filepath}:{node.lineno} — "
                        f"ORM .update() with status field: {kw.arg}="
                    )
        self.generic_visit(node)

    def _check_target(self, target: ast.AST, lineno: int):
        # obj.task_status = ...
        if isinstance(target, ast.Attribute) and target.attr in STATUS_FIELDS:
            self.violations.append(
                f"{self.filepath}:{lineno} — attribute write: .{target.attr} ="
            )
        # obj['task_status'] = ...
        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant):
            if target.slice.value in STATUS_FIELDS:
                self.violations.append(
                    f"{self.filepath}:{lineno} — subscript write: ['{target.slice.value}'] ="
                )


def _scan_python_file(filepath: str) -> list[str]:
    """Scan a single Python file for status mutations using AST + regex."""
    violations = []

    with open(filepath, encoding='utf-8', errors='ignore') as f:
        source = f.read()

    # AST-based detection (attribute writes, subscript writes, ORM .update())
    try:
        tree = ast.parse(source, filename=filepath)
        visitor = StatusMutationVisitor(filepath)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    except SyntaxError:
        pass  # Skip files that can't be parsed

    # Regex-based detection for SQL strings (including multiline)
    # Extract all string literals from AST to check their content
    try:
        tree = ast.parse(source, filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                if re.search(
                    r'UPDATE\b.*?\bSET\b.*?\b(?:task_status|run_status|step_status)\b',
                    val,
                    re.IGNORECASE | re.DOTALL,
                ):
                    snippet = val.strip().replace('\n', ' ')[:80]
                    violations.append(
                        f"{filepath}:{node.lineno} — SQL status mutation: {snippet}"
                    )
    except SyntaxError:
        pass

    return violations


def _find_violations() -> list[str]:
    """Walk all apps/ Python files except orchestrator/src/domain/."""
    violations = []
    for dirpath, _, filenames in os.walk(APPS_ROOT):
        norm_dir = os.path.normpath(dirpath)
        # Skip the allowed path
        if norm_dir.startswith(ALLOWED_PREFIX):
            continue
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, filename)
            violations.extend(_scan_python_file(filepath))
    return violations


# ── Main enforcement test ────────────────────────────────────


def test_no_status_mutation_outside_orchestrator_domain():
    """PP1: No service may mutate lifecycle status outside orchestrator/src/domain/."""
    violations = _find_violations()
    assert violations == [], (
        "PP1 VIOLATION — status mutation outside orchestrator/src/domain/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ── Self-tests: prove each detection method works ────────────


def test_pp1_detects_attribute_write():
    """Self-test: catches obj.task_status = ..."""
    code = "task.task_status = 'completed'"
    tree = ast.parse(code)
    visitor = StatusMutationVisitor("test.py")
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "task_status" in visitor.violations[0]


def test_pp1_detects_subscript_write():
    """Self-test: catches obj['run_status'] = ..."""
    code = "data['run_status'] = 'failed'"
    tree = ast.parse(code)
    visitor = StatusMutationVisitor("test.py")
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "run_status" in visitor.violations[0]


def test_pp1_detects_orm_update():
    """Self-test: catches query.update(task_status='completed')."""
    code = "session.query(Task).filter_by(id=task_id).update(task_status='completed')"
    tree = ast.parse(code)
    visitor = StatusMutationVisitor("test.py")
    visitor.visit(tree)
    assert len(visitor.violations) == 1
    assert "task_status" in visitor.violations[0]


def test_pp1_detects_multiline_sql(tmp_path):
    """Self-test: catches multiline SQL UPDATE via the real _scan_python_file."""
    code = '''\
sql = """
    UPDATE tasks
    SET task_status = 'completed',
        updated_at = NOW()
    WHERE id = %s
"""
'''
    test_file = tmp_path / "fake_service.py"
    test_file.write_text(code)
    violations = _scan_python_file(str(test_file))
    assert len(violations) >= 1, "Failed to detect multiline SQL UPDATE with task_status"
    assert any("task_status" in v for v in violations)


def test_pp1_ignores_reads():
    """Self-test: reads should NOT trigger violations."""
    code = """
x = task.task_status
if run_status == 'active':
    pass
print(step_status)
result = session.query(Task).filter_by(task_status='completed').all()
"""
    tree = ast.parse(code)
    visitor = StatusMutationVisitor("test.py")
    visitor.visit(tree)
    assert len(visitor.violations) == 0
