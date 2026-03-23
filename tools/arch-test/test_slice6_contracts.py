"""Architecture gates for Slice 6 — Frontend Application Shell.

6 gate categories proving S6-G1 through S6-G6:

  1. State boundary discipline — server-state, live-state, ui-state isolation
  2. Capability-aware rendering — no role→capability derivation on client
  3. No delivery scope — no download/export/import UI
  4. Internal surface isolation — browser never calls internal APIs
  5. SSE truth discipline — SSE only appends timeline + invalidates queries
  6. Route model follows domain — no debug/admin/agent-panel routes
"""

import os
import re

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
WEB_SRC = os.path.join(ROOT, 'apps', 'web', 'src')
PACKAGES = os.path.join(ROOT, 'packages')
SERVER_STATE_SRC = os.path.join(PACKAGES, 'server-state', 'src')
LIVE_STATE_SRC = os.path.join(PACKAGES, 'live-state', 'src')
UI_STATE_SRC = os.path.join(PACKAGES, 'ui-state', 'src')
PERMISSIONS_SRC = os.path.join(PACKAGES, 'permissions', 'src')
ROUTING_SRC = os.path.join(PACKAGES, 'routing', 'src')


def _collect_ts_files(directory: str) -> list[str]:
    """Walk directory and return all .ts/.tsx files."""
    if not os.path.isdir(directory):
        return []
    result = []
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith(('.ts', '.tsx')):
                result.append(os.path.join(dirpath, f))
    return result


def _read_file(filepath: str) -> str:
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════
# Gate 1: State Boundary Discipline (S6-G1, S6-G2)
# ══════════════════════════════════════════════════════════════════


class TestStateBoundaryDiscipline:
    """server-state, live-state, and ui-state must not cross-import."""

    def test_server_state_does_not_import_live_state(self):
        """server-state must not import from live-state."""
        violations = []
        for f in _collect_ts_files(SERVER_STATE_SRC):
            content = _read_file(f)
            if '@keviq/live-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G1: server-state must not import live-state:\n"
            + "\n".join(violations)
        )

    def test_server_state_does_not_import_ui_state(self):
        """server-state must not import from ui-state."""
        violations = []
        for f in _collect_ts_files(SERVER_STATE_SRC):
            content = _read_file(f)
            if '@keviq/ui-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G1: server-state must not import ui-state:\n"
            + "\n".join(violations)
        )

    def test_live_state_does_not_import_server_state(self):
        """live-state must not import from server-state."""
        violations = []
        for f in _collect_ts_files(LIVE_STATE_SRC):
            content = _read_file(f)
            if '@keviq/server-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G2: live-state must not import server-state:\n"
            + "\n".join(violations)
        )

    def test_live_state_does_not_import_ui_state(self):
        """live-state must not import from ui-state."""
        violations = []
        for f in _collect_ts_files(LIVE_STATE_SRC):
            content = _read_file(f)
            if '@keviq/ui-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G2: live-state must not import ui-state:\n"
            + "\n".join(violations)
        )

    def test_ui_state_does_not_import_server_state(self):
        """ui-state must not import from server-state."""
        violations = []
        for f in _collect_ts_files(UI_STATE_SRC):
            content = _read_file(f)
            if '@keviq/server-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G1: ui-state must not import server-state:\n"
            + "\n".join(violations)
        )

    def test_ui_state_does_not_import_live_state(self):
        """ui-state must not import from live-state."""
        violations = []
        for f in _collect_ts_files(UI_STATE_SRC):
            content = _read_file(f)
            if '@keviq/live-state' in content:
                rel = os.path.relpath(f, ROOT)
                violations.append(rel)

        assert violations == [], (
            "S6-G1: ui-state must not import live-state:\n"
            + "\n".join(violations)
        )


# ══════════════════════════════════════════════════════════════════
# Gate 2: Capability-Aware Rendering (S6-G3)
# ══════════════════════════════════════════════════════════════════


class TestCapabilityAwareRendering:
    """UI must render based on _capabilities, never derive from role strings."""

    ROLE_DERIVATION_PATTERNS = [
        re.compile(r'role\s*===?\s*[\'"]admin[\'"]', re.IGNORECASE),
        re.compile(r'role\s*===?\s*[\'"]owner[\'"]', re.IGNORECASE),
        re.compile(r'role\s*===?\s*[\'"]member[\'"]', re.IGNORECASE),
        re.compile(r'role\s*===?\s*[\'"]viewer[\'"]', re.IGNORECASE),
        re.compile(r'isAdmin\b', re.IGNORECASE),
        re.compile(r'isOwner\b', re.IGNORECASE),
        re.compile(r'user\.role\b'),
        re.compile(r'currentRole\b'),
    ]

    def test_no_role_derivation_in_web_pages(self):
        """Web app pages must not derive capabilities from role strings."""
        pages_dir = os.path.join(WEB_SRC, 'app')
        violations = []
        for f in _collect_ts_files(pages_dir):
            content = _read_file(f)
            for pattern in self.ROLE_DERIVATION_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}: {matches[0]}")

        assert violations == [], (
            "S6-G3: Pages must not derive capabilities from role strings:\n"
            + "\n".join(violations)
        )

    def test_no_role_derivation_in_shared_modules(self):
        """Shared modules must not derive capabilities from role strings."""
        shared_dir = os.path.join(WEB_SRC, 'modules', 'shared')
        violations = []
        for f in _collect_ts_files(shared_dir):
            content = _read_file(f)
            for pattern in self.ROLE_DERIVATION_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}: {matches[0]}")

        assert violations == [], (
            "S6-G3: Shared modules must not derive capabilities from roles:\n"
            + "\n".join(violations)
        )

    def test_capability_check_uses_hasCapability(self):
        """Pages that check capabilities must use hasCapability(), not direct property access."""
        pages_dir = os.path.join(WEB_SRC, 'app')
        violations = []
        # Pattern for direct capability access like: task._capabilities.can_cancel
        direct_access = re.compile(r'\._capabilities\.\w+')

        for f in _collect_ts_files(pages_dir):
            content = _read_file(f)
            if '_capabilities' not in content:
                continue
            matches = direct_access.findall(content)
            if matches:
                rel = os.path.relpath(f, ROOT)
                violations.append(f"{rel}: direct access {matches[0]}")

        assert violations == [], (
            "S6-G3: Must use hasCapability() helper, not direct property access:\n"
            + "\n".join(violations)
        )

    def test_permissions_package_has_no_role_mapping(self):
        """permissions package must not contain role→capability mapping tables."""
        violations = []
        role_map_patterns = [
            re.compile(r'ROLE_CAPABILITIES'),
            re.compile(r'roleToCapabilities'),
            re.compile(r'role.*Map.*capability', re.IGNORECASE),
        ]
        for f in _collect_ts_files(PERMISSIONS_SRC):
            content = _read_file(f)
            for pattern in role_map_patterns:
                matches = pattern.findall(content)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}: {matches[0]}")

        assert violations == [], (
            "S6-G3: permissions package must not have role→capability maps:\n"
            + "\n".join(violations)
        )


# ══════════════════════════════════════════════════════════════════
# Gate 3: No Delivery Scope (S6-G4)
# ══════════════════════════════════════════════════════════════════


class TestNoDeliveryScope:
    """Frontend must not have signed-url/public-share UI.

    Upload allowed since PR49.
    In-app content export (ExportActions, CSV, .md/.txt/.json download) allowed since Q3-S4.
    Still forbidden: signed URLs, presigned URLs, public share flows.
    """

    FORBIDDEN_PATTERNS = [
        re.compile(r'\bsigned.?url\b', re.IGNORECASE),
        re.compile(r'\bpresigned\b', re.IGNORECASE),
        # 'export' allowed since Q3-S4 (in-app content export, not public delivery)
        # 'import' is a JS/TS keyword — too broad to forbid here
    ]

    # Whitelist: import statements, ES module imports, dynamic imports
    IMPORT_LINE = re.compile(r'^\s*(import|export)\s')
    DYNAMIC_IMPORT = re.compile(r'\bimport\s*\(')

    def _is_import_line(self, line: str) -> bool:
        """Check if a line is an ES import/export statement or dynamic import."""
        return bool(self.IMPORT_LINE.match(line)) or bool(self.DYNAMIC_IMPORT.search(line))

    def test_artifact_pages_no_delivery_ui(self):
        """Artifact pages must not contain export/signed-url/presigned UI elements."""
        artifact_pages = os.path.join(
            WEB_SRC, 'app', '(shell)', 'workspaces', '[workspaceId]', 'artifacts'
        )
        violations = []
        for f in _collect_ts_files(artifact_pages):
            content = _read_file(f)
            for i, line in enumerate(content.splitlines(), 1):
                # Skip import/export statements
                if self._is_import_line(line):
                    continue
                # Skip comments
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                    continue
                for pattern in self.FORBIDDEN_PATTERNS:
                    matches = pattern.findall(line)
                    if matches:
                        rel = os.path.relpath(f, ROOT)
                        violations.append(f"{rel}:{i}: '{matches[0]}'")

        assert violations == [], (
            "S6-G4: Artifact pages must not have delivery scope UI:\n"
            + "\n".join(violations)
        )

    def test_no_upload_export_button_in_artifact_detail(self):
        """Artifact detail page must not render upload or public-share buttons.

        Note: in-app content export (ArtifactExportActions, .md/.txt/.json download)
        is allowed since Q3-S4. Public signed URLs and presigned URLs remain forbidden.
        """
        detail_page = os.path.join(
            WEB_SRC, 'app', '(shell)', 'workspaces', '[workspaceId]',
            'artifacts', '[artifactId]', 'page.tsx',
        )
        if not os.path.exists(detail_page):
            pytest.skip("Artifact detail page not found")

        content = _read_file(detail_page)

        # Upload and Save-As are out of scope for artifact detail.
        # Export (in-app content download) allowed since Q3-S4.
        delivery_buttons = [
            re.compile(r'Save\s+As', re.IGNORECASE),
        ]
        violations = []
        for pattern in delivery_buttons:
            for i, line in enumerate(content.splitlines(), 1):
                if self._is_import_line(line):
                    continue
                if pattern.search(line):
                    violations.append(f"line {i}: {line.strip()[:80]}")

        assert violations == [], (
            "S6-G4: Artifact detail must not have upload/save-as buttons:\n"
            + "\n".join(violations)
        )


# ══════════════════════════════════════════════════════════════════
# Gate 4: Internal Surface Isolation (S6-G6)
# ══════════════════════════════════════════════════════════════════


class TestInternalSurfaceIsolation:
    """Browser code must only use gateway/SSE endpoints, never internal APIs."""

    INTERNAL_URL_PATTERNS = [
        re.compile(r'/internal/v1/'),
        re.compile(r'localhost:80(?:0[1-9]|1[0-5])'),  # internal service ports
        re.compile(r'artifact-service'),
        re.compile(r'orchestrator.*:\d+'),
        re.compile(r'execution-service'),
        re.compile(r'event-store'),
    ]

    def test_web_src_no_internal_urls(self):
        """Web app source must not contain internal service URLs."""
        violations = []
        for f in _collect_ts_files(WEB_SRC):
            content = _read_file(f)
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                    continue
                for pattern in self.INTERNAL_URL_PATTERNS:
                    matches = pattern.findall(line)
                    if matches:
                        rel = os.path.relpath(f, ROOT)
                        violations.append(f"{rel}:{i}: {matches[0]}")

        assert violations == [], (
            "S6-G6: Web app must not call internal APIs directly:\n"
            + "\n".join(violations)
        )

    def test_api_client_no_internal_prefix(self):
        """api-client package must not hard-code internal API prefixes."""
        api_client_src = os.path.join(PACKAGES, 'api-client', 'src')
        violations = []
        internal_prefix = re.compile(r'/internal/v1/')

        for f in _collect_ts_files(api_client_src):
            content = _read_file(f)
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith('//'):
                    continue
                matches = internal_prefix.findall(line)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}:{i}: {matches[0]}")

        assert violations == [], (
            "S6-G6: api-client must not use /internal/v1/ prefix:\n"
            + "\n".join(violations)
        )

    def test_routing_package_no_internal_paths(self):
        """routing package must only build public URL paths."""
        violations = []
        internal_prefix = re.compile(r'/internal/')

        for f in _collect_ts_files(ROUTING_SRC):
            content = _read_file(f)
            for i, line in enumerate(content.splitlines(), 1):
                matches = internal_prefix.findall(line)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}:{i}: {matches[0]}")

        assert violations == [], (
            "S6-G6: routing package must not reference /internal/ paths:\n"
            + "\n".join(violations)
        )


# ══════════════════════════════════════════════════════════════════
# Gate 5: SSE Truth Discipline (S6-G1, S6-G2)
# ══════════════════════════════════════════════════════════════════


class TestSSETruthDiscipline:
    """SSE layer must only append to timeline and invalidate queries.
    It must never set query data directly or own truth."""

    def test_live_state_does_not_set_query_data(self):
        """live-state package must not call setQueryData or setQueriesData."""
        violations = []
        set_data_pattern = re.compile(r'set(?:Query|Queries)Data')

        for f in _collect_ts_files(LIVE_STATE_SRC):
            content = _read_file(f)
            matches = set_data_pattern.findall(content)
            if matches:
                rel = os.path.relpath(f, ROOT)
                violations.append(f"{rel}: {matches}")

        assert violations == [], (
            "S6-G2: live-state must not call setQueryData:\n"
            + "\n".join(violations)
        )

    def test_event_invalidation_uses_invalidate_not_set(self):
        """use-event-invalidation must call invalidateQueries, not setQueryData."""
        hook_file = os.path.join(WEB_SRC, 'modules', 'shared', 'use-event-invalidation.ts')
        if not os.path.exists(hook_file):
            pytest.skip("use-event-invalidation.ts not found")

        content = _read_file(hook_file)

        # Must use invalidateQueries
        assert 'invalidateQueries' in content, (
            "S6-G2: useEventInvalidation must call invalidateQueries"
        )

        # Must NOT use setQueryData
        assert 'setQueryData' not in content, (
            "S6-G2: useEventInvalidation must not call setQueryData"
        )

    def test_sse_hook_does_not_own_entity_state(self):
        """useEventStream must not store entity state (tasks, runs, etc.)."""
        hook_file = os.path.join(LIVE_STATE_SRC, 'use-event-stream.ts')
        if not os.path.exists(hook_file):
            pytest.skip("use-event-stream.ts not found")

        content = _read_file(hook_file)

        # Must not use useState for entity data
        entity_state_patterns = [
            re.compile(r'useState<.*Task'),
            re.compile(r'useState<.*Run'),
            re.compile(r'useState<.*Step'),
            re.compile(r'useState<.*Artifact'),
        ]
        violations = []
        for pattern in entity_state_patterns:
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Found entity state: {matches[0]}")

        assert violations == [], (
            "S6-G2: useEventStream must not store entity state:\n"
            + "\n".join(violations)
        )

    def test_sse_uses_named_event_listeners_only(self):
        """useEventStream must use addEventListener, not onmessage for data events."""
        hook_file = os.path.join(LIVE_STATE_SRC, 'use-event-stream.ts')
        if not os.path.exists(hook_file):
            pytest.skip("use-event-stream.ts not found")

        content = _read_file(hook_file)

        # Must use addEventListener
        assert 'addEventListener' in content, (
            "S6-G2: useEventStream must use named addEventListener"
        )

        # Check that onmessage is not used as a data handler
        # (onmessage = handler is forbidden; es.onmessage is forbidden for data)
        onmessage_handler = re.compile(r'\.onmessage\s*=\s*(?!null)')
        matches = onmessage_handler.findall(content)
        assert matches == [], (
            "S6-G2: useEventStream must not use onmessage for data (causes duplicate dispatch):\n"
            + str(matches)
        )


# ══════════════════════════════════════════════════════════════════
# Gate 6: Route Model Follows Domain (S6-G5)
# ══════════════════════════════════════════════════════════════════


class TestRouteModelFollowsDomain:
    """Routes must follow domain model: /workspaces/:wid/tasks/:tid etc.
    No debug, admin, or agent-panel routes."""

    FORBIDDEN_ROUTES = [
        re.compile(r'/debug'),
        re.compile(r'/agent-panel'),
        re.compile(r'/admin'),
        re.compile(r'/internal'),
    ]

    def test_routing_package_domain_aligned(self):
        """routing package path builders must follow workspace-scoped pattern."""
        violations = []
        for f in _collect_ts_files(ROUTING_SRC):
            content = _read_file(f)
            for pattern in self.FORBIDDEN_ROUTES:
                matches = pattern.findall(content)
                if matches:
                    rel = os.path.relpath(f, ROOT)
                    violations.append(f"{rel}: forbidden route {matches[0]}")

        assert violations == [], (
            "S6-G5: Routes must follow domain model, no debug/admin:\n"
            + "\n".join(violations)
        )

    def test_no_forbidden_page_directories(self):
        """App router must not have debug/admin/agent-panel directories."""
        app_dir = os.path.join(WEB_SRC, 'app')
        forbidden_dirs = ['debug', 'admin', 'agent-panel', 'internal']
        violations = []
        for dirpath, dirnames, _ in os.walk(app_dir):
            for d in dirnames:
                if d in forbidden_dirs:
                    rel = os.path.relpath(os.path.join(dirpath, d), ROOT)
                    violations.append(rel)

        assert violations == [], (
            "S6-G5: App must not have forbidden route directories:\n"
            + "\n".join(violations)
        )
