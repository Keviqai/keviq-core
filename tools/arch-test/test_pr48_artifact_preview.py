"""PR48 gate tests — Artifact preview and content rendering.

P48-G1: Preview is a separate endpoint, not download
P48-G2: Only supported text-like mimes are previewable
P48-G3: Preview has size cap, no unbounded load
P48-G4: Wrong workspace cannot preview
P48-G5: Frontend renders markdown/json/text, fallbacks for unsupported/too_large
P48-G6: No image/binary preview in scope
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
# P48-G1: Preview is a separate endpoint, not download
# ═══════════════════════════════════════════════════════════════════


class TestPreviewIsSeparateEndpoint:
    """Preview endpoint must be distinct from download endpoint."""

    def test_preview_endpoint_exists(self):
        src = _read_all_artifact_routes()
        assert '/preview' in src, \
            "Preview endpoint must exist in routes"

    def test_preview_route_is_get(self):
        src = _read_all_artifact_routes()
        assert re.search(
            r'@(?:router|content_router)\.get\([^)]*preview[^)]*\)',
            src,
        ), "Preview must be a GET endpoint"

    def test_preview_endpoint_path_distinct_from_download(self):
        src = _read_all_artifact_routes()
        # Both must exist as separate endpoints
        assert re.search(
            r'@(?:router|content_router)\.get\([^)]*download[^)]*\)', src,
        ), "Download endpoint must still exist"
        assert re.search(
            r'@(?:router|content_router)\.get\([^)]*preview[^)]*\)', src,
        ), "Preview endpoint must exist separately"

    def test_preview_returns_json_not_raw_bytes(self):
        src = _read_all_artifact_routes()
        # Find the preview function body
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        # Must return dict (JSON), not Response
        assert 'preview_kind' in preview_section, \
            "Preview must return JSON with preview_kind field"

    def test_preview_response_has_required_fields(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        for field in ['artifact_id', 'mime_type', 'preview_kind',
                       'size_bytes', 'truncated', 'content']:
            assert f'"{field}"' in preview_section, \
                f"Preview response must include {field}"

    def test_preview_does_not_set_content_disposition(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        assert 'Content-Disposition' not in preview_section, \
            "Preview must NOT set Content-Disposition (that's download semantics)"


# ═══════════════════════════════════════════════════════════════════
# P48-G2: Only supported text-like mimes are previewable
# ═══════════════════════════════════════════════════════════════════


class TestSupportedMimesOnly:
    """Preview must only support text-based mime types."""

    def test_previewable_mimes_defined(self):
        src = _read_all_artifact_routes()
        assert 'PREVIEWABLE_MIMES' in src, \
            "Must define PREVIEWABLE_MIMES set"

    def test_text_plain_supported(self):
        src = _read_all_artifact_routes()
        assert '"text/plain"' in src

    def test_application_json_supported(self):
        src = _read_all_artifact_routes()
        assert '"application/json"' in src

    def test_text_markdown_supported(self):
        src = _read_all_artifact_routes()
        assert '"text/markdown"' in src

    def test_resolve_preview_kind_function_exists(self):
        src = _read_all_artifact_routes()
        assert 'def resolve_preview_kind(' in src or 'def _resolve_preview_kind(' in src

    def test_preview_kind_values(self):
        src = _read_all_artifact_routes()
        for kind in ['text', 'json', 'markdown', 'unsupported']:
            assert f'"{kind}"' in src, \
                f"preview_kind '{kind}' must be returned"

    def test_unsupported_mime_returns_unsupported_kind(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        # Must check for unsupported kind and return without reading storage
        assert '"unsupported"' in preview_section


# ═══════════════════════════════════════════════════════════════════
# P48-G3: Preview has size cap, no unbounded load
# ═══════════════════════════════════════════════════════════════════


class TestPreviewSizeCap:
    """Preview must enforce a size limit."""

    def test_preview_max_bytes_defined(self):
        src = _read_all_artifact_routes()
        assert 'PREVIEW_MAX_BYTES' in src, \
            "Must define PREVIEW_MAX_BYTES constant"

    def test_preview_max_is_1mb(self):
        src = _read_all_artifact_routes()
        assert '1_048_576' in src or '1048576' in src, \
            "PREVIEW_MAX_BYTES must be 1 MB (1048576)"

    def test_too_large_kind_exists(self):
        src = _read_all_artifact_routes()
        assert '"too_large"' in src, \
            "Must return too_large preview_kind for oversized content"

    def test_preview_checks_size_before_read(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        # size check must appear before read_content
        size_check_pos = preview_section.find('PREVIEW_MAX_BYTES')
        read_pos = preview_section.find('read_content')
        assert size_check_pos < read_pos, \
            "Must check size cap before reading content"

    def test_truncation_flag_in_response(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        assert 'truncated' in preview_section, \
            "Preview must include truncated flag in response"


# ═══════════════════════════════════════════════════════════════════
# P48-G4: Wrong workspace cannot preview
# ═══════════════════════════════════════════════════════════════════


class TestPreviewWorkspaceIsolation:
    """Preview must verify workspace ownership."""

    def test_preview_requires_workspace_id(self):
        src = _read_all_artifact_routes()
        match = re.search(
            r'def preview_artifact_endpoint\(.*?workspace_id',
            src, re.DOTALL,
        )
        assert match, "Preview endpoint must require workspace_id"

    def test_preview_calls_verify_workspace(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        assert 'verify_workspace' in preview_section, \
            "Preview must call _verify_workspace"

    def test_preview_requires_internal_auth(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        assert 'require_service' in preview_section, \
            "Preview must require internal service auth"

    def test_preview_checks_ready_status(self):
        src = _read_all_artifact_routes()
        idx = src.index('def preview_artifact_endpoint')
        preview_section = src[idx:]
        next_def = re.search(r'\ndef [a-z]', preview_section[1:])
        if next_def:
            preview_section = preview_section[:next_def.start() + 1]
        assert '409' in preview_section, \
            "Preview must return 409 for non-READY artifacts"

    def test_gateway_routes_preview(self):
        src = _read_all_gateway_routes()
        assert '/preview' in src, \
            "Gateway must route preview paths"

    def test_gateway_rewrites_preview_path(self):
        src = _read_all_gateway_routes()
        assert re.search(
            r"parts\[\d+\]\s*==\s*'preview'",
            src,
        ), "Gateway must rewrite preview sub-resource path"


# ═══════════════════════════════════════════════════════════════════
# P48-G5: Frontend renders markdown/json/text with fallbacks
# ═══════════════════════════════════════════════════════════════════


class TestFrontendPreviewRendering:
    """Frontend must render preview content by kind with proper fallbacks."""

    def _detail_page(self) -> str:
        page = _read(os.path.join(
            WEB_APP, 'app', '(shell)', 'workspaces',
            '[workspaceId]', 'artifacts', '[artifactId]', 'page.tsx',
        ))
        preview_module = os.path.join(
            WEB_APP, 'modules', 'artifact', 'artifact-preview-section.tsx',
        )
        if os.path.exists(preview_module):
            page += '\n' + _read(preview_module)
        return page

    def test_preview_section_exists(self):
        src = self._detail_page()
        assert 'Preview' in src, \
            "Artifact detail page must have a Preview section"

    def test_uses_preview_hook(self):
        src = self._detail_page()
        assert 'useArtifactPreview' in src, \
            "Must use useArtifactPreview hook"

    def test_renders_markdown(self):
        src = self._detail_page()
        assert 'ReactMarkdown' in src or 'react-markdown' in src, \
            "Must use react-markdown for markdown rendering"

    def test_handles_json_preview(self):
        src = self._detail_page()
        assert 'json' in src.lower() and 'JSON.stringify' in src, \
            "Must format JSON content for display"

    def test_handles_text_preview(self):
        src = self._detail_page()
        assert '<pre' in src, \
            "Must render text content in a pre element"

    def test_handles_unsupported_fallback(self):
        src = self._detail_page()
        assert 'unsupported' in src, \
            "Must handle unsupported preview kind"

    def test_handles_too_large_fallback(self):
        src = self._detail_page()
        assert 'too_large' in src, \
            "Must handle too_large preview kind"

    def test_unsupported_shows_download_button(self):
        src = self._detail_page()
        # After unsupported check, must offer download as fallback
        assert 'Download instead' in src or 'download' in src.lower(), \
            "Unsupported preview must offer download fallback"

    def test_truncation_warning_shown(self):
        src = self._detail_page()
        assert 'truncated' in src, \
            "Must show truncation warning when content is truncated"

    def test_server_state_exports_preview_hook(self):
        src = _read(os.path.join(PACKAGES_ROOT, 'server-state', 'src', 'index.ts'))
        assert 'useArtifactPreview' in src, \
            "server-state must export useArtifactPreview"

    def test_api_client_has_preview_method(self):
        src = _read(os.path.join(PACKAGES_ROOT, 'api-client', 'src', 'artifacts.ts'))
        assert 'preview' in src, \
            "API client must have preview method"
        assert '/preview' in src, \
            "Preview URL must point to preview endpoint"

    def test_api_client_preview_response_type(self):
        src = _read(os.path.join(PACKAGES_ROOT, 'api-client', 'src', 'artifacts.ts'))
        assert 'ArtifactPreviewResponse' in src, \
            "API client must define ArtifactPreviewResponse type"

    def test_query_key_has_preview(self):
        src = _read(os.path.join(PACKAGES_ROOT, 'server-state', 'src', 'query-keys.ts'))
        assert 'preview' in src, \
            "Query keys must include preview"


# ═══════════════════════════════════════════════════════════════════
# P48-G6: No image/binary preview leak into scope
# ═══════════════════════════════════════════════════════════════════


class TestNoImageBinaryPreview:
    """PR48 must not include image or binary preview capabilities."""

    def test_no_image_mime_in_previewable(self):
        src = _read_all_artifact_routes()
        # Extract the PREVIEWABLE_MIMES set
        idx = src.index('PREVIEWABLE_MIMES')
        end = src.index('}', idx) + 1
        mimes_section = src[idx:end]
        assert 'image/' not in mimes_section, \
            "PREVIEWABLE_MIMES must not include image types"

    def test_no_pdf_mime_in_previewable(self):
        src = _read_all_artifact_routes()
        idx = src.index('PREVIEWABLE_MIMES')
        end = src.index('}', idx) + 1
        mimes_section = src[idx:end]
        assert 'pdf' not in mimes_section.lower(), \
            "PREVIEWABLE_MIMES must not include PDF"

    def test_no_image_element_in_preview_section(self):
        # Preview section may be inline or extracted to a module
        preview_module = os.path.join(
            WEB_APP, 'modules', 'artifact', 'artifact-preview-section.tsx',
        )
        if os.path.exists(preview_module):
            src = _read(preview_module)
        else:
            src = _read(os.path.join(
                WEB_APP, 'app', '(shell)', 'workspaces',
                '[workspaceId]', 'artifacts', '[artifactId]', 'page.tsx',
            ))
        if 'ArtifactPreviewSection' in src:
            idx = src.index('function ArtifactPreviewSection')
            preview_component = src[idx:]
            assert '<img' not in preview_component, \
                "Preview section must not render <img> elements"
            assert '<video' not in preview_component, \
                "Preview section must not render <video> elements"
            assert '<audio' not in preview_component, \
                "Preview section must not render <audio> elements"

    def test_no_binary_preview_kind(self):
        src = _read_all_artifact_routes()
        # Function may be named resolve_preview_kind (after split) or _resolve_preview_kind
        try:
            idx = src.index('def _resolve_preview_kind')
        except ValueError:
            idx = src.index('def resolve_preview_kind')
        resolver = src[idx:]
        next_def = re.search(r'\ndef [a-z]', resolver[1:])
        if next_def:
            resolver = resolver[:next_def.start() + 1]
        assert '"image"' not in resolver, \
            "Preview kind resolver must not return 'image'"
        assert '"binary"' not in resolver, \
            "Preview kind resolver must not return 'binary'"
