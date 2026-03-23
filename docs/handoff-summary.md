# Keviq Core MVP — Handoff Summary

**For:** New team members receiving the Keviq Core codebase
**Tag:** `mvp-ready` (commit `0ad0c12`)
**Date:** 2026-03-16

This document gives you everything you need to understand, run, evaluate,
and continue developing Keviq Core. It is organized by role.

---

## 1. For Everyone: What You're Looking At

Keviq Core is an AI-native work operating system — 15 backend services, 1 web
frontend, 18 architecture docs, 850+ architecture gate tests, and 46 PRs
of implementation across 4 phases.

### Repository layout

```
keviq-core/
├── apps/                    # 15 backend services + web frontend
├── packages/                # Shared packages (config, etc.)
├── tools/arch-test/         # Architecture gate tests (851+)
├── infra/docker/            # Docker Compose files, env templates
└── docs/                    # Architecture + operational docs (40+ files)
```

### Where to start reading

| Your role | Start here |
|-----------|------------|
| **Anyone** | `docs/docs-index.md` — full navigation hub |
| **Operator** | `docs/runbook-go-live.md` — deploy and run |
| **Developer** | `docs/00-product-vision.md` → `docs/16-repo-structure-conventions.md` |
| **Reviewer** | `docs/02-architectural-invariants.md` → `docs/architecture-gate-review-00-12.md` |

---

## 2. For Operators: Deploy and Run

### Quick start (local profile)

```bash
# 1. Start infrastructure
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.local up -d

# 2. Verify all services are healthy
for port in 8001 8002 8003 8004 8006 8007 8008 8009 8010 8011 8012 8013 8014 8015 8080; do
  curl -sf http://localhost:$port/healthz && echo " :$port OK" || echo " :$port FAIL"
done
```

### Deployment profiles

| Profile | Security | Execution | When to use |
|---------|----------|-----------|-------------|
| **local** | Dev defaults, all ports | docker-local sandbox | Development, debugging |
| **hardened** | Read-only FS, no-new-privileges, ports stripped | noop (no sandbox) | Staging, CI, demo |
| **cloud** | Same as hardened + externalized config | configurable (noop/k8s-job) | Production |

### Key operational commands

```bash
# Hardened profile
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d

# Cloud profile
docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d

# Backup
pg_dump -U <BACKUP_USER> -h localhost -p 5434 -d mona_os -F c -f backup.dump

# View logs
docker compose logs -f orchestrator
```

### What to monitor

- `/healthz` on all 15 services
- Orchestrator recovery sweep logs (runs every 60s)
- Outbox relay batch logs (50 events/batch)
- PostgreSQL connection pool utilization

Full runbook: `docs/runbook-go-live.md`

---

## 3. For Developers: Understand and Extend

### Architecture in 60 seconds

1. **API Gateway** receives all external requests, enforces auth + RBAC
2. **Orchestrator** manages Task → Run → Step lifecycle with state machines
3. **Agent Runtime** dispatches AI work to **Model Gateway** (provider-agnostic)
4. **Execution Service** runs tools in sandboxed containers
5. **Artifact Service** stores outputs with provenance and lineage tracking
6. **Event Store** provides append-only event persistence + SSE streaming
7. **Workspace Service** manages multi-tenant isolation (workspace_id on everything)

### Service inventory

| Layer | Services |
|-------|----------|
| **Infrastructure** | PostgreSQL 16, Redis 7 |
| **Control** | auth-service, policy-service |
| **Domain** | orchestrator, agent-runtime, artifact-service, execution-service, workspace-service, secret-broker, model-gateway, audit-service, event-store, notification-service, telemetry-service |
| **API Surface** | api-gateway, sse-gateway |
| **Frontend** | web (Next.js/React) |

### Key patterns you'll see everywhere

- **Outbox pattern**: domain events committed atomically with state changes, then relayed to event-store
- **Internal service auth**: shared secret header on all cross-service HTTP calls
- **State machines**: every entity lifecycle follows explicit state transitions (doc 05)
- **workspace_id**: every entity carries workspace_id; every query filters by it
- **Hexagonal architecture**: each service has `api/` (routes), `application/` (ports/services), `infrastructure/` (adapters)

### How to run tests

```bash
# All architecture gate tests
python -m pytest tools/arch-test/ -v

# Specific gate (e.g., PR46 closeout)
python -m pytest tools/arch-test/test_pr46_project_closeout.py -v

# With live Docker (integration tests)
docker compose up -d
python -m pytest tools/arch-test/ -v --timeout=30
```

### How to add a new feature

1. Check `docs/deferred-backlog.md` — your feature may already be scoped
2. Read the relevant architecture doc (docs 00-17)
3. Follow the service structure in `docs/16-repo-structure-conventions.md`
4. Write architecture gate tests in `tools/arch-test/`
5. Run full regression before merging: `python -m pytest tools/arch-test/ -v`

---

## 4. For Architecture Reviewers: Evaluate the System

### What to verify

| Question | Where to look |
|----------|---------------|
| Are invariants upheld? | `docs/02-architectural-invariants.md` + `tools/arch-test/test_import_boundaries.py` |
| Are state machines enforced? | `docs/05-state-machines.md` + `tools/arch-test/test_pp1_state_transition_authority.py` |
| Is DB isolation real? | `infra/docker/init-schemas.sql` + `tools/arch-test/test_pp10_db_privilege.py` |
| Is internal auth enforced? | `tools/arch-test/test_pr37_internal_auth.py` (54 tests) |
| Are containers hardened? | `tools/arch-test/test_pr38_container_hardening.py` (92 tests) |
| Is workspace isolation proven? | `tools/arch-test/test_pr44_workspace_isolation.py` (49 tests) |
| Is the system operationally ready? | `tools/arch-test/test_pr45_operational_readiness.py` (97 tests) |

### Known architectural gaps

These are documented in `docs/architecture-gate-review-00-12.md` and
`docs/deferred-backlog.md` (Section 6):

- PP1: No AST-level enforcement preventing direct status field writes
- PP3: Agent-runtime does not reconcile from event log on startup
- PP10: DB privilege isolation validated structurally, not with runtime credential rotation

### What diverged from the original roadmap

The original roadmap (doc 17) defined Phase C as "Slices 7-9" (sandbox
enforcement, approval flows, taint/lineage). The actual Phase C prioritized
**hardening the existing slices** — security, concurrency, performance,
layering — which was the right call for MVP stability.

Slices 7-9 are now in `docs/deferred-backlog.md` as post-MVP product extensions.
This is an intentional scope decision, fully documented in
`docs/mvp-release-readiness.md` Section 7.

---

## 5. What Is NOT in MVP

Read `docs/deferred-backlog.md` for the full list. The top 5 items to address
before production use with real users:

1. **Load testing** — structural validation done, no benchmark under concurrency
2. **Distributed tracing export** — correlation IDs flow, no Jaeger/OTEL backend
3. **Artifact delivery** — stored and queryable, but no download/export endpoints
4. **External security audit** — no third-party pentest conducted
5. **Connection pool tuning** — default `max_connections=100` may be insufficient

---

## 6. Key Files Quick Reference

| What | Where |
|------|-------|
| Navigation hub | `docs/docs-index.md` |
| Release status | `docs/mvp-release-readiness.md` |
| Deferred backlog | `docs/deferred-backlog.md` |
| Go-live runbook | `docs/runbook-go-live.md` |
| Release announcement | `docs/mvp-announcement.md` |
| Architecture gate tests | `tools/arch-test/` |
| Docker Compose (base) | `infra/docker/docker-compose.yml` |
| Docker Compose (hardened) | `infra/docker/docker-compose.hardened.yml` |
| Docker Compose (cloud) | `infra/docker/docker-compose.cloud.yml` |
| Cloud env template | `infra/docker/.env.cloud.example` |

---

## 7. Milestone Tags

| Tag | Commit | Meaning |
|-----|--------|---------|
| `phase-a-verified` | `9d5a0a4` | Phase A foundation complete and verified |
| `mvp-ready` | `0ad0c12` | MVP operationally ready — all phases + closeout done |
