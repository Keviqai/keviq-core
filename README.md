<p align="center">
  <img src="apps/web/public/logo.png" alt="Keviq Core" width="80" />
</p>

<h1 align="center">Keviq Core</h1>

<p align="center">
  <strong>Open-source infrastructure for running AI agents in production.</strong><br/>
  The missing control plane between your agent framework and your organization.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/services-15_microservices-blueviolet" alt="15 Services" /></a>
  <a href="#current-status"><img src="https://img.shields.io/badge/tests-1546_passing-brightgreen" alt="Tests" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/docker_compose_up-2496ED?logo=docker&logoColor=white" alt="Docker" /></a>
</p>

<p align="center">
  <a href="#the-problem">Why this exists</a> &nbsp;&bull;&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;&bull;&nbsp;
  <a href="#architecture">Architecture</a> &nbsp;&bull;&nbsp;
  <a href="ROADMAP.md">Roadmap</a> &nbsp;&bull;&nbsp;
  <a href="docs/docs-index.md">Docs</a> &nbsp;&bull;&nbsp;
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

---

## The Problem

Every team building with AI agents hits the same infrastructure wall.

You can build a working agent in an afternoon with LangChain, CrewAI, or AutoGen. But putting that agent into production — where real users depend on it, real data flows through it, and real decisions get made — requires solving a set of hard infrastructure problems that **no agent framework addresses**:

**1. Agents produce outputs nobody can trace.**
An agent writes a report, modifies a codebase, or generates a financial analysis. Three weeks later, someone asks: "Which model version produced this? What data did it use? Who approved it?" Without provenance infrastructure, the answer is "we don't know."

**2. There is no safe way to let agents act autonomously.**
Today it's all-or-nothing: either you give the agent full access and hope for the best, or you don't deploy it. There's no standard infrastructure for "pause here, get human approval, then continue" — the way CI/CD systems solved this for code deployment years ago.

**3. Every team rebuilds the same platform from scratch.**
Auth, RBAC, multi-tenancy, secret management, rate limiting, audit logging, event bus, health checks, metrics, a web dashboard — this is 6+ months of infrastructure work before you write a single line of agent logic. And every team builds it differently, poorly, or not at all.

**4. Agent outputs are second-class citizens.**
Outputs end up in chat logs, temp directories, or S3 buckets with no metadata. There's no unified system for versioning, searching, comparing, annotating, or tracing the lineage of what agents produce — the way Git solved this for source code.

These aren't theoretical problems. They're the reason most AI agent projects stall between "impressive demo" and "trusted production system."

---

## What Keviq Core Does

Keviq Core is the **infrastructure layer** that sits between your agent framework and your users. It's not another way to build agents — it's the production platform they run on.

```
┌──────────────────────────────────────────────────────┐
│                    Your Agent Logic                   │
│           (LangChain, CrewAI, AutoGen, custom)        │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│                   KEVIQ CORE                          │
│                                                       │
│  Task Orchestration    Artifact Management            │
│  ├─ Task → Run → Step  ├─ Versioned outputs           │
│  ├─ Retries, timeouts  ├─ Full provenance chain       │
│  └─ State machines      └─ Lineage, search, tags      │
│                                                       │
│  Human-in-the-Loop     Platform Infrastructure        │
│  ├─ Approval gates      ├─ Auth + RBAC + workspaces   │
│  ├─ Review workflows    ├─ Secret management          │
│  └─ Real-time SSE       ├─ Audit log (every action)   │
│                         ├─ Prometheus + Grafana        │
│                         └─ Rate limiting, health       │
│                                                       │
│  Web UI (21 pages) ─── API Gateway ─── Event Bus      │
└───────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│              PostgreSQL + Redis                        │
│        (13 isolated schemas, outbox pattern)           │
└───────────────────────────────────────────────────────┘
```

### Core capabilities

| Capability | What it solves |
|-----------|---------------|
| **Task orchestration** | Define work as structured tasks (not prompts). The orchestrator manages the lifecycle: scheduling, retries, cancellation, dependency resolution. Every task produces a traceable chain: Task → Run → Steps → Artifacts. |
| **Artifact provenance** | Every output is a first-class artifact with metadata, ownership, version history, and a provenance chain linking it back to the exact agent, model, task, and inputs that produced it. Search across artifacts by 10+ parameters. |
| **Human approval gates** | Pause agent execution at critical decision points. Route approval requests to specific reviewers. Resume or reject with full audit trail. The pattern CI/CD uses for deployments, applied to AI agent actions. |
| **Multi-tenant workspaces** | Isolated environments with membership, roles, and capability-based RBAC. Teams share infrastructure without sharing data or permissions. |
| **Execution sandboxing** | Agent tool calls execute in policy-driven sandbox environments with resource quotas, network policies, and cleanup semantics. |
| **Secret management** | Encrypted credential storage with versioned key rotation. Agents access secrets through the broker — never directly. |
| **Full observability** | Prometheus metrics on all 15 services. Grafana dashboards included. Real-time SSE event streams (35+ event types). Structured audit logging for every state change. |
| **Production-ready API** | JWT auth, internal service auth, rate limiting (tiered: read/write/global), health checks on every service. One API gateway handles routing, auth validation, and workspace isolation. |

### How it compares

| | Agent Frameworks<br/>(LangChain, CrewAI) | Chat Platforms<br/>(Dify, FlowiseAI) | **Keviq Core** |
|---|---|---|---|
| Agent reasoning | Built-in | Visual builder | **Bring your own** |
| Task orchestration | None | Basic chains | **Full lifecycle** (Task→Run→Step) |
| Artifact provenance | None | None | **First-class** with lineage |
| Human approval gates | None | None | **Built-in** with review workflows |
| Multi-tenancy + RBAC | None | Basic | **Workspace-level** with capabilities |
| Audit trail | None | Partial | **Every action logged** |
| Observability | None | Basic | **Prometheus + Grafana** on all services |
| Self-hosted | N/A | Yes | **Yes** (Docker Compose or K8s) |
| Architecture | Library | Monolith | **15 microservices** (independent scaling) |

**Keviq Core is not a replacement for agent frameworks.** It's the infrastructure those frameworks need to run in production. Use LangChain to build your agent's reasoning. Use Keviq Core to deploy, observe, govern, and trust it.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- [Node.js 22+](https://nodejs.org/) & [pnpm](https://pnpm.io/) (frontend dev)
- 8 GB RAM minimum (16 GB recommended)

### 1. Clone & configure

```bash
git clone https://github.com/Keviqai/keviq-core.git && cd keviq-core
cp infra/docker/.env.example infra/docker/.env.local
```

### 2. Start the platform

```bash
./scripts/bootstrap.sh
```

Boots PostgreSQL + Redis, runs 13 schema migrations, starts 18 containers. Takes ~60 seconds from zero.

### 3. Create a user

```bash
curl -s -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme123","display_name":"Admin"}'
```

Open **http://localhost:3000** — log in and create your first workspace.

### 4. Verify

```bash
./scripts/smoke-test.sh    # 21 automated checks
```

> **Deploying for real?** Follow the [Production Deployment Checklist](docs/ops/production-deployment-checklist.md) — covers secret rotation, resource sizing, health verification, and operational runbooks.

---

## Architecture

15 Python/FastAPI microservices. Each owns its own PostgreSQL schema. Services communicate via outbox pattern + Redis Streams — no direct service-to-service calls for state mutations.

```
                         ┌─────────────┐
                         │   Next.js   │   21 pages, React 19
                         │  Frontend   │   TanStack Query + Zustand
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ API Gateway │   JWT auth, routing, rate limiting
                         └──────┬──────┘
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼───┐    ┌───────▼──────┐   ┌──────▼───────┐
     │   Control   │    │    Domain    │   │Infrastructure │
     │             │    │              │   │               │
     │ auth        │    │ orchestrator │   │ event-store   │
     │ policy      │    │ agent-runtime│   │ model-gateway │
     │ workspace   │    │ artifact-svc │   │ audit-service │
     │             │    │ execution-svc│   │ notification  │
     │             │    │              │   │ secret-broker │
     │             │    │              │   │ telemetry     │
     │             │    │              │   │ sse-gateway   │
     └─────────────┘    └──────────────┘   └───────────────┘
              │                 │                  │
              └─────────────────┼─────────────────┘
                         ┌──────▼──────┐
                         │ PostgreSQL  │   13 schemas (1 per service)
                         │   + Redis   │   event bus + cache
                         └─────────────┘
```

| Layer | Services | Responsibility |
|-------|----------|----------------|
| **API Surface** | api-gateway, sse-gateway | Auth, routing, rate limiting, real-time event streaming |
| **Control** | auth, policy, workspace | Identity, RBAC, multi-tenant isolation |
| **Domain** | orchestrator, agent-runtime, artifact, execution | Task lifecycle, agent tool loops, artifact CRUD + provenance, sandboxed execution |
| **Infrastructure** | event-store, model-gateway, audit, notification, secret-broker, telemetry | Event sourcing, LLM routing, audit trail, alerts, encrypted secrets, metrics |

> **18 architecture specification documents** cover every design decision. See the [Architecture Overview](docs/architecture-overview.md) for a visual introduction or the [Documentation Index](docs/docs-index.md) for the full set.

### Key design decisions

- **One schema per service** — enforced by architecture tests. No shared tables, no cross-schema joins.
- **Outbox pattern** — services write events to a local outbox table, a relay publishes to Redis Streams. Guarantees at-least-once delivery without distributed transactions.
- **Capability-based RBAC** — permissions are capabilities (e.g., `task:create`, `artifact:upload`), not rigid roles. Policies bind capabilities to workspace members.
- **910 architecture tests** — invariants are enforced in CI, not just documented. Tests verify import boundaries, schema isolation, API contracts, and security properties.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| Frontend | TypeScript, Next.js 15, React 19, TanStack Query, Zustand |
| Database | PostgreSQL 16 (multi-schema) |
| Event Bus | Redis 7 Streams + outbox pattern |
| Monorepo | pnpm workspaces + Turborepo |
| Infrastructure | Docker Compose (local), Kubernetes-ready |
| Observability | Prometheus + Grafana (dashboards included) |
| Testing | pytest (unit + arch), Playwright (E2E), k6 (load) |

---

## Project Structure

```
keviq-core/
├── apps/                  # 15 backend services + Next.js frontend
│   ├── api-gateway/       #   routing, auth, rate limiting
│   ├── orchestrator/      #   task lifecycle, run management
│   ├── agent-runtime/     #   agent execution, tool loops, guardrails
│   ├── artifact-service/  #   artifact CRUD, provenance, lineage, search
│   ├── execution-service/ #   sandboxed code/tool execution
│   ├── auth-service/      #   JWT auth, registration, token refresh
│   ├── workspace-service/ #   multi-tenancy, membership
│   ├── policy-service/    #   capability-based RBAC
│   ├── event-store/       #   event sourcing, timeline, SSE
│   ├── model-gateway/     #   LLM provider proxy
│   ├── web/               #   Next.js 15 frontend (21 pages)
│   └── ...                #   4 more services
├── packages/              # 14 shared packages
│   ├── api-client/        #   type-safe API client
│   ├── domain-types/      #   shared TypeScript types
│   ├── server-state/      #   React Query hooks
│   ├── routing/           #   URL builders
│   └── ...                #   10 more packages
├── tools/arch-test/       # 910 architecture enforcement tests
├── infra/                 # Docker Compose, Grafana, Prometheus configs
├── scripts/               # bootstrap, smoke-test, clean-boot
├── docs/                  # 18 architecture specs + ops guides
└── tests/e2e/             # Playwright E2E + k6 load tests
```

---

## Development

```bash
./scripts/bootstrap.sh           # Full start (infra + migrations + services)
./scripts/bootstrap.sh migrate   # Migrations only
./scripts/bootstrap.sh up        # Services only
./scripts/smoke-test.sh          # 21 automated checks
./scripts/clean-boot-test.sh     # Tear down everything, rebuild, verify

python -m pytest tools/arch-test/ -v    # 910 architecture tests
cd apps/web && pnpm dev                 # Frontend dev server (port 3000)
```

| Port | Service |
|------|---------|
| 3000 | Frontend (Next.js) |
| 8080 | API Gateway |
| 8001–8016 | Individual backend services |
| 5434 | PostgreSQL |
| 6379 | Redis |

---

## Current Status

| Metric | Value |
|--------|-------|
| Backend services | 14/15 domain-functional, 1 stub (sse-gateway) |
| User journeys | 21/21 verified end-to-end |
| Unit tests | 636 passing |
| Architecture tests | 910 passing |
| E2E tests | 12 Playwright specs |
| Load tests | k6 scripts (auth, task creation, concurrent writes) |
| Frontend | 21 data-driven pages |
| Observability | All 15 services expose `/metrics` |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/architecture-overview.md) | Visual introduction with Mermaid diagram — start here |
| [Documentation Index](docs/docs-index.md) | Navigation hub for all 18 architecture specs |
| [Architectural Invariants](docs/02-architectural-invariants.md) | 15 rules the system must never violate |
| [API Contracts](docs/07-api-contracts.md) | Full REST API specification |
| [State Machines](docs/05-state-machines.md) | Task, run, artifact lifecycle models |
| [Sandbox Security](docs/08-sandbox-security-model.md) | Execution isolation model |
| [Permission Model](docs/09-permission-model.md) | Capability-based RBAC design |
| [Artifact Lineage](docs/10-artifact-lineage-model.md) | Provenance and derivation tracking |
| [Production Checklist](docs/ops/production-deployment-checklist.md) | Deployment, secrets, monitoring |
| [Observability Guide](docs/ops/observability.md) | Prometheus + Grafana setup |
| [Coding Standards](docs/CODING-RULES.md) | Contributor code conventions |

---

## Roadmap

Keviq Core is under active development. The roadmap has four phases:

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Hardened Platform — K8s, CI/CD, OpenTelemetry, distributed rate limiting | **In progress** |
| **Phase 2** | Agent SDK — `pip install keviq` / `npm install @keviq/sdk` | Design |
| **Phase 3** | Plugin System — agent plugins, tool plugins, storage/auth/notification extensions | Concept |
| **Phase 4** | Ecosystem — federation, marketplace, AI infra primitives (memory, RAG, eval, cost tracking) | Future |

Read the full **[ROADMAP.md](ROADMAP.md)** for details, code examples, and extension point specifications.

---

## Start Contributing

New here? Pick a **[good first issue](https://github.com/Keviqai/keviq-core/labels/good%20first%20issue)** and follow the **[Your First Contribution](docs/community/your-first-contribution.md)** guide.

Three setup paths depending on what you're changing:
- **Docs only** — just Git, no setup needed
- **Frontend** — Node + pnpm, no Docker
- **Backend** — full Docker stack (~60 seconds to boot)

See [CONTRIBUTING.md](CONTRIBUTING.md) for code standards, testing, and PR process.

Key constraints:
- Each service owns its own schema — no cross-service imports
- Architecture tests must pass — they enforce invariants in CI
- Files < 300 lines, functions < 50 lines, route handlers < 80 lines

---

## Security

Report vulnerabilities responsibly — see [SECURITY.md](SECURITY.md).

---

## License

[MIT](LICENSE)
