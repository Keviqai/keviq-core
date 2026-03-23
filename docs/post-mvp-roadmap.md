# Keviq Core — Post-MVP Roadmap

**Baseline:** MVP complete at tag `mvp-ready` (`0ad0c12`)
**Date:** 2026-03-16
**Strategy:** Productization-first — make existing capabilities consumable
before adding infrastructure depth.

---

## Guiding Principle

The MVP core is operationally ready. What's missing is not more infrastructure
but **consumable experience surfaces** — artifact delivery, terminal sessions,
approval flows. Productization creates visible value immediately; infrastructure
hardening follows when preparing for wider rollout.

---

## Three Parallel Tracks

### Track 1 — Productization (leads)

Make existing capabilities usable end-to-end.

| PR | Title | Goal | Priority |
|----|-------|------|----------|
| **PR47** | Artifact delivery and access surfaces | Download, signed URLs, delivery authz, content-type/checksum surfacing | **NOW** |
| **PR48** | Artifact preview and content rendering | Preview text/json/markdown, provenance-linked content, fallback download | NEXT |
| **PR49** | Upload/import roots | Upload artifact root types, provenance for imports, query surfaces | NEXT |

**Outcome:** Artifacts go from "created and queryable" to "fully consumable."

### Track 2 — Agent Capability Expansion

Make Keviq Core feel like an operating system, not a backend.

| PR | Title | Goal | Priority |
|----|-------|------|----------|
| **PR50** | Terminal / command session UI | Terminal-backed sandbox, streaming stdout/stderr, session reconnect | AFTER Track 1 |
| **PR51** | Browser task execution | Browser sandbox, DOM snapshot/screenshot artifacts, event integration | AFTER PR50 |
| **PR52** | Approval / human-in-the-loop center | Pending approvals surface, approve/reject flows, audit trail UI | AFTER PR50 |

**Outcome:** Keviq Core becomes a "working system" with interactive execution surfaces.

### Track 3 — Productionization Deep

Run in parallel selectively; don't lead with this.

| PR | Title | Goal | Priority |
|----|-------|------|----------|
| **PR53** | Deep security productionization | Secrets manager, key rotation, stronger service auth, audit hardening | WHEN NEEDED |
| **PR54** | HA / scale transport evolution | Redis Streams transport, worker pool separation, queue durability | WHEN NEEDED |
| **PR55** | Cloud deployment maturity | Kubernetes manifests, object storage backend, rollout strategy | WHEN NEEDED |
| **PR56** | Advanced multi-tenant controls | Tenant admin surface, quotas/budgets, workload partitioning | WHEN NEEDED |

**Outcome:** Keviq Core approaches production platform maturity.

---

## Recommended Execution Order

```
PR47 → PR48 → PR49 → PR50 → PR52 → PR53 → PR54 → PR55 → PR56
 │                      │
 └── Track 1 ───────────┘── Track 2 ──────── Track 3 ────────→
```

PR51 (browser execution) can run in parallel with PR52 (approval center).

---

## Progress Milestones

| After | Keviq Core Is... | Estimated Maturity |
|-------|-------------|-------------------|
| MVP (current) | Operationally release-ready core | 98-99% core |
| PR47-PR49 | Post-MVP usable product — artifacts consumable | Product-ready |
| PR50-PR52 | Agent workspace — interactive execution + approval | Workspace-ready |
| PR53-PR56 | Production platform — security, scale, multi-tenant | Platform-ready |

---

## Why Not Start with Infrastructure

At the current state, Keviq Core has:
- 15 services with health endpoints and recovery sweeps
- 3 deployment profiles (local/hardened/cloud)
- Container hardening, internal auth, concurrency safety
- 850+ architecture gate tests

What's visibly missing to users:
- Artifacts created but **not downloadable**
- Sandbox/tool execution exists but **no terminal surface**
- Approval state machine defined but **no approval center**

The gap is experience, not infrastructure. Track 1 closes this gap first.

---

## Relationship to Deferred Backlog

This roadmap draws from `docs/deferred-backlog.md`:

| Roadmap PR | Backlog Section | Items Addressed |
|------------|----------------|-----------------|
| PR47 | 1 (Product Extensions) | Artifact delivery/download/export |
| PR48 | 5 (UX/Frontend) | Content rendering, loading states |
| PR49 | 1 (Product Extensions) | Upload/import root types |
| PR50 | 1 (Product Extensions) | Terminal/shell integration |
| PR51 | 1 (Product Extensions) | Browser automation tools |
| PR52 | 1 (Product Extensions) | Approval flow (human-in-the-loop) |
| PR53 | 2 (Hardening) | mTLS, secret rotation, audit hardening |
| PR54 | 4 (Performance) | SSE fanout, relay parallelism |
| PR55 | 3 (Cloud/HA) | k8s manifests, S3 backend, rollout |
| PR56 | 3 (Cloud/HA) | Tenant admin, quotas, partitioning |
