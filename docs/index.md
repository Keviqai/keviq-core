# Keviq Core Documentation

> Production-ready infrastructure for building and deploying autonomous AI agents.

## Quick Links

- [Documentation Index](docs-index.md) — full doc map by role and feature area
- [Quick Start](../README.md#quick-start) — get running in 60 seconds
- [Architecture Overview](architecture-overview.md) — system diagram and service responsibilities
- [CONTRIBUTING](../CONTRIBUTING.md) — how to contribute
- [Your First Contribution](community/your-first-contribution.md) — beginner guide
- [Roadmap](../ROADMAP.md) — what's next

## Documentation by Role

| Role | Start Here |
|------|-----------|
| **Operator** | [Go-Live Runbook](runbook-go-live.md) → [Known Limitations](deferred-backlog.md) |
| **Developer** | [Product Vision](00-product-vision.md) → [Repo Structure](16-repo-structure-conventions.md) → [Service Map](15-backend-service-map.md) |
| **Reviewer** | [Invariants](02-architectural-invariants.md) → [Bounded Contexts](03-bounded-contexts.md) → [Gate Review](architecture-gate-review-00-12.md) |

## Feature Areas

| Area | Docs | Services |
|------|------|----------|
| Task orchestration | [Domain Model](04-core-domain-model.md), [State Machines](05-state-machines.md) | `orchestrator` |
| Agent execution | [Sandbox Security](08-sandbox-security-model.md), [Failure Recovery](12-failure-recovery-model.md) | `agent-runtime`, `execution-service` |
| Auth & RBAC | [Permission Model](09-permission-model.md) | `auth-service`, `policy-service` |
| Events & streaming | [Event Contracts](06-event-contracts.md) | `event-store`, `notification-service` |
| Observability | [Observability Model](11-observability-model.md) | `telemetry-service`, `audit-service` |
| API & gateway | [API Contracts](07-api-contracts.md) | `api-gateway`, `model-gateway` |
