# Keviq Core — Post-Baseline Roadmap v1

**Baseline:** `v0.6.0-post-mvp-stable` (2026-03-17)
**Context:** 16/16 user journeys verified, 12/15 services functional, ~97% core platform

---

## Guiding Principle

> The baseline is stable. Do not regress it. Every track below adds capability without breaking what works.

---

## Track 1: Operator Depth

**Goal:** Make Keviq Core observable and auditable for production operations.

| Priority | Item | Effort | Dependencies |
|----------|------|--------|-------------|
| P0 | SSE consumption on frontend (replace polling) | 1 sprint | sse-gateway or event-store SSE |
| P0 | Notification delivery: email webhook | 1 sprint | notification-service |
| P1 | Audit trail UI: event log viewer with search | 2 sprints | audit-service (currently stub) |
| P1 | Notification delivery: Slack webhook | 1 sprint | notification-service |
| P2 | Ops dashboard: service health matrix in browser | 1 sprint | health endpoints exist |
| P2 | Distributed tracing export (Jaeger/OTLP) | 1 sprint | span definitions exist |
| P3 | Alert rules: configurable thresholds on metrics | 2 sprints | telemetry-service (stub) |

### Stub services to activate
- **audit-service**: Needs domain tables, ingest from event-store, query API, frontend viewer
- **telemetry-service**: Needs metric collection, aggregation, dashboard API
- **sse-gateway**: Optional — SSE works via event-store; gateway adds fan-out and auth

---

## Track 2: Integrations Depth

**Goal:** Make LLM provider setup production-grade with validation and testing.

| Priority | Item | Effort | Dependencies |
|----------|------|--------|-------------|
| P0 | Integration connection test ("Test Connection" button) | 0.5 sprint | model-gateway |
| P1 | Provider-specific setup guides (inline help text) | 0.5 sprint | Frontend only |
| P1 | Model list discovery (fetch available models from provider) | 1 sprint | model-gateway |
| P2 | Multi-model routing (fallback chains) | 2 sprints | model-gateway + orchestrator |
| P2 | Usage tracking per integration (token counts, cost) | 2 sprints | model-gateway + new schema |
| P3 | Marketplace-like provider catalog | 3 sprints | New frontend surface |

---

## Track 3: Enterprise / Platform Depth

**Goal:** Production-harden Keviq Core for multi-tenant, multi-region deployment.

| Priority | Item | Effort | Dependencies |
|----------|------|--------|-------------|
| P0 | Load testing suite (k6 or similar) | 1 sprint | Docker Compose stack |
| P0 | Performance SLOs definition | 0.5 sprint | Load test results |
| P1 | mTLS between services | 1 sprint | Certificate management |
| P1 | PostgreSQL connection pool tuning | 0.5 sprint | Load test results |
| P2 | Kubernetes deployment manifests | 2 sprints | Cloud profile exists |
| P2 | Autoscaling configuration | 1 sprint | K8s manifests |
| P2 | Multi-region support | 3 sprints | K8s + DB replication |
| P3 | Per-tenant billing / quota tracking | 3 sprints | New service |
| P3 | External security audit | — | External engagement |

---

## Track 4: Product Polish

**Goal:** Close remaining UX debt and minor gaps.

| Priority | Item | Effort | Dependencies |
|----------|------|--------|-------------|
| P1 | Drag-and-drop artifact upload | 0.5 sprint | Frontend only |
| P1 | Adopt `emptyStateBoxStyle`/`loadingTextStyle` across remaining pages | 0.5 sprint | Frontend only |
| P1 | Fix remaining arch test (`test_timeline_matches_final_state`) | 1 hour | Test fixture |
| P2 | Error message sanitization (filter 5xx details) | 0.5 sprint | Shared utility |
| P2 | Sidebar `<nav>` aria-label | 1 hour | Frontend only |
| P2 | Responsive/mobile layout | 2 sprints | CSS refactor |
| P3 | Dark mode | 2 sprints | Design system |
| P3 | i18n framework | 2 sprints | Design decision |

---

## Suggested Sprint Plan

### Sprint 1 (next)
- Track 1 P0: SSE on frontend + email notifications
- Track 2 P0: Integration connection test
- Track 4 P1: Quick fixes (arch test, style adoption, drag-drop upload)

### Sprint 2
- Track 1 P1: Audit trail UI
- Track 3 P0: Load testing + SLOs
- Track 2 P1: Provider guides + model discovery

### Sprint 3
- Track 1 P1: Slack notifications
- Track 3 P1: mTLS + pool tuning
- Track 4 P2: Error sanitization + responsive start

---

## Decision Log

| Decision | Date | Rationale |
|----------|------|-----------|
| Freeze baseline before new features | 2026-03-17 | 16/16 verified — protect this state |
| Track-based roadmap (not slice-based) | 2026-03-17 | Post-MVP work is capability deepening, not new vertical slices |
| SSE before audit | 2026-03-17 | SSE enables real-time UX across all surfaces; audit is operator-only |
| Load testing before enterprise | 2026-03-17 | Must know current limits before scaling work |
