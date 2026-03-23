# Keviq Core — Documentation Index

Start here. This page maps all documentation and provides reading paths
for operators, developers, and architecture reviewers.

---

## Quick Start by Role

### Operator (deploy and run Keviq Core)

1. [MVP Release Readiness](mvp-release-readiness.md) — what the system does, current status
2. [Go-Live Runbook](runbook-go-live.md) — deployment profiles, startup, monitoring, recovery
3. [Known Limitations](deferred-backlog.md) — what is not in MVP

### Developer (contribute to Keviq Core)

1. This index — understand the doc structure
2. [Product Vision](00-product-vision.md) — what Keviq Core is and who it serves
3. [System Goals](01-system-goals-and-non-goals.md) — G1-G10 goals, N1-N7 non-goals
4. [Repo Structure](16-repo-structure-conventions.md) — naming conventions, PR checklist
5. [Implementation Roadmap](17-implementation-roadmap.md) — phases, slices, pressure points
6. [Backend Service Map](15-backend-service-map.md) — which service does what
7. [Frontend Application Map](14-frontend-application-map.md) — frontend architecture

### Architecture Reviewer

1. [Architectural Invariants](02-architectural-invariants.md) — I1-I15 invariants
2. [Bounded Contexts](03-bounded-contexts.md) — C1-C11 service boundaries
3. [Core Domain Model](04-core-domain-model.md) — entities and ownership
4. [State Machines](05-state-machines.md) — lifecycle state diagrams
5. [Architecture Gate Review](architecture-gate-review-00-12.md) — cross-doc consistency audit
6. [Workspace Isolation Model](phase-d-pr44-isolation-model.md) — multi-tenant design

---

## Full Document Map

### Architecture Constitution (docs 00-12)

These documents define the system's design and constraints. They were written
before any implementation code and serve as the authoritative source of truth.

| Doc | Title | Purpose |
|-----|-------|---------|
| [00](00-product-vision.md) | Product Vision | What Keviq Core is, target users, use cases |
| [01](01-system-goals-and-non-goals.md) | System Goals & Non-Goals | G1-G10 goals, N1-N7 non-goals |
| [02](02-architectural-invariants.md) | Architectural Invariants | I1-I15 rules that must never be violated |
| [03](03-bounded-contexts.md) | Bounded Contexts | C1-C11 service boundaries and responsibilities |
| [04](04-core-domain-model.md) | Core Domain Model | Entity definitions, ownership, relationships |
| [05](05-state-machines.md) | State Machines | Lifecycle diagrams for Task, Run, Step, etc. |
| [06](06-event-contracts.md) | Event Contracts | Event types, envelope schema, naming |
| [07](07-api-contracts.md) | API Contracts | REST API specifications per service |
| [08](08-sandbox-security-model.md) | Sandbox Security Model | Execution environment isolation |
| [09](09-permission-model.md) | Permission Model | RBAC, fail-closed auth, policy enforcement |
| [10](10-artifact-lineage-model.md) | Artifact & Lineage Model | Provenance tracking, lineage DAG |
| [11](11-observability-model.md) | Observability Model | Spans, traces, metrics design |
| [12](12-failure-recovery-model.md) | Failure & Recovery Model | Crash recovery, error handling |
| [13](13-deployment-topology.md) | Deployment Topology | Local/cloud/hybrid infrastructure |

### Application Architecture (docs 14-17)

| Doc | Title | Purpose |
|-----|-------|---------|
| [14](14-frontend-application-map.md) | Frontend Application Map | React/Next.js architecture, state isolation |
| [15](15-backend-service-map.md) | Backend Service Map | 15 services: roles, ports, dependencies |
| [16](16-repo-structure-conventions.md) | Repo Structure & Conventions | Naming, patterns, monorepo layout, PR checklist |
| [17](17-implementation-roadmap.md) | Implementation Roadmap | Phases A-D, slices 1-6, pressure points PP1-PP10 |

### Gate Reviews and Phase Tracking

| Doc | Purpose |
|-----|---------|
| [Architecture Gate Review](architecture-gate-review-00-12.md) | Cross-document consistency audit, gaps, do-not-break list |

### Slice Documentation (Phase B)

Each slice has up to 3 documents: implementation contract, gate note, closeout.

| Slice | Topic | Docs |
|-------|-------|------|
| Slice 1 | Auth + Workspace + Policy | [contract](slice-1-implementation-contract.md), [gate](slice-1-gate-note.md) |
| Slice 2 | Task → Orchestrator → Event | [contract](slice-2-implementation-contract.md), [gate](slice-2-gate-note.md), [closeout](slice-2-closeout.md) |
| Slice 3 | Run/Step Lifecycle | [gate](slice-3-gate-note.md), [closeout](slice-3-closeout.md) |
| Slice 4 | Model Gateway + Agent | [contract](slice-4-implementation-contract.md), [pr20](slice-4-pr20-contract.md), [gate](slice-4-gate-note.md), [closeout](slice-4-closeout.md) |
| Slice 5 | Artifact + Lineage | [contract](slice-5-implementation-contract.md), [gate](slice-5-gate-note.md), [closeout](slice-5-closeout.md) |
| Slice 6 | Frontend Shell | [contract](slice-6-implementation-contract.md), [gate](slice-6-gate-note.md), [closeout](slice-6-closeout.md) |

### Phase D: Deployment Maturity

| Doc | Purpose |
|-----|---------|
| [Workspace Isolation Model](phase-d-pr44-isolation-model.md) | Multi-workspace isolation guarantees and known limitations |

### Operational Documentation

| Doc | Purpose |
|-----|---------|
| [Go-Live Runbook](runbook-go-live.md) | Deployment, startup, monitoring, backup, rollback, scaling |
| [MVP Release Readiness](mvp-release-readiness.md) | Current status, what works, known limitations |
| [Deferred Backlog](deferred-backlog.md) | What is not in MVP, organized by category and priority |
| [MVP Announcement](mvp-announcement.md) | Internal release announcement for the MVP milestone |
| [Handoff Summary](handoff-summary.md) | Onboarding guide for new team members receiving the codebase |

---

## Phase Completion Status

| Phase | PRs | Status | Key Milestone |
|-------|-----|--------|---------------|
| **A** | PR1–PR12 | COMPLETE | 15 service skeletons, DB schemas, arch tests |
| **B** | PR13–PR36 | COMPLETE | 6 vertical slices, end-to-end flows proven |
| **C** | PR37–PR42 | COMPLETE | Security hardening, concurrency, performance |
| **D** | PR43–PR45 | COMPLETE | Deployment profiles, isolation, ops validation |
| **Closeout** | PR46 | COMPLETE | Release readiness docs, deferred backlog |

**Total:** 46 PRs, 850+ architecture gate tests passing

---

## Architecture Test Coverage

All gate tests are in `tools/arch-test/`. Run with:

```bash
python -m pytest tools/arch-test/ -v
```

| Test File | Gate | Tests |
|-----------|------|-------|
| `test_import_boundaries.py` | Import layer enforcement | 30 |
| `test_pp1_state_transition_authority.py` | PP1: state machines | 6 |
| `test_pp10_db_privilege.py` | PP10: DB isolation | 14 |
| `test_pr37_internal_auth.py` | Internal service auth | 54 |
| `test_pr38_container_hardening.py` | Container security | 92 |
| `test_pr39_concurrency_recovery.py` | Concurrency safety | 18 |
| `test_pr40_async_retry.py` | Async execution | 27 |
| `test_pr41_layering_enforcement.py` | Service layering | 40 |
| `test_pr42_perf_readiness.py` | Performance bounds | 65 |
| `test_pr43_deployment_readiness.py` | Deployment profiles | 51 |
| `test_pr44_workspace_isolation.py` | Workspace isolation | 49 |
| `test_pr45_operational_readiness.py` | Operational validation | 97 |
| `test_pr46_project_closeout.py` | Release readiness gates | 68 |
| `test_slice*` | Slice contracts + integration | ~190 |

---

## Recommended Milestone Tags

| Tag | Commit | Meaning |
|-----|--------|---------|
| `phase-a-verified` | `9d5a0a4` | Phase A foundation complete |
| `mvp-ready` | `0ad0c12` | MVP operationally ready |

---

## Repository Layout

```
keviq-core/
├── apps/                    # 15 backend services + web frontend
│   ├── orchestrator/        # Task/Run/Step lifecycle
│   ├── agent-runtime/       # Agent invocation + model calls
│   ├── artifact-service/    # Artifact storage + lineage
│   ├── execution-service/   # Sandbox + tool execution
│   ├── event-store/         # Append-only event store + SSE
│   ├── workspace-service/   # Workspace + membership RBAC
│   ├── api-gateway/         # Public API proxy + auth
│   ├── sse-gateway/         # Real-time event gateway
│   ├── auth-service/        # JWT authentication
│   ├── policy-service/      # Permission evaluation
│   ├── model-gateway/       # LLM provider abstraction
│   ├── secret-broker/       # Secret storage
│   ├── audit-service/       # Audit log
│   ├── notification-service/# Event-driven notifications
│   ├── telemetry-service/   # Metrics collection
│   └── web/                 # Next.js frontend
├── packages/                # Shared packages
│   └── config/              # Deployment metadata, env helpers
├── tools/
│   └── arch-test/           # Architecture gate tests (850+)
├── infra/
│   └── docker/              # Compose files, env templates
└── docs/                    # Architecture + operational docs
```
