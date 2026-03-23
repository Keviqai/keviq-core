# Keviq Core — Post-MVP Release Closeout

**Milestone:** `post-mvp-stable`
**Date:** 2026-03-17
**Tag:** `v0.6.0-post-mvp-stable`

---

## 1. What This Release Is

Keviq Core post-MVP baseline: a **release-stable AI-native work operating system** with 16 verified user journeys, 12 functional backend services, 21 frontend pages, and 960+ architecture tests.

This is the first release where:
- Every user journey has been individually verified
- All data-driven pages have error, loading, and empty states
- Docs, progress tracking, and code are fully synchronized
- Known limitations are explicitly catalogued — no overclaims

---

## 2. Cumulative PR History

### Phase A–D (Foundation → Deployment)
| PR Range | Phase | Scope |
|----------|-------|-------|
| PR1–PR12 | A: Foundation | Service skeletons, DB schemas, arch tests |
| PR13–PR36 | B: Vertical Slices | Full end-to-end flows (6 slices) |
| PR37–PR42 | C: Hardening | Security, concurrency, performance, layering |
| PR43–PR45 | D: Deployment | Profiles, isolation, ops validation |

### Post-MVP (Browser Journeys + Polish)
| PR | Scope | Key Deliverable |
|----|-------|----------------|
| PR49 | Artifact upload | Chunked upload API + browser UI |
| PR50A | Slice 0 foundation | bootstrap.sh, smoke-test.sh, Dockerfiles |
| PR50B | Auth UI | Register, login, logout, onboarding |
| PR50C | Task creation | Task form, capability-gated, async 202 |
| PR50D | Run visibility | Run detail + timeline + steps |
| PR50E | Members | Settings + members management |
| PR50F | Terminal | Command-based terminal session UI |
| PR50G | Demo flow | Guided demo, connected empty states |
| PR50H | Approvals | Approval center with state machine |
| PR50I | Settings depth | Policies + secrets + secret-broker |
| PR50J | Operator visibility | Activity feed + notifications + bell badge |
| PR50K | Integrations | LLM provider CRUD + model-gateway |
| PR50L | UX polish | Shared styles, error states, a11y baseline |
| PR50M | Verification | 16-journey matrix, docs sync, closeout |
| PR50N | Stabilization | Secret bug fix, 16/16 verified |

---

## 3. Final Numbers

| Metric | Value |
|--------|-------|
| Backend services | 12 functional + 3 stubs |
| Frontend pages | 21 |
| User journeys | 16/16 verified |
| Architecture tests | 960+ |
| TypeScript errors | 0 |
| File limit violations | 0 |
| Known HIGH bugs | 0 |

### 3-Axis Progress

| Axis | Value |
|------|-------|
| Core Platform Maturity | ~97% |
| Product Usability | ~98% |
| Frontend Completeness | ~96% |

---

## 4. What Works Today

### For a new developer
1. `git clone` + `./scripts/bootstrap.sh` → 15 services + web running
2. `./scripts/smoke-test.sh` → health checks pass
3. Follow `docs/demo-flow.md` → full demo in browser

### For a demo/evaluation
- Register → Login → Create Workspace → Create Task → View Run → Inspect Artifact
- Approval Center: review and decide on pending approvals
- Activity Feed: see workspace events with filters
- Notifications: unread badge, mark-read, click-to-navigate
- Settings: members, policies, secrets, integrations (LLM providers)
- Terminal: command-based sandbox inspection

### For staging deployment
- Use `hardened` profile (read-only FS, no-new-privileges)
- Set production env vars per SYSTEM.md
- Run smoke-test post-deploy

---

## 5. What Does NOT Work / Is Deferred

### Stub services (3)
- **sse-gateway**: SSE works via event-store; dedicated gateway deferred
- **audit-service**: Events exist in event-store; dedicated audit trail deferred
- **telemetry-service**: Health endpoints suffice; metrics dashboards deferred

### Missing capabilities
- No email/Slack notification delivery (store + read only)
- No SSE consumption on frontend (polling via TanStack Query)
- No drag-and-drop upload (button + file picker works)
- No distributed tracing export
- No load testing performed
- No multi-region / HA / autoscaling
- No mTLS between services

### UX debt (LOW priority)
- Some style constants exported but not fully adopted
- Approvals/integrations empty states use solid vs. dashed border
- Sidebar `<nav>` lacks `aria-label`
- Raw server error messages shown without sanitization filter

---

## 6. Release Artifacts

| Artifact | Location |
|----------|----------|
| Source code | This repository, tag `v0.6.0-post-mvp-stable` |
| Demo guide | `docs/demo-flow.md` |
| Release readiness | `docs/mvp-release-readiness.md` |
| User journeys | `USER-JOURNEYS.md` |
| System registry | `SYSTEM.md` |
| Progress tracking | `PROGRESS.md` |
| Changelog | `CHANGELOG.md` |
| Architecture docs | `docs/00-17-*.md` (18 documents) |
| Bootstrap script | `scripts/bootstrap.sh` |
| Smoke test | `scripts/smoke-test.sh` |

---

## 7. Recommended Next Steps

See `docs/post-baseline-roadmap.md` for detailed track planning.

**Short-term (next 1-2 sprints):**
- Fix remaining arch test (`test_timeline_matches_final_state`)
- SSE consumption on frontend (replace polling)
- Notification delivery (email/Slack webhook)

**Medium-term (next quarter):**
- Operator depth: audit trail, richer ops console
- Integration depth: provider validation, setup wizard
- Load testing + performance SLOs

**Long-term:**
- Enterprise: HA, multi-region, mTLS, tenant isolation
- Platform: marketplace, plugin system, advanced multi-tenant
