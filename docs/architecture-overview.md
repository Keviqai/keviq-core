# Architecture Overview

> A quick visual guide for new contributors. For the full specification, see the
> [Documentation Index](docs-index.md) (18 architecture documents).

---

## At a Glance

Keviq Core is a **microservices platform** (15 Python/FastAPI services + 1 Next.js frontend)
for running AI agents in production. Services communicate via an **outbox pattern** over
Redis Streams — no direct service-to-service calls for state mutations. Each service owns
its own PostgreSQL schema; there are no shared tables or cross-schema joins.

```mermaid
graph TB
    subgraph Frontend["Web Tier"]
        WEB["Next.js Frontend<br/>21 pages · React 19"]
    end

    subgraph Gateway["API Surface"]
        APIGW["API Gateway<br/>JWT auth · routing · rate limiting"]
    end

    subgraph Control["Control Plane"]
        AUTH["Auth Service<br/>users · JWT · sessions"]
        POLICY["Policy Service<br/>capability-based RBAC"]
        WORKSPACE["Workspace Service<br/>multi-tenant isolation"]
    end

    subgraph Domain["Domain Services"]
        ORCH["Orchestrator<br/>Task → Run → Step lifecycle"]
        AGENT["Agent Runtime<br/>model loop · tool dispatch"]
        ARTIFACT["Artifact Service<br/>storage · lineage · provenance"]
        EXEC["Execution Service<br/>sandboxed tool execution"]
    end

    subgraph Infra["Infrastructure Services"]
        EVENTSTORE["Event Store<br/>append-only log · SSE streaming"]
        MODELGW["Model Gateway<br/>LLM provider routing"]
        AUDIT["Audit Service<br/>action audit trail"]
        NOTIF["Notification Service<br/>delivery + retry"]
        SECRET["Secret Broker<br/>encrypted secrets"]
        TELEMETRY["Telemetry Service<br/>Prometheus metrics"]
    end

    subgraph Storage["Storage Layer"]
        PG["PostgreSQL 16<br/>13 isolated schemas"]
        REDIS["Redis 7<br/>event bus · cache"]
    end

    WEB -->|HTTP| APIGW
    APIGW --> AUTH
    APIGW --> POLICY
    APIGW --> ORCH
    APIGW --> ARTIFACT
    APIGW --> WORKSPACE
    APIGW -->|timeline, activity, SSE| EVENTSTORE

    ORCH -->|dispatch| AGENT
    AGENT -->|model call| MODELGW
    AGENT -->|store output| ARTIFACT
    AGENT -->|run tool| EXEC
    EXEC -->|fetch secret| SECRET

    ORCH -->|outbox| REDIS
    AGENT -->|outbox| REDIS
    ARTIFACT -->|outbox| REDIS
    REDIS -->|relay| EVENTSTORE
    EVENTSTORE -->|consumed by| AUDIT

    Control -->|read/write| PG
    Domain -->|read/write| PG
    Infra -->|read/write| PG

    style Frontend fill:#e1f5fe,stroke:#0288d1
    style Gateway fill:#f3e5f5,stroke:#7b1fa2
    style Control fill:#fff3e0,stroke:#ef6c00
    style Domain fill:#e8f5e9,stroke:#2e7d32
    style Infra fill:#fce4ec,stroke:#c62828
    style Storage fill:#f1f8e9,stroke:#558b2f
```

---

## Service Groups

### Control Plane — identity and policy
**Auth**, **Policy**, and **Workspace** services handle user identity, capability-based
RBAC, and multi-tenant workspace isolation. Every request passes through the API Gateway,
which validates JWT tokens and resolves workspace membership before forwarding.

### Domain Services — core logic
The **Orchestrator** manages the task lifecycle (Task → Run → Steps). When a run starts,
it dispatches to the **Agent Runtime**, which drives a model-call → tool-call loop. Tool
calls execute in the **Execution Service** sandbox. Outputs are stored as first-class
artifacts in the **Artifact Service** with full provenance chains.

### Infrastructure Services — supporting concerns
The **Event Store** persists all domain events (append-only) and serves real-time SSE
streams for run progress and activity feeds. The **Model Gateway** proxies LLM calls to
configurable providers. **Audit**, **Notification**, **Secret Broker**, and **Telemetry**
services handle cross-cutting concerns without coupling to domain logic.

> **Note:** A separate `sse-gateway` service exists in the repo but is currently a stub
> (health endpoints only). All real-time streaming is handled by `event-store` today.

---

## Key Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **Outbox + relay** | Every service with mutations | Guarantees at-least-once event delivery without distributed transactions. Services write to a local outbox table; a relay publishes to Redis Streams. |
| **Schema-per-service** | All 13 DB-backed services | Enforces bounded contexts at the database level. No service can read another's tables. Validated by 910+ architecture tests. |
| **Capability-based RBAC** | Policy service | Permissions are fine-grained capabilities (`task:create`, `artifact:upload`), not rigid roles. Policies bind capabilities to workspace members. |
| **Event sourcing (read side)** | Event Store | The event log is the authoritative timeline. Services can rebuild state from events on recovery. |

---

## Where to Start Reading

| Interest | Start with | Then read |
|----------|-----------|-----------|
| Overall vision | [00 — Product Vision](00-product-vision.md) | [01 — Goals & Non-Goals](01-system-goals-and-non-goals.md) |
| Architecture rules | [02 — Invariants](02-architectural-invariants.md) | [03 — Bounded Contexts](03-bounded-contexts.md) |
| Data model | [04 — Core Domain Model](04-core-domain-model.md) | [05 — State Machines](05-state-machines.md) |
| API surface | [07 — API Contracts](07-api-contracts.md) | [SYSTEM.md](../SYSTEM.md) §4 |
| Security model | [08 — Sandbox Security](08-sandbox-security-model.md) | [09 — Permission Model](09-permission-model.md) |
| Service details | [15 — Backend Service Map](15-backend-service-map.md) | [14 — Frontend App Map](14-frontend-application-map.md) |
| Deployment & ops | [13 — Deployment Topology](13-deployment-topology.md) | [Production Checklist](ops/production-deployment-checklist.md) |
| Contributing code | [CONTRIBUTING.md](../CONTRIBUTING.md) | [Coding Rules](CODING-RULES.md) · [Testing Rules](TESTING-RULES.md) |
