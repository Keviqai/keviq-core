# Keviq Core — Deferred Backlog

Items intentionally deferred from MVP. Organized by category with priority
guidance. None of these are bugs — they are scope decisions.

**Last updated:** 2026-03-16 (PR46 closeout)

---

## 1. Post-MVP Product Extensions

Features defined in the architecture docs but not wired in MVP.

| Item | Source | Priority | Notes |
|------|--------|----------|-------|
| Approval flow (human-in-the-loop) | doc 05, Slice 8 | HIGH | State machine defined, Step has `waiting_approval` state, but approval watcher + UI not wired |
| Taint/lineage enforcement | doc 10, Slice 9 | HIGH | Provenance tracked, but taint propagation from parent→child not enforced |
| Artifact delivery/download/export | doc 07 | HIGH | Artifacts are stored and queryable, but no download or delivery endpoints |
| Browser automation tools | doc 07, G7 | MEDIUM | Tool-first architecture ready, but no browser/scraping tool implemented |
| Notification delivery | notification-service | MEDIUM | Service exists and consumes events, but no email/Slack/webhook delivery |
| Multi-step workflow chaining | doc 04, G3 | MEDIUM | Single task→run→step chain works; automatic chaining of dependent tasks not implemented |
| Terminal/shell integration | doc 00 | MEDIUM | Sandbox executes commands, but no interactive terminal UI |
| Cost tracking and model usage metering | G5 | LOW | Model calls logged, but no aggregation or cost attribution |
| File management UI | doc 00 | LOW | Artifacts stored, but no file browser or drag-drop upload |
| Investigation surfaces | doc 14, Slice 9 | LOW | Timeline and event views exist, but no deep-dive investigation tooling |

---

## 2. Production Hardening (Beyond Phase C/D)

Security, reliability, and operational improvements for production at scale.

| Item | Source | Priority | Notes |
|------|--------|----------|-------|
| mTLS between services | doc 13 | HIGH | Currently internal auth via shared secret; mTLS needed for zero-trust |
| Distributed tracing export | doc 11 | HIGH | Correlation IDs flow through all services, but no OpenTelemetry/Jaeger export |
| Secret rotation mechanism | secret-broker | HIGH | Secrets stored, but no rotation workflow or expiry tracking |
| External security audit | — | HIGH | No third-party pentest or security review conducted |
| Rate limiting at API gateway | api-gateway | MEDIUM | No request rate limiting; rely on resource limits only |
| Circuit breaker for service calls | resilience pkg | MEDIUM | Retry with backoff exists, but no circuit breaker pattern |
| Database connection pool monitoring | all DB services | MEDIUM | Pool configured, but no metrics export for pool exhaustion |
| Audit log tamper protection | audit-service | LOW | Events written, but no append-only guarantee or hash chain |
| Log aggregation pipeline | all services | LOW | Services log to stdout; no centralized logging (ELK/Loki) configured |

---

## 3. Cloud / HA / Multi-Tenant Advanced

Items needed for multi-tenant SaaS or high-availability deployment.

| Item | Source | Priority | Notes |
|------|--------|----------|-------|
| Per-tenant database sharding | doc 13 | HIGH | Row-level isolation only; regulatory use cases may need schema/DB-per-tenant |
| Autoscaling configuration | doc 13 | HIGH | Services are stateless (scalable), but no HPA/KEDA config |
| Multi-region deployment | doc 13 | MEDIUM | Single-region only; no cross-region replication or failover |
| Kubernetes manifests / Helm charts | doc 13 | MEDIUM | Docker Compose only; k8s deployment descriptors not created |
| k8s-job execution backend | execution-service | MEDIUM | Backend interface exists, but k8s-job implementation is stub |
| S3 storage backend implementation | artifact-service | MEDIUM | Config recognized, but actual S3 client not implemented |
| Tenant admin console | workspace-service | LOW | Workspace CRUD exists, but no admin dashboard for tenant management |
| Billing and quota tracking | — | LOW | Not in architecture scope (N-goal territory) |
| CDN integration for artifacts | artifact-service | LOW | Local/S3 storage only; no CDN edge caching |

---

## 4. Performance / Scale Future Work

Items for handling higher concurrency and larger workloads.

| Item | Source | Priority | Notes |
|------|--------|----------|-------|
| Load testing under realistic concurrency | PR45 | HIGH | Structural validation done; no benchmark under 100+ concurrent users |
| PostgreSQL `max_connections` tuning guide | runbook | HIGH | Default 100 insufficient for 12 services; documented but not automated |
| SSE fanout at scale (1000+ streams) | event-store | MEDIUM | Polling-based SSE works; may need Redis pub/sub for high fanout |
| Event-store partitioning / archival | event-store | MEDIUM | Append-only store grows indefinitely; no TTL or partition strategy |
| Outbox relay parallelism | orchestrator | LOW | Sequential batch relay; could parallelize for higher throughput |
| Query optimization for large workspaces | all services | LOW | Indexes exist, but no query plan analysis for 100K+ rows |
| Connection pooling per deployment profile | config pkg | LOW | Same pool config for all profiles; cloud may need different sizing |

---

## 5. UX / Frontend Polish

Items for production-quality user experience.

| Item | Source | Priority | Notes |
|------|--------|----------|-------|
| Responsive / mobile design | web | MEDIUM | Desktop-only layout |
| Accessibility audit (WCAG) | web | MEDIUM | No screen reader or keyboard navigation audit |
| Dark mode | web | LOW | Not implemented |
| Internationalization (i18n) | web | LOW | Vietnamese + English in docs, but UI is English-only with no i18n framework |
| Rich text editing | web | LOW | Plain text only in task descriptions |
| Error boundary UI | web | LOW | Basic error handling, no user-friendly error pages |
| Loading states and skeleton screens | web | LOW | Minimal loading indicators |

---

## 6. Architectural Gaps (from Gate Review)

Items identified in `docs/architecture-gate-review-00-12.md` that are not
yet enforced in code.

| Item | PP | Severity | Notes |
|------|-----|----------|-------|
| AST-level enforcement for status field writes | PP1 | MEDIUM | State machine tested structurally, but no import/lint rule prevents direct `*_status = ...` writes |
| Agent-runtime event log reconciliation | PP3 | MEDIUM | Agent-runtime does not rebuild state from event log on startup (orchestrator does) |
| Runtime DB credential rotation test | PP10 | LOW | init-schemas.sql creates per-service users; no test verifies credentials are rotated in production |
| Sandbox attempt index | PP4 | LOW | 1-N sandbox relationship documented but `sandbox_attempt_index` field not in schema yet |
| Approval timeout watcher | PP8 | LOW | Deferred with approval flow (Section 1 above) |

---

## How to Use This Backlog

1. **HIGH priority items** should be addressed before opening Keviq Core to external users
2. **MEDIUM priority items** should be planned for the next development cycle
3. **LOW priority items** are nice-to-have and can be addressed opportunistically
4. Items in Section 1 (product extensions) represent the most impactful user-facing work
5. Items in Section 2 (hardening) are the most critical for production reliability
6. This backlog should be reviewed and updated at each milestone
