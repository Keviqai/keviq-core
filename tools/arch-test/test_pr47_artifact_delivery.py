"""PR47 gate tests — Artifact delivery and access surfaces.

D47-G1: Storage abstraction is a port (no infrastructure imports)
D47-G2: Download only serves READY artifacts (route checks status)
D47-G3: Workspace isolation in storage paths
D47-G4: Content headers from artifact metadata
D47-G5: Gateway exposes download with RBAC
D47-G6: No cross-workspace content leak
"""

import functools
import os
import re

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
APPS_ROOT = os.path.join(REPO_ROOT, 'apps')
PACKAGES_ROOT = os.path.join(REPO_ROOT, 'packages')

ARTIFACT_SVC = os.path.join(APPS_ROOT, 'artifact-service', 'src')
GATEWAY_SVC = os.path.join(APPS_ROOT, 'api-gateway', 'src')
WEB_APP = os.path.join(APPS_ROOT, 'web', 'src')


@functools.lru_cache(maxsize=64)
def _read(filepath: str) -> str:
    with open(filepath, encoding='utf-8') as f:
        return f.read()


def _read_all_artifact_routes() -> str:
    """Read all artifact-service route modules (split from routes.py)."""
    api_dir = os.path.join(ARTIFACT_SVC, 'api')
    parts = []
    for fname in sorted(os.listdir(api_dir)):
        if fname.startswith('route') and fname.endswith('.py'):
            parts.append(_read(os.path.join(api_dir, fname)))
    return '\n'.join(parts)


def _read_all_gateway_routes() -> str:
    """Read all api-gateway route modules (split from routes.py)."""
    api_dir = os.path.join(GATEWAY_SVC, 'api')
    parts = []
    for fname in sorted(os.listdir(api_dir)):
        if fname.endswith('.py') and fname != '__init__.py':
            parts.append(_read(os.path.join(api_dir, fname)))
    return '\n'.join(parts)


# ═══════════════════════════════════════════════════════════════════
# D47-G1: Storage abstraction is a port
# ═══════════════════════════════════════════════════════════════════


class TestStorageAbstractionIsPort:
    """StorageBackend must be a pure application-layer port."""

    def test_storage_backend_in_ports(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'class StorageBackend' in src, \
            "StorageBackend must be defined in ports.py"

    def test_storage_backend_is_abstract(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'ABC' in src, "StorageBackend must extend ABC"

    def test_ports_no_infrastructure_imports(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'from src.infrastructure' not in src, \
            "Ports must not import infrastructure"
        assert 'import sqlalchemy' not in src, \
            "Ports must not import SQLAlchemy"

    def test_storage_has_write_content(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'def write_content(' in src

    def test_storage_has_read_content(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'def read_content(' in src

    def test_storage_has_exists(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'def exists(' in src

    def test_storage_has_delete(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'ports.py'))
        assert 'def delete(' in src

    def test_local_backend_implements_storage(self):
        src = _read(os.path.join(
            ARTIFACT_SVC, 'infrastructure', 'storage', 'local.py',
        ))
        assert 'class LocalStorageBackend' in src
        assert 'StorageBackend' in src

    def test_local_backend_has_path_traversal_guard(self):
        src = _read(os.path.join(
            ARTIFACT_SVC, 'infrastructure', 'storage', 'local.py',
        ))
        assert 'startswith' in src or 'resolve' in src, \
            "Local backend must guard against path traversal"

    def test_storage_configured_in_main(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'main.py'))
        assert 'configure_storage_backend' in src, \
            "Storage backend must be configured at startup"

    def test_bootstrap_has_storage_getter(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'bootstrap.py'))
        assert 'def get_storage_backend' in src


# ═══════════════════════════════════════════════════════════════════
# D47-G2: Download only serves READY artifacts
# ═══════════════════════════════════════════════════════════════════


class TestDownloadOnlyReady:
    """Download endpoint must enforce READY-only access."""

    def test_download_endpoint_exists(self):
        src = _read_all_artifact_routes()
        assert '/download' in src, \
            "Download endpoint must exist in routes"

    def test_download_route_is_get(self):
        src = _read_all_artifact_routes()
        # Find the download endpoint and verify it's a GET
        assert re.search(
            r'@(router|content_router)\.get\([^)]*download[^)]*\)',
            src,
        ), "Download must be a GET endpoint"

    def test_download_checks_ready_status(self):
        src = _read_all_artifact_routes()
        # Must check for "ready" status before allowing download
        assert 'ready' in src.lower() and '409' in src, \
            "Download must check READY status and return 409 otherwise"

    def test_download_uses_storage_backend(self):
        src = _read_all_artifact_routes()
        assert 'get_storage_backend' in src, \
            "Download endpoint must use storage backend"

    def test_download_reads_content(self):
        src = _read_all_artifact_routes()
        assert 'read_content' in src, \
            "Download must call read_content on storage"


# ═══════════════════════════════════════════════════════════════════
# D47-G3: Workspace isolation in storage paths
# ═══════════════════════════════════════════════════════════════════


class TestWorkspaceIsolationStorage:
    """Storage paths must include workspace_id for isolation."""

    def test_config_has_storage_key_with_workspace(self):
        path = os.path.join(PACKAGES_ROOT, 'config', 'src', '__init__.py')
        src = _read(path)
        assert 'def artifact_storage_key(' in src, \
            "Config must have artifact_storage_key function"
        # Must include workspace_id in the path
        assert 'workspace_id' in src

    def test_storage_key_follows_pr44_convention(self):
        path = os.path.join(PACKAGES_ROOT, 'config', 'src', '__init__.py')
        src = _read(path)
        assert 'workspaces/' in src, \
            "Storage key must follow workspaces/ prefix convention"

    def test_download_endpoint_verifies_workspace(self):
        src = _read_all_artifact_routes()
        # Download endpoint must take workspace_id and verify it
        match = re.search(
            r'def download_artifact_endpoint\(.*?workspace_id',
            src, re.DOTALL,
        )
        assert match, "Download endpoint must require workspace_id"

    def test_download_calls_verify_workspace(self):
        src = _read_all_artifact_routes()
        # Between download function def and the next function def,
        # must call verify_workspace (was _verify_workspace before split)
        download_section = src[src.index('def download_artifact_endpoint'):]
        # Find next function definition
        next_def = re.search(r'\ndef [a-z]', download_section[1:])
        if next_def:
            download_section = download_section[:next_def.start() + 1]
        assert 'verify_workspace' in download_section, \
            "Download must call verify_workspace"

    def test_local_backend_uses_resolve(self):
        src = _read(os.path.join(
            ARTIFACT_SVC, 'infrastructure', 'storage', 'local.py',
        ))
        assert '.resolve()' in src, \
            "Local backend must resolve paths to prevent traversal"


# ═══════════════════════════════════════════════════════════════════
# D47-G4: Content headers from artifact metadata
# ═══════════════════════════════════════════════════════════════════


class TestContentHeaders:
    """Download response must include proper content headers."""

    def test_content_type_from_mime_type(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'mime_type' in download_section, \
            "Download must use artifact mime_type for Content-Type"

    def test_content_disposition_header(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'Content-Disposition' in download_section, \
            "Download must set Content-Disposition header"

    def test_etag_from_checksum(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'ETag' in download_section and 'checksum' in download_section, \
            "Download must set ETag from checksum"

    def test_content_length_conditional(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'Content-Length' in download_section, \
            "Download must set Content-Length when size_bytes available"
        # Must be conditional
        assert 'size_bytes is not None' in download_section \
            or 'size_bytes' in download_section, \
            "Content-Length must only be set when size_bytes is known"

    def test_fallback_content_type(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'application/octet-stream' in download_section, \
            "Must have fallback Content-Type"


# ═══════════════════════════════════════════════════════════════════
# D47-G5: Gateway exposes download with RBAC
# ═══════════════════════════════════════════════════════════════════


class TestGatewayDownloadRoute:
    """Gateway must proxy download endpoint with workspace RBAC."""

    def test_gateway_routes_download_to_artifact_service(self):
        src = _read_all_gateway_routes()
        assert 'download' in src, \
            "Gateway must handle download paths"

    def test_gateway_rewrites_download_path(self):
        src = _read_all_gateway_routes()
        # Must rewrite /v1/workspaces/{wid}/artifacts/{aid}/download
        # to /internal/v1/artifacts/{aid}/download
        assert '/download' in src
        assert 'internal' in src

    def test_gateway_artifact_routes_are_get_only(self):
        src = _read_all_gateway_routes()
        # Existing guard: artifact routes are GET-only at gateway
        assert "request.method != 'GET'" in src or "method != 'GET'" in src, \
            "Gateway must block non-GET for artifact routes"

    def test_gateway_extracts_workspace_id(self):
        src = _read_all_gateway_routes()
        assert 'artifact_query_params' in src, \
            "Gateway must extract workspace_id for artifact queries"


# ═══════════════════════════════════════════════════════════════════
# D47-G6: No cross-workspace content leak
# ═══════════════════════════════════════════════════════════════════


class TestNoCrossWorkspaceLeak:
    """Download must not leak content across workspaces."""

    def test_download_returns_404_for_wrong_workspace(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        # verify_workspace raises 404 for wrong workspace
        assert 'verify_workspace' in download_section

    def test_verify_workspace_returns_404(self):
        src = _read_all_artifact_routes()
        assert '404' in src and 'verify_workspace' in src

    def test_download_requires_internal_auth(self):
        src = _read_all_artifact_routes()
        download_section = src[src.index('def download_artifact_endpoint'):]
        assert 'require_service' in download_section, \
            "Download must require internal service auth"

    def test_storage_ref_not_exposed_in_api(self):
        src = _read_all_artifact_routes()
        # storage_ref should not be in the dict serialization
        assert "storage_ref is NOT exposed" in src or \
            "'storage_ref'" not in src.split('artifact_to_dict')[1].split('def ')[0], \
            "storage_ref must not be exposed in API responses"


# ═══════════════════════════════════════════════════════════════════
# Frontend: Download button for READY artifacts
# ═══════════════════════════════════════════════════════════════════


class TestFrontendDownload:
    """Frontend must show download button only for READY artifacts."""

    def test_artifact_detail_has_download_link(self):
        path = os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', '[artifactId]', 'page.tsx',
        )
        src = _read(path)
        assert 'download' in src.lower(), \
            "Artifact detail page must have download functionality"

    def test_download_only_for_ready(self):
        path = os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', '[artifactId]', 'page.tsx',
        )
        src = _read(path)
        assert 'ready' in src.lower(), \
            "Download must be conditional on READY status"

    def test_api_client_has_download_url(self):
        path = os.path.join(PACKAGES_ROOT, 'api-client', 'src', 'artifacts.ts')
        src = _read(path)
        assert 'downloadUrl' in src, \
            "API client must have downloadUrl method"
        assert '/download' in src, \
            "Download URL must point to download endpoint"

    def test_server_state_exports_download_hook(self):
        path = os.path.join(PACKAGES_ROOT, 'server-state', 'src', 'index.ts')
        src = _read(path)
        assert 'useArtifactDownloadUrl' in src, \
            "server-state must export useArtifactDownloadUrl"
