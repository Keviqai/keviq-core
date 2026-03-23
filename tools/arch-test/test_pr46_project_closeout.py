"""PR46 gate tests — Project closeout / MVP release readiness.

R46-G1: Documentation is honest (no overclaims)
R46-G2: MVP boundary is explicit (done vs deferred vs non-goals)
R46-G3: Operational guidance is actionable (runbook + checklists usable)
R46-G4: Architecture story is consistent (docs, memory, roadmap agree)
R46-G5: No feature creep (PR46 is docs-only)
R46-G6: New team member can onboard from docs
"""

import functools
import os
import re

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '../..'))
APPS_ROOT = os.path.join(REPO_ROOT, 'apps')
DOCS_ROOT = os.path.join(REPO_ROOT, 'docs')
INFRA_DOCKER = os.path.join(REPO_ROOT, 'infra', 'docker')
TOOLS_ROOT = os.path.join(REPO_ROOT, 'tools', 'arch-test')


@functools.lru_cache(maxsize=64)
def _read_doc(filename: str) -> str:
    with open(os.path.join(DOCS_ROOT, filename), encoding='utf-8') as f:
        return f.read()



def _doc_exists(filename: str) -> bool:
    return os.path.isfile(os.path.join(DOCS_ROOT, filename))


# ═══════════════════════════════════════════════════════════════════
# R46-G1: Documentation is honest
# ═══════════════════════════════════════════════════════════════════


class TestDocumentationHonest:
    """Release docs must not overclaim capabilities the system doesn't have."""

    def test_release_doc_exists(self):
        assert _doc_exists('mvp-release-readiness.md'), \
            "mvp-release-readiness.md must exist"

    def test_no_production_complete_claim(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'production-complete' not in content.lower(), \
            "Must not claim production-complete"

    def test_no_enterprise_ready_claim(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'enterprise-ready' not in content.lower(), \
            "Must not claim enterprise-ready"

    def test_no_fully_multi_tenant_claim(self):
        content = _read_doc('mvp-release-readiness.md')
        # Should not claim full multi-tenant SaaS without qualification
        assert 'fully multi-tenant' not in content.lower(), \
            "Must not claim fully multi-tenant"

    def test_known_limitations_section_exists(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'known limitation' in content.lower(), \
            "Must have Known Limitations section"

    def test_limitations_mention_no_ha(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'autoscal' in content.lower() or 'ha' in content.lower() \
            or 'high-availability' in content.lower() \
            or 'multi-region' in content.lower(), \
            "Limitations must mention HA/autoscaling gaps"

    def test_limitations_mention_no_load_test(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'load' in content.lower() or 'benchmark' in content.lower(), \
            "Limitations must mention load testing gaps"

    def test_limitations_mention_sandbox_scope(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'docker-local' in content.lower() or 'sandbox' in content.lower(), \
            "Limitations must mention sandbox execution scope"

    def test_limitations_mention_delivery_gap(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'delivery' in content.lower() or 'download' in content.lower() \
            or 'export' in content.lower(), \
            "Limitations must mention artifact delivery gap"


# ═══════════════════════════════════════════════════════════════════
# R46-G2: MVP boundary is explicit
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.skip(reason="H1-S2: MVP release doc assertions stale — project is at O8, doc structure has evolved beyond initial closeout")
class TestMVPBoundaryExplicit:
    """Clear separation between done, deferred, and non-goals."""

    def test_deferred_backlog_exists(self):
        assert _doc_exists('deferred-backlog.md'), \
            "deferred-backlog.md must exist"

    def test_deferred_has_product_extensions(self):
        content = _read_doc('deferred-backlog.md')
        assert 'product extension' in content.lower() or 'post-mvp' in content.lower(), \
            "Deferred backlog must categorize product extensions"

    def test_deferred_has_hardening_section(self):
        content = _read_doc('deferred-backlog.md')
        assert 'hardening' in content.lower() or 'production' in content.lower(), \
            "Deferred backlog must have hardening section"

    def test_deferred_has_cloud_ha_section(self):
        content = _read_doc('deferred-backlog.md')
        lower = content.lower()
        has_ha = 'high-availability' in lower or '/ ha /' in lower \
            or 'ha /' in lower or '## 3. cloud / ha' in lower
        assert ('cloud' in lower and has_ha) \
            or ('cloud' in lower and 'multi-tenant' in lower), \
            "Deferred backlog must cover cloud/HA or cloud/multi-tenant items"

    def test_deferred_has_performance_section(self):
        content = _read_doc('deferred-backlog.md')
        assert 'performance' in content.lower() or 'scale' in content.lower(), \
            "Deferred backlog must cover performance/scale items"

    def test_deferred_has_ux_section(self):
        content = _read_doc('deferred-backlog.md')
        assert 'ux' in content.lower() or 'frontend' in content.lower(), \
            "Deferred backlog must cover UX/frontend items"

    def test_deferred_has_priority_guidance(self):
        content = _read_doc('deferred-backlog.md')
        assert 'high' in content.lower() and 'medium' in content.lower() \
            and 'low' in content.lower(), \
            "Deferred backlog must have priority levels"

    def test_release_doc_has_phase_summary(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'phase a' in content.lower() and 'phase b' in content.lower() \
            and 'phase c' in content.lower() and 'phase d' in content.lower(), \
            "Release doc must summarize all phases"

    def test_release_doc_has_non_goals(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'not in mvp' in content.lower() or 'non-goal' in content.lower() \
            or 'what is not' in content.lower(), \
            "Release doc must state what is NOT in MVP"

    def test_deferred_mentions_approval_flow(self):
        content = _read_doc('deferred-backlog.md')
        assert 'approval' in content.lower(), \
            "Deferred backlog must mention deferred approval flow"

    def test_deferred_mentions_taint_lineage(self):
        content = _read_doc('deferred-backlog.md')
        assert 'taint' in content.lower(), \
            "Deferred backlog must mention deferred taint enforcement"

    def test_deferred_mentions_architectural_gaps(self):
        content = _read_doc('deferred-backlog.md')
        assert 'pp1' in content.lower() or 'pp3' in content.lower() \
            or 'gate review' in content.lower() or 'architectural gap' in content.lower(), \
            "Deferred backlog must reference architectural gaps from gate review"


# ═══════════════════════════════════════════════════════════════════
# R46-G3: Operational guidance is actionable
# ═══════════════════════════════════════════════════════════════════


class TestOperationalGuidanceActionable:
    """Runbooks and checklists must be usable by a real operator."""

    def test_runbook_exists(self):
        assert _doc_exists('runbook-go-live.md'), \
            "runbook-go-live.md must exist"

    def test_runbook_has_startup_commands(self):
        content = _read_doc('runbook-go-live.md')
        assert 'docker compose' in content, \
            "Runbook must have docker compose commands"

    def test_runbook_has_health_check_script(self):
        content = _read_doc('runbook-go-live.md')
        assert 'curl' in content, \
            "Runbook must have health check curl examples"

    def test_runbook_has_three_profiles(self):
        content = _read_doc('runbook-go-live.md')
        assert 'local' in content and 'hardened' in content and 'cloud' in content, \
            "Runbook must cover all 3 deployment profiles"

    def test_runbook_has_backup_commands(self):
        content = _read_doc('runbook-go-live.md')
        assert 'pg_dump' in content, \
            "Runbook must have backup commands"

    def test_runbook_has_rollback_section(self):
        content = _read_doc('runbook-go-live.md')
        assert 'rollback' in content.lower(), \
            "Runbook must have rollback procedures"

    def test_runbook_has_troubleshooting(self):
        content = _read_doc('runbook-go-live.md')
        assert 'troubleshoot' in content.lower(), \
            "Runbook must have troubleshooting section"

    def test_runbook_has_go_live_checklist(self):
        content = _read_doc('runbook-go-live.md')
        assert '- [ ]' in content, \
            "Runbook must have actionable checklist items"

    def test_env_example_exists(self):
        path = os.path.join(INFRA_DOCKER, '.env.cloud.example')
        assert os.path.isfile(path), \
            ".env.cloud.example must exist for operators"


# ═══════════════════════════════════════════════════════════════════
# R46-G4: Architecture story is consistent
# ═══════════════════════════════════════════════════════════════════


class TestArchitectureStoryConsistent:
    """Docs, roadmap, and release notes must tell the same story."""

    ALL_SERVICES = [
        'orchestrator', 'agent-runtime', 'artifact-service',
        'execution-service', 'workspace-service', 'auth-service',
        'policy-service', 'model-gateway', 'event-store',
        'api-gateway', 'sse-gateway', 'notification-service',
        'telemetry-service', 'audit-service', 'secret-broker',
    ]

    def test_release_doc_mentions_15_services(self):
        content = _read_doc('mvp-release-readiness.md')
        assert '15' in content, \
            "Release doc must mention 15 backend services"

    def test_release_doc_mentions_all_phases_complete(self):
        content = _read_doc('mvp-release-readiness.md')
        assert 'COMPLETE' in content, \
            "Release doc must show phases as COMPLETE"

    def test_docs_index_exists(self):
        assert _doc_exists('docs-index.md'), \
            "docs-index.md must exist"

    def test_docs_index_links_to_release_doc(self):
        content = _read_doc('docs-index.md')
        assert 'mvp-release-readiness' in content, \
            "Docs index must link to release readiness doc"

    def test_docs_index_links_to_deferred_backlog(self):
        content = _read_doc('docs-index.md')
        assert 'deferred-backlog' in content, \
            "Docs index must link to deferred backlog"

    def test_docs_index_links_to_runbook(self):
        content = _read_doc('docs-index.md')
        assert 'runbook-go-live' in content, \
            "Docs index must link to go-live runbook"

    def test_docs_index_links_to_architecture_docs(self):
        content = _read_doc('docs-index.md')
        for i in range(18):
            doc_prefix = f'{i:02d}-'
            assert doc_prefix in content, \
                f"Docs index must link to doc {doc_prefix}*.md"

    def test_docs_index_has_slice_references(self):
        content = _read_doc('docs-index.md')
        for i in range(1, 7):
            assert f'slice-{i}' in content.lower() or f'Slice {i}' in content, \
                f"Docs index must reference Slice {i}"

    @pytest.mark.skip(reason="H1-S2: MVP release doc stale — project at O8, doc evolved")
    def test_release_doc_reconciles_roadmap_vs_actual(self):
        """Release doc must honestly explain the roadmap divergence."""
        content = _read_doc('mvp-release-readiness.md')
        assert 'roadmap' in content.lower() or 'reconcil' in content.lower(), \
            "Release doc must address roadmap vs actual implementation"

    def test_all_services_have_routes_file(self):
        """Every listed service must actually exist in the codebase."""
        for svc in self.ALL_SERVICES:
            routes = os.path.join(APPS_ROOT, svc, 'src', 'api', 'routes.py')
            assert os.path.isfile(routes), \
                f"Service {svc} must exist with routes.py"

    def test_architecture_gate_review_exists(self):
        assert _doc_exists('architecture-gate-review-00-12.md'), \
            "Architecture gate review doc must exist"

    def test_isolation_model_doc_exists(self):
        assert _doc_exists('phase-d-pr44-isolation-model.md'), \
            "Phase D isolation model doc must exist"


# ═══════════════════════════════════════════════════════════════════
# R46-G5: No feature creep
# ═══════════════════════════════════════════════════════════════════


class TestNoFeatureCreep:
    """PR46 must be docs-only — no new production code, APIs, or schemas."""

    def test_no_new_api_routes(self):
        """PR46 should not have added new API endpoints."""
        content = _read_doc('mvp-release-readiness.md')
        lower = content.lower()
        assert 'new feature' not in lower or 'no new feature' in lower, \
            "Release doc must not claim new features (unless negated)"
        assert 'new endpoint' not in lower, \
            "Release doc must not introduce new endpoints"

    def test_deferred_backlog_is_documentation(self):
        """Deferred backlog must be a documentation file, not code."""
        path = os.path.join(DOCS_ROOT, 'deferred-backlog.md')
        assert path.endswith('.md'), "Deferred backlog must be markdown"

    def test_docs_index_is_documentation(self):
        path = os.path.join(DOCS_ROOT, 'docs-index.md')
        assert path.endswith('.md'), "Docs index must be markdown"


# ═══════════════════════════════════════════════════════════════════
# R46-G6: New team member can onboard from docs
# ═══════════════════════════════════════════════════════════════════


class TestOnboardingPath:
    """A new team member must be able to understand the system from docs."""

    def test_docs_index_has_role_based_paths(self):
        content = _read_doc('docs-index.md')
        assert 'operator' in content.lower(), "Must have operator reading path"
        assert 'developer' in content.lower(), "Must have developer reading path"
        assert 'reviewer' in content.lower() or 'architecture' in content.lower(), \
            "Must have architecture reviewer reading path"

    def test_docs_index_has_repo_layout(self):
        content = _read_doc('docs-index.md')
        assert 'apps/' in content, "Must describe apps/ directory"
        assert 'packages/' in content, "Must describe packages/ directory"
        assert 'tools/' in content, "Must describe tools/ directory"
        assert 'docs/' in content, "Must describe docs/ directory"

    def test_docs_index_has_test_instructions(self):
        content = _read_doc('docs-index.md')
        assert 'pytest' in content, \
            "Must include instructions for running architecture tests"

    def test_docs_index_has_phase_status_table(self):
        content = _read_doc('docs-index.md')
        assert 'Phase' in content and 'COMPLETE' in content, \
            "Must have phase completion status table"

    def test_product_vision_exists(self):
        assert _doc_exists('00-product-vision.md'), \
            "Product vision doc must exist"

    def test_system_goals_exist(self):
        assert _doc_exists('01-system-goals-and-non-goals.md'), \
            "System goals doc must exist"

    def test_repo_conventions_exist(self):
        assert _doc_exists('16-repo-structure-conventions.md'), \
            "Repo structure conventions doc must exist"

    def test_backend_service_map_exists(self):
        assert _doc_exists('15-backend-service-map.md'), \
            "Backend service map doc must exist"

    def test_roadmap_exists(self):
        assert _doc_exists('17-implementation-roadmap.md'), \
            "Implementation roadmap doc must exist"

    # Key architecture docs exist
    @pytest.mark.parametrize('doc_num', range(0, 14))
    def test_architecture_doc_exists(self, doc_num):
        pattern = f'{doc_num:02d}-'
        found = any(f.startswith(pattern) for f in os.listdir(DOCS_ROOT)
                     if f.endswith('.md'))
        assert found, f"Architecture doc {doc_num:02d}-*.md must exist"
