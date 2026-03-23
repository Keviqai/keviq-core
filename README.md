<p align="center">
  <img src="apps/web/public/logo.png" alt="Keviq Core" width="80" />
</p>

<h1 align="center">Keviq Core</h1>

<p align="center">
  <strong>The open-source operating system for AI agents.</strong><br/>
  Orchestrate tasks. Run agents. Manage artifacts — with full provenance, permissions, and observability.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/services-15-blueviolet" alt="15 Services" /></a>
  <a href="#current-status"><img src="https://img.shields.io/badge/tests-1546_passing-brightgreen" alt="Tests" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/docker-compose_up-2496ED?logo=docker&logoColor=white" alt="Docker" /></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &nbsp;&bull;&nbsp;
  <a href="#features">Features</a> &nbsp;&bull;&nbsp;
  <a href="#architecture">Architecture</a> &nbsp;&bull;&nbsp;
  <a href="docs/docs-index.md">Documentation</a> &nbsp;&bull;&nbsp;
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## What is Keviq Core?

Keviq Core is a **self-hosted platform** for running AI agents as structured, observable work — not chat threads. It provides the control plane, execution environment, and audit trail that teams need to deploy AI agents in production.

Think of it as **Kubernetes for AI workflows**: you define tasks, the system orchestrates agent runs, tracks every artifact with full provenance, and gives humans approval gates at critical decision points.

### Who is this for?

- **Teams deploying AI agents** who need governance, audit trails, and human-in-the-loop controls
- **Platform engineers** building internal AI tooling on a proven microservices foundation
- **Developers** who want a production-ready agent orchestration stack they can self-host and extend

---

## Features

### Agent Orchestration
- **Task-driven execution** — define work as tasks, not prompts. Tasks spawn runs, runs execute steps, steps produce artifacts
- **Multi-agent coordination** — orchestrator manages task graphs, dependencies, retries, and cancellation
- **Tool execution loop** — agents call tools in sandboxed environments with budget limits and guardrails
- **Model gateway** — route to any OpenAI-compatible LLM (OpenAI, Azure, vLLM, Ollama) through a unified proxy

### Human-in-the-Loop
- **Approval gates** — require human approval before sensitive agent actions execute
- **Review workflows** — assign reviewers, track approval decisions, get notified on outcomes
- **Real-time observation** — watch agent execution live via SSE streams with 35+ event types

### Artifact Management
- **First-class artifacts** — every output is a versioned, typed artifact with metadata and ownership
- **Full provenance** — track which agent, task, run, and step produced each artifact
- **Lineage graph** — trace artifact derivation chains across workflows
- **Search & tags** — filter by 10+ parameters, tag artifacts for organization
- **Preview & export** — inline preview, diff view, annotations, and bulk export

### Platform & Security
- **Multi-tenant workspaces** — isolated environments with membership and role-based access
- **Capability-based RBAC** — fine-grained permissions at the workspace level
- **Secret management** — encrypted storage with versioned key rotation
- **Audit logging** — every state change is recorded and queryable
- **Observability** — Prometheus metrics on all 15 services, Grafana dashboards included

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- [Node.js 22+](https://nodejs.org/) & [pnpm](https://pnpm.io/) (for frontend dev)
- 8 GB RAM minimum (16 GB recommended)

### 1. Clone & configure

```bash
git clone https://github.com/Keviqai/keviq-core.git && cd keviq-core
cp infra/docker/.env.example infra/docker/.env.local
```

### 2. Start everything

```bash
./scripts/bootstrap.sh
```

This boots PostgreSQL, Redis, runs migrations across 13 schemas, and starts all 18 containers.

### 3. Create a user & open the UI

```bash
curl -s -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme123","display_name":"Admin"}'
```

Open **http://localhost:3000** and log in.

### 4. Verify

```bash
./scripts/smoke-test.sh    # 21 automated checks
```

> **Production?** See the [Production Deployment Checklist](docs/ops/production-deployment-checklist.md).

---

## Architecture

Keviq Core is a **microservices platform** — 15 Python/FastAPI services communicating via an outbox pattern + Redis Streams event bus. Each service owns its own PostgreSQL schema.

```
                         ┌─────────────┐
                         │   Next.js   │
                         │  Frontend   │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ API Gateway │  auth + routing + rate limiting
                         └──────┬──────┘
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼───┐    ┌───────▼──────┐   ┌──────▼───────┐
     │   Control   │    │    Domain    │   │ Infrastructure│
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
                         │ PostgreSQL  │  13 schemas (1 per service)
                         │   + Redis   │  event bus + cache
                         └─────────────┘
```

| Layer | Services | Role |
|-------|----------|------|
| **API Surface** | api-gateway, sse-gateway | Auth, routing, rate limiting, SSE streaming |
| **Control** | auth, policy, workspace | Identity, RBAC, tenant isolation |
| **Domain** | orchestrator, agent-runtime, artifact, execution | Task lifecycle, agent loops, artifact management, sandboxed execution |
| **Infrastructure** | event-store, model-gateway, audit, notification, secret-broker, telemetry | Events, LLM routing, audit trail, alerts, secrets, metrics |

> **18 architecture specification documents** available in [`docs/`](docs/docs-index.md).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Frontend | TypeScript, Next.js 15, React 19, TanStack Query, Zustand |
| Database | PostgreSQL 16 (multi-schema, one per service) |
| Event Bus | Redis 7 Streams + outbox pattern |
| Monorepo | pnpm workspaces + Turborepo |
| Containers | Docker Compose (local), Kubernetes-ready |
| Observability | Prometheus metrics, Grafana dashboards |

---

## Project Structure

```
keviq-core/
├── apps/                  # 15 backend services + Next.js frontend
│   ├── api-gateway/       #   API routing, auth, rate limiting
│   ├── orchestrator/      #   Task lifecycle, run management
│   ├── agent-runtime/     #   Agent execution, tool loops
│   ├── artifact-service/  #   Artifact CRUD, provenance, lineage
│   ├── execution-service/ #   Sandboxed code execution
│   ├── web/               #   Next.js 15 frontend (21 pages)
│   └── ...                #   10 more services
├── packages/              # 14 shared packages
│   ├── api-client/        #   Type-safe API client
│   ├── domain-types/      #   Shared TypeScript types
│   ├── server-state/      #   React Query hooks
│   └── ...                #   11 more packages
├── tools/                 # Architecture tests, codegen, migrations
├── infra/                 # Docker Compose, Grafana, Prometheus
├── scripts/               # bootstrap.sh, smoke-test.sh
├── docs/                  # 18 architecture specification docs
└── tests/                 # E2E tests (Playwright)
```

---

## Development

```bash
# Full bootstrap (first time)
./scripts/bootstrap.sh

# Migrations only
./scripts/bootstrap.sh migrate

# Start services only
./scripts/bootstrap.sh up

# Smoke test (21 checks)
./scripts/smoke-test.sh

# Architecture tests (910 tests)
python -m pytest tools/arch-test/ -v

# Frontend dev server
cd apps/web && pnpm dev

# View service logs
cd infra/docker && docker compose -f docker-compose.yml \
  -f docker-compose.local.yml --env-file .env.local logs -f <service>

# Clean boot from zero (tears down everything, rebuilds, verifies)
./scripts/clean-boot-test.sh
```

### Local Ports

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Gateway | http://localhost:8080 |
| PostgreSQL | localhost:5434 |
| Redis | localhost:6379 |
| Individual services | localhost:8001–8016 |

---

## Current Status

| Metric | Value |
|--------|-------|
| Backend services | 14/15 domain-functional |
| User journeys | 21/21 verified |
| Unit tests | 636 passing |
| Architecture tests | 910 passing |
| Frontend pages | 21 data-driven pages |
| Prometheus metrics | All 15 services instrumented |

The platform is **pilot-ready** for small deployments (1–5 users, single Docker host). See the [Production Deployment Checklist](docs/ops/production-deployment-checklist.md) for operational guidance.

---

## External Dependencies

| Dependency | Required? | Notes |
|-----------|-----------|-------|
| Docker + Compose v2 | Yes | Runs all 18 containers locally |
| LLM API (OpenAI-compatible) | Optional | For agent execution. Supports OpenAI, Azure, vLLM, Ollama |
| GPU | No | model-gateway is a proxy, not an inference engine |
| Cloud services | No | Runs fully local |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Index](docs/docs-index.md) | Navigation hub for all 18 spec docs |
| [API Contracts](docs/07-api-contracts.md) | Full API specification |
| [Production Checklist](docs/ops/production-deployment-checklist.md) | Deployment & operations guide |
| [Observability](docs/ops/observability.md) | Prometheus + Grafana setup |
| [Security Model](docs/08-sandbox-security-model.md) | Sandbox & execution security |
| [Coding Standards](docs/CODING-RULES.md) | Code style & conventions |
| [Testing Standards](docs/TESTING-RULES.md) | Test strategy & rules |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup & standards
- Code style (Python: snake_case + type hints, TypeScript: strict mode)
- Commit conventions
- Pull request process

---

## Security

Found a vulnerability? Please report it responsibly — see [SECURITY.md](SECURITY.md).

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
