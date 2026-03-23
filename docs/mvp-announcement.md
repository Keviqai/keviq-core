# Keviq Core MVP — Release Announcement

**Date:** 2026-03-16
**Tag:** `mvp-ready` (commit `0ad0c12`)
**Status:** Operationally release-ready

---

## What is Keviq Core?

Keviq Core is an **AI-native work operating system** — a unified workspace where
humans, AI agents, tools, and compute resources coexist in a structured
operating environment. It is not a chatbot. It is not an automation dashboard.

Target users: engineers, knowledge workers, and managers who need AI for
multi-step digital workflows — code analysis, research, planning, document
generation, and structured task execution.

---

## What the MVP Proves

The MVP delivers **9 end-to-end flows**, each proven through architecture
gate tests and structural validation:

| # | Flow | What Works |
|---|------|------------|
| 1 | **Auth & Workspace** | JWT auth, workspace CRUD, membership RBAC (owner/admin/member), fail-closed policy enforcement |
| 2 | **Task Orchestration** | Task submission → Run → Steps with full state machines, cancellation cascade |
| 3 | **Agent & Model Path** | Agent invocation, model calls via provider-agnostic gateway, retry with backoff |
| 4 | **Sandbox Execution** | Docker-local sandbox provisioning, tool execution with timeout/resource limits |
| 5 | **Artifact & Lineage** | Artifact registration with provenance, lineage DAG, workspace-scoped queries |
| 6 | **Event Pipeline** | Outbox pattern, batch relay, append-only event store, SSE with Last-Event-ID replay |
| 7 | **Frontend Surfaces** | Web shell, task/run/step views, live timeline with SSE, artifact/lineage views |
| 8 | **Security & Hardening** | Internal service auth, container hardening, concurrency safety, recovery sweeps |
| 9 | **Deployment & Ops** | 3 deployment profiles (local/hardened/cloud), health endpoints, go-live runbook |

---

## By the Numbers

| Metric | Value |
|--------|-------|
| Total PRs | 46 |
| Backend services | 15 |
| Architecture gate tests | 850+ passing |
| Deployment profiles | 3 (local, hardened, cloud) |
| Architecture docs | 18 (docs 00-17) |
| Slice docs | 17 (contracts, gates, closeouts) |
| Operational docs | 4 (runbook, release readiness, deferred backlog, docs index) |
| DB schemas | 12 (isolated per service) |

---

## Development Phases

| Phase | Scope | PRs | Status |
|-------|-------|-----|--------|
| **A** | Foundation: 15 service skeletons, DB schemas, arch tests | PR1-PR12 | COMPLETE |
| **B** | Vertical slices: 6 end-to-end flows proven | PR13-PR36 | COMPLETE |
| **C** | Hardening: security, concurrency, performance, layering | PR37-PR42 | COMPLETE |
| **D** | Deployment: profiles, isolation, operational validation | PR43-PR45 | COMPLETE |
| **Closeout** | Release docs, deferred backlog, docs index | PR46 | COMPLETE |

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                        │
│              (auth + RBAC proxy)                     │
├──────────────┬──────────────┬───────────────────────┤
│  orchestrator│ agent-runtime│ artifact-service       │
│  exec-service│ model-gateway│ workspace-service      │
│  event-store │ secret-broker│ audit-service          │
│  notification│ telemetry    │ policy-service         │
│              │              │ auth-service           │
├──────────────┴──────────────┴───────────────────────┤
│         SSE Gateway (real-time event streams)        │
├─────────────────────────────────────────────────────┤
│         PostgreSQL 16  │  Redis 7                    │
└─────────────────────────────────────────────────────┘
```

Key patterns:
- One DB schema per service (12 schemas, isolated credentials)
- Outbox pattern for event-driven communication
- Internal service auth for all cross-service calls
- API gateway as single public entry point

---

## What Is NOT in MVP

These are **intentional scope decisions**, not gaps:

- No approval flow (human-in-the-loop) — state machine defined, not wired
- No taint/lineage enforcement — provenance tracked, propagation deferred
- No artifact delivery/download/export endpoints
- No autoscaling or multi-region deployment
- No distributed tracing export (correlation IDs flow, no backend)
- No mTLS between services (internal auth via shared secret)
- No load testing under realistic concurrency
- No external security audit

The full deferred backlog is in `docs/deferred-backlog.md`, organized by
category (product extensions, hardening, cloud/HA, performance, UX,
architectural gaps) with HIGH/MEDIUM/LOW priority guidance.

---

## How to Deploy

Three profiles are available (all commands run from `infra/docker/`):

| Profile | Use Case | Command |
|---------|----------|---------|
| **local** | Development, debugging | `docker compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.local up -d` |
| **hardened** | Staging, CI, demo | `docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d` |
| **cloud** | Production deployment | `docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d` |

Full deployment instructions: `docs/runbook-go-live.md`

---

## How to Evaluate

1. **Read the docs** — start at `docs/docs-index.md`
2. **Run the tests** — `python -m pytest tools/arch-test/ -v`
3. **Deploy locally** — follow `docs/runbook-go-live.md`
4. **Check health** — all 15 services expose `/healthz`
5. **Review limitations** — `docs/deferred-backlog.md`

---

## Recommended Next Steps

Before production use with real users:

1. Load testing under expected concurrency
2. Distributed tracing export to observability backend
3. Artifact delivery/download feature
4. Security audit by external reviewer
5. PostgreSQL `max_connections` tuning for service pool sizes

See `docs/deferred-backlog.md` for the complete prioritized backlog.

---

## Contact

This announcement covers the state of Keviq Core at tag `mvp-ready`.
For questions, start with `docs/docs-index.md` — it has role-based
reading paths for operators, developers, and architecture reviewers.
