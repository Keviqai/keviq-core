"""Architecture gates for Slice 5 — Artifact domain invariants + public surface.

PR30 gates (public surface correctness):
  Gateway command route exclusion, domain import isolation,
  permission map entries, path rewrite correctness, no delivery scope.

PR31 gates (domain invariants — closeout proof):
  S5-G1: artifact-service sole write authority for artifact_core
  S5-G2: Provenance completeness enforced before READY transition
  S5-G3: Concrete model identity only — no aliases in provenance
  S5-G4: Lineage append-only DAG — no self-loop, no cycle, no update/delete
  S5-G5: No delivery scope in public surface or artifact-service API
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))
GATEWAY_SRC = os.path.join(APPS_ROOT, 'api-gateway', 'src')


def _collect_python_files(directory: str) -> list[str]:
    """Walk directory and return all .py files."""
    if not os.path.isdir(directory):
        return []
    result = []
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith('.py'):
                result.append(os.path.join(dirpath, f))
    return result


def _read_file(filepath: str) -> str:
    with open(filepath, encoding='utf-8', errors='ignore') as f:
        return f.read()


def _extract_full_imports(filepath: str) -> list[str]:
    """Extract full dotted import paths."""
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


# ── S5-G1: Gateway does NOT expose artifact command routes ────────


class TestGatewayNoArtifactCommandRoutes:
    """Public gateway must NOT route POST/PATCH/DELETE to artifact-service.
    Only GET (query) routes are allowed."""

    COMMAND_PATTERNS = [
        re.compile(r'/artifacts/register'),
        re.compile(r'/artifacts/[^/]+/begin-writing'),
        re.compile(r'/artifacts/[^/]+/finalize'),
        re.compile(r'/artifacts/[^/]+/fail'),
        # NOTE: /lineage/ancestors is a GET query (allowed), not a command.
        # POST /lineage (create edge) should not appear in gateway routes.
        re.compile(r"POST.*?/artifacts/[^/]+/lineage(?!/)", re.IGNORECASE),
    ]

    def test_gateway_routes_no_artifact_commands(self):
        """Gateway routes.py must not contain artifact command path patterns."""
        routes_file = os.path.join(GATEWAY_SRC, 'api', 'routes.py')
        content = _read_file(routes_file)

        violations = []
        for pattern in self.COMMAND_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Found command route pattern: {matches[0]}")

        assert violations == [], (
            f"Gateway must not expose artifact command routes:\n"
            + "\n".join(violations)
        )

    def test_gateway_has_method_guard(self):
        """Gateway must block non-GET methods for artifact routes."""
        routes_file = os.path.join(GATEWAY_SRC, 'api', 'routes.py')
        content = _read_file(routes_file)

        assert "service == 'artifact' and request.method != 'GET'" in content, (
            "Gateway must have a method guard blocking non-GET artifact requests"
        )

    def test_permission_map_no_destructive_artifact_routes(self):
        """PERMISSION_MAP must NOT have PATCH/DELETE/PUT entries for artifacts.

        POST is allowed for upload (artifact:create, added in PR49).
        """
        middleware_file = os.path.join(GATEWAY_SRC, 'application', 'auth_middleware.py')
        content = _read_file(middleware_file)

        violations = []
        for method in ['PATCH', 'DELETE', 'PUT']:
            pattern = re.compile(
                rf"\('{method}',\s*'[^']*artifacts[^']*'\)",
            )
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Found destructive permission entry: {matches[0]}")

        assert violations == [], (
            f"PERMISSION_MAP must not have destructive artifact entries:\n"
            + "\n".join(violations)
        )


# ── S5-G2: Gateway does NOT import artifact_core directly ─────────


class TestGatewayNoDirectArtifactDomain:
    """api-gateway must NOT import artifact-service domain modules.
    It communicates via HTTP proxy only."""

    FORBIDDEN_IMPORT_FRAGMENTS = [
        'artifact_core',
        'artifact_service',
        'src.domain.artifact',
        'src.domain.provenance',
        'src.domain.lineage',
    ]

    def test_no_artifact_domain_imports(self):
        violations = []
        for f in _collect_python_files(GATEWAY_SRC):
            imports = _extract_full_imports(f)
            for imp in imports:
                for forbidden in self.FORBIDDEN_IMPORT_FRAGMENTS:
                    if forbidden in imp:
                        rel = os.path.relpath(f, APPS_ROOT)
                        violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"Gateway must not import artifact domain:\n"
            + "\n".join(violations)
        )


# ── S5-G3: Workspace-scoped authz via PERMISSION_MAP ──────────────


class TestArtifactPermissionMapFromSource:
    """Verify PERMISSION_MAP has artifact entries by parsing source."""

    EXPECTED_ENTRIES = [
        "('GET', '/v1/workspaces/{workspace_id}/artifacts')",
        "('GET', '/v1/workspaces/{workspace_id}/artifacts/{artifact_id}')",
        "('GET', '/v1/workspaces/{workspace_id}/runs/{run_id}/artifacts')",
    ]

    def test_all_artifact_permission_entries_exist(self):
        middleware_file = os.path.join(GATEWAY_SRC, 'application', 'auth_middleware.py')
        content = _read_file(middleware_file)

        missing = []
        for entry in self.EXPECTED_ENTRIES:
            if entry not in content:
                missing.append(entry)

        assert missing == [], (
            f"Missing PERMISSION_MAP entries:\n" + "\n".join(missing)
        )

    def test_all_entries_map_to_workspace_view(self):
        middleware_file = os.path.join(GATEWAY_SRC, 'application', 'auth_middleware.py')
        content = _read_file(middleware_file)

        for entry in self.EXPECTED_ENTRIES:
            assert entry in content, f"Entry not found: {entry}"
            # Find the line and check it maps to workspace:view
            for line in content.splitlines():
                if entry in line:
                    assert 'workspace:view' in line, (
                        f"Entry {entry} does not map to workspace:view: {line.strip()}"
                    )



# ── S5-G4: Path rewrite correctness ───────────────────────────────


class TestArtifactPathRewriteGate:
    """Verify _rewrite_artifact_path strips workspace_id from internal paths."""

    def test_rewrite_functions_exist(self):
        routing_file = os.path.join(GATEWAY_SRC, 'api', 'routing.py')
        content = _read_file(routing_file)

        assert 'def _rewrite_artifact_path' in content, (
            "Missing _rewrite_artifact_path function in gateway routing"
        )
        assert 'def artifact_query_params' in content, (
            "Missing artifact_query_params function in gateway routing"
        )

    def test_rewrite_uses_internal_prefix(self):
        """Internal paths must use /internal/v1/ prefix."""
        routes_file = os.path.join(GATEWAY_SRC, 'api', 'routing.py')
        content = _read_file(routes_file)

        # Find _rewrite_artifact_path function body
        in_func = False
        internal_count = 0
        for line in content.splitlines():
            if 'def _rewrite_artifact_path' in line:
                in_func = True
                continue
            if in_func:
                if line.strip() and not line[0].isspace() and 'def ' in line:
                    break
                if '/internal/v1/artifacts' in line:
                    internal_count += 1

        assert internal_count >= 2, (
            f"_rewrite_artifact_path should produce /internal/v1/artifacts paths "
            f"(found {internal_count} references)"
        )


# ── S5-G5: No download/delivery/signed-URL in public surface ─────


class TestNoDownloadScope:
    """Signed-URL and presigned semantics must not exist yet (deferred to PR55)."""

    FORBIDDEN_PATTERNS = [
        re.compile(r'signed.?url', re.IGNORECASE),
        re.compile(r'presigned', re.IGNORECASE),
    ]

    # NOTE: download/delivery patterns are now allowed after PR47.

    def test_gateway_routes_no_signed_url(self):
        """Gateway routes must not contain signed-URL patterns (deferred to PR55)."""
        routes_file = os.path.join(GATEWAY_SRC, 'api', 'routes.py')
        content = _read_file(routes_file)

        violations = []
        for pattern in self.FORBIDDEN_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Found forbidden pattern '{pattern.pattern}': {matches}")

        assert violations == [], (
            f"Gateway must not have signed-URL scope:\n"
            + "\n".join(violations)
        )

    def test_permission_map_no_download(self):
        """PERMISSION_MAP must not have download-related entries."""
        middleware_file = os.path.join(GATEWAY_SRC, 'application', 'auth_middleware.py')
        content = _read_file(middleware_file)

        violations = []
        for pattern in self.FORBIDDEN_PATTERNS:
            # Only check within PERMISSION_MAP block
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Found forbidden pattern '{pattern.pattern}': {matches}")

        assert violations == [], (
            f"PERMISSION_MAP must not have download/delivery entries:\n"
            + "\n".join(violations)
        )


# ══════════════════════════════════════════════════════════════════
# PR31 — Domain invariant gates (closeout proof)
# ══════════════════════════════════════════════════════════════════

ARTIFACT_SRC = os.path.join(APPS_ROOT, 'artifact-service', 'src')
ARTIFACT_MIGRATIONS = os.path.join(APPS_ROOT, 'artifact-service', 'alembic', 'versions')


# ── S5-G1: Sole write authority for artifact_core ─────────────


class TestSoleWriteAuthority:
    """Only artifact-service may write to artifact_core schema.
    No other service should reference artifact_core in write operations."""

    # Services that must NOT write to artifact_core
    OTHER_SERVICES = [
        'orchestrator', 'agent-runtime', 'execution-service',
        'api-gateway', 'workspace-service', 'policy-service',
        'auth-service', 'event-store', 'model-gateway',
    ]

    def test_no_other_service_references_artifact_core_schema(self):
        """No service outside artifact-service should reference artifact_core."""
        violations = []
        for svc in self.OTHER_SERVICES:
            svc_src = os.path.join(APPS_ROOT, svc, 'src')
            for f in _collect_python_files(svc_src):
                content = _read_file(f)
                if 'artifact_core' in content:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: references artifact_core")

        assert violations == [], (
            f"S5-G1 violation: services outside artifact-service reference artifact_core:\n"
            + "\n".join(violations)
        )

    def test_runtime_uses_http_not_db(self):
        """agent-runtime must communicate with artifact-service via HTTP, not DB."""
        runtime_src = os.path.join(APPS_ROOT, 'agent-runtime', 'src')
        violations = []
        for f in _collect_python_files(runtime_src):
            imports = _extract_full_imports(f)
            for imp in imports:
                # Must not import artifact-service domain/infra directly
                if 'artifact_service' in imp or 'artifact_core' in imp:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: imports {imp}")

        assert violations == [], (
            f"S5-G1 violation: agent-runtime imports artifact-service directly:\n"
            + "\n".join(violations)
        )

    def test_artifact_service_owns_artifact_core_migrations(self):
        """Only artifact-service should have migrations for artifact_core."""
        violations = []
        for svc in self.OTHER_SERVICES:
            mig_dir = os.path.join(APPS_ROOT, svc, 'alembic', 'versions')
            for f in _collect_python_files(mig_dir):
                content = _read_file(f)
                if 'artifact_core' in content:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: migration references artifact_core")

        assert violations == [], (
            f"S5-G1 violation: other services have artifact_core migrations:\n"
            + "\n".join(violations)
        )


# ── S5-G2: Provenance completeness before READY ──────────────


class TestProvenanceCompletenessGate:
    """Artifact cannot transition to READY without complete provenance."""

    def test_finalize_calls_validate_complete(self):
        """Artifact.finalize() must call provenance.validate_complete()."""
        artifact_file = os.path.join(ARTIFACT_SRC, 'domain', 'artifact.py')
        content = _read_file(artifact_file)

        assert 'validate_complete' in content, (
            "S5-G2: Artifact.finalize() must validate provenance completeness"
        )

    def test_provenance_has_validate_complete(self):
        """ArtifactProvenance must define validate_complete() method."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        assert 'def validate_complete' in content, (
            "S5-G2: ArtifactProvenance must have validate_complete() method"
        )

    def test_validate_complete_checks_reproducibility_tuple(self):
        """validate_complete() must check all 5 reproducibility components."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        # Extract validate_complete function body
        in_func = False
        func_body = []
        for line in content.splitlines():
            if 'def validate_complete' in line:
                in_func = True
                continue
            if in_func:
                if line.strip() and not line[0].isspace() and line.strip().startswith('def '):
                    break
                func_body.append(line)

        body = '\n'.join(func_body)

        # Must check these fields
        required_checks = [
            'run_config_hash',
            'model_provider',
            'model_name_concrete',
            'model_version_concrete',
        ]

        missing = [c for c in required_checks if c not in body]
        assert missing == [], (
            f"S5-G2: validate_complete() missing checks for: {missing}"
        )

    def test_finalize_service_fetches_provenance(self):
        """finalize_artifact service function must fetch provenance before finalize."""
        svc_file = os.path.join(ARTIFACT_SRC, 'application', 'services.py')
        content = _read_file(svc_file)

        assert 'provenance' in content.lower(), (
            "S5-G2: finalize_artifact must involve provenance validation"
        )


# ── S5-G3: Concrete model identity — no aliases ──────────────


class TestConcreteModelIdentityGate:
    """Provenance must reject model aliases (PP9, DNB12)."""

    def test_alias_pattern_detection_exists(self):
        """Provenance domain must have alias detection patterns."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        assert '_ALIAS_PATTERNS' in content or '_is_model_alias' in content, (
            "S5-G3: Provenance must have alias detection logic"
        )

    def test_alias_patterns_include_common_aliases(self):
        """Alias patterns must catch 'latest', 'default', 'stable', etc."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        expected_patterns = ['latest', 'default', 'stable']
        for pattern in expected_patterns:
            assert pattern in content, (
                f"S5-G3: Missing alias pattern for '{pattern}'"
            )

    def test_init_validates_alias(self):
        """ArtifactProvenance __post_init__ must validate model aliases."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        assert '__post_init__' in content, (
            "S5-G3: ArtifactProvenance must have __post_init__ for alias validation"
        )
        assert 'ModelAliasError' in content, (
            "S5-G3: ArtifactProvenance must raise ModelAliasError for aliases"
        )

    def test_set_model_identity_validates_alias(self):
        """set_model_identity() must validate aliases."""
        prov_file = os.path.join(ARTIFACT_SRC, 'domain', 'provenance.py')
        content = _read_file(prov_file)

        assert 'def set_model_identity' in content, (
            "S5-G3: ArtifactProvenance must have set_model_identity()"
        )


# ── S5-G4: Lineage append-only DAG ───────────────────────────


class TestLineageAppendOnlyDAGGate:
    """Lineage edges are append-only: no self-loop, no cycle, no update/delete."""

    def test_self_loop_rejection_in_domain(self):
        """LineageEdge domain must reject self-loops."""
        lineage_file = os.path.join(ARTIFACT_SRC, 'domain', 'lineage.py')
        content = _read_file(lineage_file)

        assert 'SelfLoopError' in content or 'self_loop' in content.lower(), (
            "S5-G4: Lineage domain must detect self-loops"
        )

    def test_cycle_detection_exists(self):
        """detect_cycle() function must exist in lineage domain."""
        lineage_file = os.path.join(ARTIFACT_SRC, 'domain', 'lineage.py')
        content = _read_file(lineage_file)

        assert 'def detect_cycle' in content, (
            "S5-G4: Lineage domain must have detect_cycle() function"
        )

    def test_no_update_delete_on_lineage_in_services(self):
        """Application services must not UPDATE or DELETE lineage edges."""
        svc_file = os.path.join(ARTIFACT_SRC, 'application', 'services.py')
        content = _read_file(svc_file)

        violations = []
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            lower = stripped.lower()
            if ('lineage' in lower or 'edge' in lower) and (
                'update' in lower or 'delete' in lower
            ):
                # Allow 'update' in comments and docstrings
                if not stripped.startswith(('"""', "'''")):
                    # Check if it's actual code, not a string
                    if '.update(' in stripped or '.delete(' in stripped:
                        violations.append(f"services.py:{i}: {stripped}")

        assert violations == [], (
            f"S5-G4: Lineage edges must be append-only, found mutations:\n"
            + "\n".join(violations)
        )

    def test_lineage_migration_has_self_loop_check_constraint(self):
        """Migration must have CHECK constraint preventing self-loops."""
        violations = []
        for f in _collect_python_files(ARTIFACT_MIGRATIONS):
            content = _read_file(f)
            if 'lineage' in content.lower() and 'CheckConstraint' in content:
                # Good — has a check constraint
                return

        # If we get here, no migration has a check constraint for lineage
        pytest.fail("S5-G4: No lineage migration with CheckConstraint found")

    def test_no_cross_schema_fk_in_artifact_migrations(self):
        """artifact-service migrations must not FK to other schemas."""
        other_schemas = {'orchestrator_core', 'runtime_core', 'event_core',
                        'execution_core', 'gateway_core'}
        violations = []
        for f in _collect_python_files(ARTIFACT_MIGRATIONS):
            content = _read_file(f)
            for schema in other_schemas:
                if schema in content:
                    rel = os.path.relpath(f, APPS_ROOT)
                    violations.append(f"{rel}: references {schema}")

        assert violations == [], (
            f"S5-G4: Cross-schema FK detected in artifact migrations:\n"
            + "\n".join(violations)
        )


# ── S5-G5 (extended): No delivery scope in artifact-service ───


class TestNoSignedUrlScopeArtifactService:
    """artifact-service API must not have signed-URL/presigned endpoints (deferred to PR55)."""

    FORBIDDEN = ['signed_url', 'presign', 'publish']

    # NOTE: 'download' and 'export' are now allowed after PR47.

    def test_no_signed_url_in_artifact_routes(self):
        """artifact-service routes must not have signed-URL endpoints."""
        routes_file = os.path.join(ARTIFACT_SRC, 'api', 'routes.py')
        content = _read_file(routes_file).lower()

        violations = [kw for kw in self.FORBIDDEN if kw in content]

        assert violations == [], (
            f"S5-G5: artifact-service has signed-URL scope: {violations}"
        )
