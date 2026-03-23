"""PR42 gate tests — Performance and scale readiness.

C42-G1: No regression in correctness (arch boundary tests still pass)
C42-G2: Streaming is truly streaming (SSE proxy uses aiter_bytes, separate client)
C42-G3: Large-list paths are bounded (LIMIT/OFFSET, _MAX_LIMIT caps)
C42-G4: Optimizations stay inside correct layer (no perf hacks in domain/)
C42-G5: Scale improvements are testable/observable (batch ingest, pool configs, shared clients)
"""

import ast
import os
import re

import pytest

APPS_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../apps'))


def _read(relpath: str) -> str:
    with open(os.path.join(APPS_ROOT, relpath), encoding='utf-8') as f:
        return f.read()


# ── C42-G2: Streaming is truly streaming ─────────────────────────────


class TestSSEStreamingIsReal:
    """Verify api-gateway proxies SSE via true streaming, not buffering."""

    PROXY = 'api-gateway/src/infrastructure/service_proxy.py'

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.PROXY)

    def test_sse_client_exists(self):
        """A separate httpx client with long timeout must exist for SSE."""
        assert '_sse_client' in self.src, '_sse_client not found in service_proxy'

    def test_sse_client_has_long_timeout(self):
        """SSE client must use SSE_TIMEOUT (3600s default), not the normal 10s."""
        assert 'SSE_TIMEOUT' in self.src
        # Verify the default is much higher than normal TIMEOUT
        match = re.search(r"SSE_TIMEOUT\s*=\s*float\(.+?'([\d.]+)'", self.src)
        assert match, 'SSE_TIMEOUT default not found'
        assert float(match.group(1)) >= 300, 'SSE_TIMEOUT default must be >= 300s'

    def test_is_sse_path_helper_exists(self):
        """_is_sse_path() must exist for detecting SSE endpoints."""
        assert 'def _is_sse_path(' in self.src

    def test_proxy_sse_stream_uses_aiter_bytes(self):
        """SSE proxy must use aiter_bytes() for true chunk-by-chunk streaming."""
        assert 'aiter_bytes()' in self.src, 'SSE proxy must use aiter_bytes()'

    def test_proxy_sse_stream_returns_streaming_response(self):
        """SSE proxy must return StreamingResponse, not buffered Response."""
        assert 'StreamingResponse(' in self.src

    def test_proxy_request_delegates_to_sse_handler(self):
        """proxy_request() must detect SSE paths and delegate."""
        assert '_is_sse_path(path)' in self.src
        assert '_proxy_sse_stream(' in self.src


# ── C42-G3: Large-list paths are bounded ─────────────────────────────


class TestQueryBounds:
    """Verify unbounded list endpoints have LIMIT/OFFSET caps."""

    def test_workspace_repo_has_max_limit(self):
        src = _read('workspace-service/src/infrastructure/db/workspace_repository.py')
        assert '_MAX_LIMIT' in src, 'workspace_repository must define _MAX_LIMIT'
        match = re.search(r'_MAX_LIMIT\s*=\s*(\d+)', src)
        assert match and int(match.group(1)) <= 500, '_MAX_LIMIT must be <= 500'

    def test_workspace_find_by_user_is_paginated(self):
        src = _read('workspace-service/src/infrastructure/db/workspace_repository.py')
        # Must contain LIMIT and OFFSET in the query
        assert 'LIMIT :limit OFFSET :offset' in src

    def test_workspace_members_is_paginated(self):
        src = _read('workspace-service/src/infrastructure/db/workspace_repository.py')
        # find_members_by_workspace must accept limit/offset
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'find_members_by_workspace':
                arg_names = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
                assert 'limit' in arg_names, 'find_members_by_workspace must accept limit'
                assert 'offset' in arg_names, 'find_members_by_workspace must accept offset'
                return
        pytest.fail('find_members_by_workspace not found')

    def test_policy_repo_has_max_limit(self):
        src = _read('policy-service/src/infrastructure/db/policy_repository.py')
        assert '_MAX_LIMIT' in src, 'policy_repository must define _MAX_LIMIT'
        match = re.search(r'_MAX_LIMIT\s*=\s*(\d+)', src)
        assert match and int(match.group(1)) <= 500

    def test_policy_list_is_paginated(self):
        src = _read('policy-service/src/infrastructure/db/policy_repository.py')
        assert 'LIMIT :limit OFFSET :offset' in src

    def test_artifact_repo_has_max_limit(self):
        src = _read('artifact-service/src/infrastructure/db/repositories.py')
        assert '_MAX_LIMIT' in src


# ── C42-G4: Optimizations stay inside correct layer ──────────────────


class TestNoPerformanceHacksInDomain:
    """Domain layer must not contain DB queries, httpx, or pool config."""

    SERVICES_WITH_DOMAIN = [
        d for d in os.listdir(APPS_ROOT)
        if os.path.isdir(os.path.join(APPS_ROOT, d, 'src', 'domain'))
    ]

    @pytest.mark.parametrize('service', SERVICES_WITH_DOMAIN)
    def test_domain_has_no_sqlalchemy(self, service):
        domain_dir = os.path.join(APPS_ROOT, service, 'src', 'domain')
        for dirpath, _, filenames in os.walk(domain_dir):
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(dirpath, fname)
                src = open(fpath, encoding='utf-8').read()
                assert 'sqlalchemy' not in src, (
                    f'{service}/src/domain/{fname} imports sqlalchemy — '
                    f'performance optimizations must stay in infrastructure/'
                )

    @pytest.mark.parametrize('service', SERVICES_WITH_DOMAIN)
    def test_domain_has_no_httpx(self, service):
        domain_dir = os.path.join(APPS_ROOT, service, 'src', 'domain')
        for dirpath, _, filenames in os.walk(domain_dir):
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(dirpath, fname)
                src = open(fpath, encoding='utf-8').read()
                assert 'import httpx' not in src, (
                    f'{service}/src/domain/{fname} imports httpx — '
                    f'HTTP clients must stay in infrastructure/'
                )


# ── C42-G5: Scale improvements are testable/observable ───────────────


class TestBatchIngest:
    """Event-store must support batch ingest with single commit."""

    def test_repository_has_ingest_batch(self):
        src = _read('event-store/src/infrastructure/db/repository.py')
        assert 'def ingest_batch(' in src, 'SqlEventRepository must have ingest_batch()'

    def test_ingest_batch_single_commit(self):
        """ingest_batch must call commit only once after all inserts."""
        src = _read('event-store/src/infrastructure/db/repository.py')
        # Extract the ingest_batch method body
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'ingest_batch':
                # Count commit calls in the method — should be exactly 1
                method_src = ast.get_source_segment(src, node)
                commit_count = method_src.count('.commit()')
                assert commit_count == 1, (
                    f'ingest_batch has {commit_count} commit() calls, expected 1'
                )
                return
        pytest.fail('ingest_batch method not found')

    def test_ports_declares_ingest_batch(self):
        src = _read('event-store/src/application/ports.py')
        assert 'ingest_batch' in src, 'EventRepository port must declare ingest_batch()'


class TestPoolStandardization:
    """Hot services must use standardized pool config."""

    HOT_SERVICES = {
        'orchestrator': 'src/main.py',
        'artifact-service': 'src/main.py',
        'execution-service': 'src/main.py',
        'event-store': 'src/main.py',
    }

    @pytest.mark.parametrize('service,main_file', list(HOT_SERVICES.items()))
    def test_pool_pre_ping_enabled(self, service, main_file):
        src = _read(f'{service}/{main_file}')
        assert 'pool_pre_ping=True' in src, f'{service} must enable pool_pre_ping'

    @pytest.mark.parametrize('service,main_file', list(HOT_SERVICES.items()))
    def test_pool_size_at_least_10(self, service, main_file):
        src = _read(f'{service}/{main_file}')
        match = re.search(r'pool_size=(\d+)', src)
        assert match, f'{service} must set pool_size'
        assert int(match.group(1)) >= 10, f'{service} pool_size must be >= 10'

    @pytest.mark.parametrize('service,main_file', list(HOT_SERVICES.items()))
    def test_pool_recycle_set(self, service, main_file):
        src = _read(f'{service}/{main_file}')
        assert 'pool_recycle=' in src, f'{service} must set pool_recycle'


class TestSharedHttpClients:
    """api-gateway must use module-level shared httpx clients, not per-request."""

    CLIENTS = [
        'api-gateway/src/infrastructure/workspace_client.py',
        'api-gateway/src/infrastructure/policy_client.py',
    ]

    @pytest.mark.parametrize('path', CLIENTS)
    def test_module_level_client(self, path):
        src = _read(path)
        assert '_client = httpx.AsyncClient(' in src, (
            f'{path} must use a module-level shared httpx client'
        )

    @pytest.mark.parametrize('path', CLIENTS)
    def test_no_per_request_client(self, path):
        src = _read(path)
        assert 'async with httpx.AsyncClient' not in src, (
            f'{path} must not create per-request httpx clients'
        )


class TestLineageOptimizations:
    """Lineage queries must be workspace-scoped and use recursive CTE."""

    REPO = 'artifact-service/src/infrastructure/db/repositories.py'

    @pytest.fixture(autouse=True)
    def _load(self):
        self.src = _read(self.REPO)

    def test_workspace_scoped_edges(self):
        """list_edges_by_workspace must exist (not the old list_all_edges)."""
        assert 'def list_edges_by_workspace(' in self.src
        assert 'def list_all_edges(' not in self.src, 'list_all_edges must be removed'

    def test_workspace_scoped_edges_has_join(self):
        """Must JOIN to artifacts table to scope by workspace_id."""
        assert 'JOIN artifact_core.artifacts' in self.src

    def test_ancestor_edges_uses_recursive_cte(self):
        """list_ancestor_edges must use WITH RECURSIVE, not BFS."""
        assert 'WITH RECURSIVE ancestors' in self.src

    def test_no_deque_import(self):
        """BFS deque import must be gone — replaced by CTE."""
        assert 'from collections import deque' not in self.src
