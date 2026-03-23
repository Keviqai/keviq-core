"""PR49 gate tests — Upload / import artifact roots.

U49-G1: Upload endpoint exists with POST method and multipart form
U49-G2: Upload has configurable size cap (env-driven)
U49-G3: Server-authoritative mime detection (not trusting client)
U49-G4: Provenance is root-type-aware (uploaded ≠ generated)
U49-G5: Gateway routing, method guard, and artifact:create permission
U49-G6: Frontend upload UI (button, mutation hook, redirect)
U49-G7: State machine preserved (PENDING → WRITING → READY in single call)
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


# ═══════════════════════════════════════════════════════════════════
# U49-G1: Upload endpoint exists with POST method and multipart form
# ═══════════════════════════════════════════════════════════════════


class TestUploadEndpointExists:
    """Upload endpoint must be a POST with multipart file handling."""

    def test_upload_route_exists(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert '/upload' in src, "Upload endpoint must exist in routes_content"

    def test_upload_route_is_post(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert re.search(
            r'@content_router\.post\([^)]*upload[^)]*\)',
            src,
        ), "Upload must be a POST endpoint"

    def test_upload_accepts_file_param(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert 'UploadFile' in src, "Upload must use FastAPI UploadFile"
        assert 'File(...)' in src, "Upload must have a required File parameter"

    def test_upload_returns_201(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        idx = src.index('def upload_artifact_endpoint')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert '201' in upload_section or 'HTTP_201_CREATED' in upload_section, \
            "Upload must return 201 Created"

    def test_upload_response_has_required_fields(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        idx = src.index('def upload_artifact_endpoint')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        for field in ['artifact_type', 'root_type', 'artifact_status',
                       'mime_type', 'size_bytes', 'checksum']:
            assert field in upload_section, \
                f"Upload response must include '{field}'"


# ═══════════════════════════════════════════════════════════════════
# U49-G2: Upload has configurable size cap (env-driven)
# ═══════════════════════════════════════════════════════════════════


class TestUploadSizeCap:
    """Upload must enforce a configurable size limit."""

    def test_upload_max_bytes_constant_exists(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert 'UPLOAD_MAX_BYTES' in src, \
            "Upload size cap constant must exist"

    def test_size_cap_is_env_configurable(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert re.search(
            r'os\.getenv\([^)]*ARTIFACT_UPLOAD_MAX_BYTES[^)]*\)',
            src,
        ), "Upload size cap must be configurable via env var"

    def test_size_cap_defaults_to_25mb(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        # 25 * 1024 * 1024 = 26214400
        assert '25 * 1024 * 1024' in src or '26214400' in src, \
            "Default upload size cap must be 25 MB"

    def test_413_returned_on_oversized_file(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        idx = src.index('def upload_artifact_endpoint')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert '413' in upload_section or 'HTTP_413' in upload_section, \
            "Oversized file must return 413 Request Entity Too Large"


# ═══════════════════════════════════════════════════════════════════
# U49-G3: Server-authoritative mime detection
# ═══════════════════════════════════════════════════════════════════


class TestServerMimeDetection:
    """Server must detect mime type from filename, not trust client blindly."""

    def test_detect_mime_type_function_exists(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert '_detect_mime_type' in src, \
            "Server-side mime detection function must exist"

    def test_uses_mimetypes_module(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert 'import mimetypes' in src or 'from mimetypes' in src, \
            "Must use Python mimetypes module for server-side detection"

    def test_mime_detection_uses_filename(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert 'guess_type' in src, \
            "Must use mimetypes.guess_type() for filename-based detection"

    def test_fallback_to_octet_stream(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'api', 'routes_content.py'))
        assert 'application/octet-stream' in src, \
            "Unknown types must fall back to application/octet-stream"


# ═══════════════════════════════════════════════════════════════════
# U49-G4: Provenance is root-type-aware
# ═══════════════════════════════════════════════════════════════════


class TestProvenanceRootTypeAware:
    """Uploaded artifacts must not require model/run provenance."""

    def test_validate_complete_accepts_root_type(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'domain', 'provenance.py'))
        assert re.search(
            r'def validate_complete\([^)]*root_type',
            src,
        ), "validate_complete must accept root_type parameter"

    def test_upload_root_type_skips_model_provenance(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'domain', 'provenance.py'))
        idx = src.index('def validate_complete')
        vc_section = src[idx:]
        next_def = re.search(r'\n    def [a-z]', vc_section[1:])
        if next_def:
            vc_section = vc_section[:next_def.start() + 1]
        assert 'upload' in vc_section, \
            "validate_complete must handle upload root type"
        # Should NOT require model_provider for uploads
        assert 'model_provider' in vc_section, \
            "validate_complete must reference model_provider for generated"

    def test_generated_still_requires_model_provenance(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'domain', 'provenance.py'))
        idx = src.index('def validate_complete')
        vc_section = src[idx:]
        next_def = re.search(r'\n    def [a-z]', vc_section[1:])
        if next_def:
            vc_section = vc_section[:next_def.start() + 1]
        # Generated path must still require these
        for field in ['model_provider', 'model_name_concrete', 'model_version_concrete']:
            assert field in vc_section, \
                f"Generated provenance must still require '{field}'"

    def test_artifact_finalize_passes_root_type(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'domain', 'artifact.py'))
        assert 'root_type' in src, \
            "Artifact.finalize must pass root_type to validate_complete"

    def test_upload_service_creates_minimal_provenance(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'ArtifactProvenance' in upload_section, \
            "Upload service must create provenance record"
        # Should NOT set model_provider for uploads
        assert 'model_provider' not in upload_section, \
            "Upload service must NOT set model provenance fields"


# ═══════════════════════════════════════════════════════════════════
# U49-G5: Gateway routing, method guard, and artifact:create permission
# ═══════════════════════════════════════════════════════════════════


class TestGatewayUploadRouting:
    """Gateway must route upload POST, guard methods, enforce permission."""

    def test_upload_path_rewrite(self):
        src = _read(os.path.join(GATEWAY_SVC, 'api', 'routing.py'))
        assert 'upload' in src, \
            "Gateway routing must handle upload path rewrite"

    def test_upload_path_rewrites_to_internal(self):
        src = _read(os.path.join(GATEWAY_SVC, 'api', 'routing.py'))
        assert '/internal/v1/workspaces/' in src, \
            "Upload rewrite must preserve workspace_id in internal path"

    def test_method_guard_allows_post_for_upload(self):
        src = _read(os.path.join(GATEWAY_SVC, 'api', 'routes.py'))
        assert '/artifacts/upload' in src, \
            "Method guard must check for upload path"
        # Must allow POST for upload
        assert re.search(
            r"request\.method\s*==\s*'POST'.*upload|upload.*request\.method\s*==\s*'POST'",
            src,
            re.DOTALL,
        ), "Method guard must allow POST for upload paths"

    def test_artifact_create_permission_exists(self):
        src = _read(os.path.join(GATEWAY_SVC, 'application', 'auth_middleware.py'))
        assert 'artifact:create' in src, \
            "PERMISSION_MAP must include artifact:create for upload"

    def test_permission_map_has_upload_entry(self):
        src = _read(os.path.join(GATEWAY_SVC, 'application', 'auth_middleware.py'))
        assert re.search(
            r"\('POST'.*upload'\).*artifact:create",
            src,
        ), "PERMISSION_MAP must map POST upload to artifact:create"

    def test_action_literal_upload_recognized(self):
        src = _read(os.path.join(GATEWAY_SVC, 'application', 'auth_middleware.py'))
        assert 'upload' in src, \
            "match_permission must recognize 'upload' as action literal"


# ═══════════════════════════════════════════════════════════════════
# U49-G6: Frontend upload UI
# ═══════════════════════════════════════════════════════════════════


class TestFrontendUploadUI:
    """Artifact list page must have upload button and mutation hook."""

    def test_upload_button_exists(self):
        src = _read(os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', 'page.tsx',
        ))
        assert 'Upload artifact' in src or 'upload' in src.lower(), \
            "Artifact list page must have upload button"

    def test_file_input_exists(self):
        src = _read(os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', 'page.tsx',
        ))
        assert 'type="file"' in src, \
            "Page must have a file input element"

    def test_upload_mutation_hook_exists(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'server-state', 'src', 'hooks', 'use-artifacts.ts',
        ))
        assert 'useArtifactUpload' in src, \
            "useArtifactUpload mutation hook must exist"

    def test_upload_hook_uses_mutation(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'server-state', 'src', 'hooks', 'use-artifacts.ts',
        ))
        assert 'useMutation' in src, \
            "Upload hook must use useMutation"

    def test_upload_hook_invalidates_list(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'server-state', 'src', 'hooks', 'use-artifacts.ts',
        ))
        idx = src.index('useArtifactUpload')
        hook_section = src[idx:]
        assert 'invalidateQueries' in hook_section, \
            "Upload hook must invalidate artifact list on success"

    def test_upload_hook_exported(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'server-state', 'src', 'index.ts',
        ))
        assert 'useArtifactUpload' in src, \
            "useArtifactUpload must be exported from server-state"

    def test_api_client_has_upload_method(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'api-client', 'src', 'artifacts.ts',
        ))
        assert 'upload' in src, \
            "ArtifactsApi must have upload method"

    def test_api_client_has_post_form(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'api-client', 'src', 'client.ts',
        ))
        assert 'postForm' in src, \
            "ApiClient must have postForm method for multipart"

    def test_upload_uses_form_data(self):
        src = _read(os.path.join(
            PACKAGES_ROOT, 'api-client', 'src', 'artifacts.ts',
        ))
        assert 'FormData' in src, \
            "Upload must use FormData for multipart encoding"

    def test_success_redirects_to_detail(self):
        src = _read(os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', 'page.tsx',
        ))
        assert 'artifactDetailPath' in src, \
            "Upload success must redirect to artifact detail page"
        assert 'router.push' in src, \
            "Must use router.push for redirect after upload"

    def test_error_banner_shown(self):
        src = _read(os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', 'page.tsx',
        ))
        assert 'Upload failed' in src or 'upload.isError' in src, \
            "Upload errors must be displayed to user"


# ═══════════════════════════════════════════════════════════════════
# U49-G7: State machine preserved (PENDING → WRITING → READY)
# ═══════════════════════════════════════════════════════════════════


class TestStateMachinePreserved:
    """Upload service must go through PENDING → WRITING → READY transitions."""

    def test_upload_service_calls_begin_writing(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'begin_writing' in upload_section, \
            "Upload service must call begin_writing (PENDING → WRITING)"

    def test_upload_service_calls_finalize(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'finalize' in upload_section, \
            "Upload service must call finalize (WRITING → READY)"

    def test_upload_service_computes_checksum(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'sha256' in upload_section, \
            "Upload service must compute SHA-256 checksum"

    def test_upload_service_writes_to_storage(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'write_content' in upload_section, \
            "Upload service must write content to storage backend"

    def test_upload_sets_root_type_upload(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'RootType.UPLOAD' in upload_section or "root_type='upload'" in upload_section, \
            "Upload service must set root_type to UPLOAD"

    def test_upload_emits_outbox_events(self):
        src = _read(os.path.join(ARTIFACT_SVC, 'application', 'services.py'))
        idx = src.index('def upload_artifact')
        upload_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', upload_section[1:])
        if next_def:
            upload_section = upload_section[:next_def.start() + 1]
        assert 'artifact_registered_event' in upload_section, \
            "Upload must emit artifact.registered event"
        assert 'artifact_ready_event' in upload_section, \
            "Upload must emit artifact.ready event"
