# 17 — Implementation Roadmap

**Status:** Draft v1.0
**Dependencies:** All docs 00–16
**Objective:** Execution contract for the team — not a marketing roadmap. Locks philosophy, phase model, entry/exit conditions, vertical slice order, PP preconditions, architecture gates, and definition of done.

---

## 1. Implementation Philosophy

**Architecture-first, implementation-increments.**
Docs 00–16 form the constitution of the system. No code may be written to "prove a concept" then later refactored to fit the architecture. If you want to change the architecture, change the doc first — then code.

**Vertical slices only.**
Do not build "the entire orchestrator layer" then "the entire agent layer." Each slice cuts straight through every layer (DB → domain → API → event → frontend) for a specific capability, end-to-end, and must be verifiable. A slice that is not done must not be abandoned for the next slice.

**Risk-first ordering.**
Slice order follows architectural risk, not which features users want to see first. Things that could break the architecture later (state machine authority, outbox, artifact isolation, security boundary) must be locked earliest.

**Pressure points are preconditions, not nice-to-haves.**
PP1–PP10 from the gate review are not technical debt to be addressed later. Each slice lists which PPs must pass. Merge is blocked if PP preconditions are not met.

**Done means done — there is no "mostly done."**
The Definition of Done (section 7) applies to every slice, every phase. There is no "it runs but has no tests" or "deployed but has no audit trail."

---

## 2. Phase Model

```
Phase A — Foundation & Skeleton         (weeks 1–4)
  All service skeletons, DB schemas, event infrastructure, import boundaries,
  architecture tests. The system cannot do anything meaningful yet — but it
  cannot violate the architecture.

Phase B — First Vertical Slice          (weeks 5–12)
  End-to-end: user submit task → orchestrator → run → step →
  agent invocation → artifact → SSE → timeline view.
  Proof that the entire backbone works correctly.

Phase C — Hardening & Security Tightening  (weeks 13–20)
  Sandbox enforcement, policy enforcement, taint/lineage, approval flows,
  failure recovery, multi-step workflows, investigation surfaces.
  The system becomes "production-ready" for single-tenant.

Phase D — Topology Expansion            (weeks 21–28)
  Hybrid topology, multi-tenant isolation, scale hardening,
  model gateway fallback, compliance surfaces, performance SLOs.
```

Each phase has **entry conditions** (must be satisfied before starting) and **exit criteria** (must be satisfied before considering the phase complete).

---

## 3. Entry Conditions & Exit Criteria

### Phase A — Foundation & Skeleton

**Entry conditions:**
- Docs 00–17 have been reviewed and no critical GAPs remain open.
- The team has read and acknowledged gate review + DNB1–DNB12.
- Monorepo has been initialized with pnpm + Turborepo.
- Docker Compose local-first topology has been set up.

**Exit criteria:**
- All 15 services have skeletons: Dockerfile, `main.py`/`main.ts`, health endpoint `/healthz/live` + `/healthz/ready`.
- All DB schemas have been created with correct ownership (each schema has its own DB user).
- Outbox tables have been created for all services that need to emit events.
- `dependency-cruiser` and `import-linter` run clean (0 violations).
- Architecture test PP1 passes: `test_no_status_write_outside_orchestrator`.
- Architecture test PP10 passes: `test_artifact_schema_credentials`.
- CI pipeline runs all stages: lint → arch-test → build.
- `event-store` service can receive and replay events by `correlation_id`.
- `sse-gateway` can open a connection and send heartbeats.

**Not required in Phase A:**
- Any business logic.
- Any UI.
- Any model calls.

---

### Phase B — First Vertical Slice

**Entry conditions:**
- Phase A exit criteria have been met.
- `api-gateway` has authn via `auth-service`.
- `policy-service` can return a permission decision for at least one resource type.

**Exit criteria:**
- User can submit Task → Task transitions `draft → pending → running` per the state machine.
- Orchestrator creates Run, creates Step, assigns AgentInvocation.
- AgentInvocation calls model via `model-gateway` (not directly).
- Model response is wrapped as an Artifact through `artifact-service` (not direct write).
- Artifact has a complete 5-component provenance tuple — model version must not be an alias.
- `artifact.ready` event is emitted.
- `sse-gateway` pushes timeline events to the client.
- Frontend Task timeline displays the correct sequence `task.submitted → run.started → step.started → ... → artifact.ready`.
- When Orchestrator crashes and restarts: Run state is correctly rebuilt from event log (PP2).
- Agent Runtime crashes and restarts: dangling AgentInvocation is correctly interrupted (PP3).
- All PP preconditions for Slices 1–5 have passed (see section 4).

---

### Phase C — Hardening & Security Tightening

**Entry conditions:**
- Phase B exit criteria have been met.
- Gate 1 and Gate 2 have passed (see section 5).

**Exit criteria:**
- Sandbox provisioning + policy enforcement works: egress deny-by-default, `/secrets` unmount before `sandbox.terminated`.
- Policy violation cascade works: violation → taint artifact → block download.
- Approval flow is complete: `waiting_approval`, timeout watcher, approve/reject, cascade cancel.
- Failure recovery: Run failed → human triggers Rerun → new Run created (old Run not resumed).
- Taint propagation: taint parent artifact → child artifact is tainted automatically, taint write before event emit (PP5).
- Investigation surfaces: Artifact Lineage View, Taint Investigation View, Sandbox Session View all load within < 2 seconds.
- Audit trail: every permission decision has an audit record, `permission.violation` triggers alert.
- Degraded mode: when `policy-service` is down, all requests are denied (no fail open).
- All PP preconditions for Slices 6–9 have passed.
- Gate 3 and Gate 4 have passed.

---

### Phase D — Topology Expansion

**Entry conditions:**
- Phase C exit criteria have been met.
- Gates 1–4 have passed.

**Exit criteria:**
- Hybrid topology: control plane on cloud, execution plane local, event/artifact relay consistent.
- Multi-tenant isolation: workspace A cannot read/write resources of workspace B.
- Model Gateway fallback: primary provider down → fallback to backup transparent to agent.
- Performance SLOs met: API command ack p95 < 500ms, SSE propagation p95 < 2s, lineage view < 2s.
- Compliance surfaces: Approval Audit View has CSV/JSON export.
- `sandbox_attempt_index` works correctly in multi-attempt scenarios (PP4).
- Load test: 50 concurrent runs do not break the state machine.

---

## 4. Vertical Slice Order & PP Preconditions

### Slice 1 — Workspace + Auth + Policy Bootstrap

**Capability:** User can log in, create a workspace, invite members, assign roles.

**Services involved:** `auth-service`, `workspace-service`, `policy-service`, `api-gateway`

**Deliverables:**
- User registration + login (JWT).
- Workspace CRUD.
- Member invite + role assignment.
- Permission resolution for workspace:read, workspace:write.
- `_capabilities` flags returned in workspace API response.

**PP preconditions that must pass:**
- PP1 (schema isolation already in place from Phase A — orchestrator cannot write identity schema)
- PP10 (artifact schema isolation already in place from Phase A)

**Architecture test:**
- `test_policy_fail_closed`: when `policy-service` is unreachable → all requests → 403.
- `test_capabilities_in_response`: workspace response must have `_capabilities` object.

---

### Slice 2 — Task Submit → Orchestrator → Event/Outbox

**Capability:** User submits Task → Orchestrator processes it → events are emitted and persisted.

**Services involved:** `api-gateway`, `orchestrator-service`, `event-store`

**Deliverables:**
- `SubmitTask` command end-to-end.
- Task state transition: `draft → pending` with events `task.submitted` + `task.pending`.
- Outbox relay: event persisted to `event-store`, queryable by `correlation_id`.
- Correlation ID injection at `api-gateway` → propagated through the entire chain.

**PP preconditions that must pass:**
- PP1: `orchestrator-service` is the sole entity that mutates `task_status` — arch test passes.
- PP6: `run.timed_out` + `run.cancelled` in same transaction — unit test passes (may not be triggered yet but the code path must be correct).

**Architecture test:**
- `test_no_status_write_outside_orchestrator` passes.
- `test_correlation_id_propagated`: all events from this slice have `correlation_id` matching the trace header.

---

### Slice 3 — Run/Step Lifecycle

**Capability:** Orchestrator creates Run, Step, and manages the complete lifecycle.

**Services involved:** `orchestrator-service`, `agent-runtime-service`, `event-store`

**Deliverables:**
- Task `pending → running`, creates Run `queued → preparing → running`.
- Run creates a simple Step sequence (1 step).
- Step `pending → running`.
- AgentInvocation `initializing → running`.
- Cancel cascade: Task cancel → Run cancel → Step cancel → AgentInvocation interrupt.
- Crash recovery: Orchestrator restart rebuilds state from event log (PP2).
- Agent Runtime restart reconciles dangling invocation (PP3).

**PP preconditions that must pass:**
- PP2: `test_orchestrator_startup_order` — outbox flush before accept.
- PP3: `test_agent_runtime_no_accept_before_reconcile`.
- PP6: `test_timed_out_emits_cancelled`.

**Architecture test:**
- `test_cancel_cascade_inside_out`: cancel order is correct (Step first, Run second, Task last).
- `test_run_no_resume`: no code path sets `run.status = 'running'` on a Run that has already `failed`.

---

### Slice 4 — Model Gateway + Agent Invocation

**Capability:** AgentInvocation can call an LLM via model gateway and receive a response.

**Services involved:** `agent-runtime-service`, `model-gateway`

**Deliverables:**
- `model-gateway` routes calls to provider, returns response.
- Model version alias is resolved to a specific version before returning (PP9).
- Token tracking: `agent.prompt_tokens`, `agent.completion_tokens` are recorded.
- Retry with backoff on provider 429 or 5xx (max 3 attempts).
- AgentInvocation `running → completed` when model returns response.

**PP preconditions that must pass:**
- PP9: `test_model_version_not_alias` — `model-gateway` does not return an alias.

**Architecture test:**
- `test_agent_no_direct_provider_key`: sandbox and agent-runtime do not have provider API keys in env.
- `test_model_gateway_sole_exit`: no HTTP calls from non-gateway services to known provider domains.

---

### Slice 5 — Artifact Creation + Lineage

**Capability:** AgentInvocation creates Artifacts via `artifact-service`, lineage is recorded.

**Services involved:** `agent-runtime-service`, `artifact-service`, `model-gateway` (for provenance)

**Deliverables:**
- `RegisterArtifact` → `FinalizeArtifact` flow.
- Provenance tuple validation: reject artifact if any 1 of the 5 components is missing.
- Model version in provenance: must be a specific version (PP9, DNB12).
- `artifact.ready` event emitted after finalization.
- Lineage edge recorded: `generated_from` root type.
- Checksum validation before `ready`.

**PP preconditions that must pass:**
- PP5: `test_taint_db_before_outbox` (infrastructure must be correct even if no taint trigger exists yet).
- PP10: `test_artifact_schema_credentials` — artifact-service is the sole writer.
- DNB12: model version is not an alias — validated at `RegisterArtifact`.

**Architecture test:**
- `test_artifact_provenance_complete`: `FinalizeArtifact` with missing field → 400.
- `test_artifact_no_direct_write`: no INSERT into `artifact_core` from outside artifact-service.

---

### Slice 6 — SSE + Task/Run Timeline Frontend

**Capability:** User views Task Timeline and Run Timeline in real-time via SSE.

**Services involved:** `sse-gateway`, `event-store`, `api-gateway`, frontend `task-monitor`

**Deliverables:**
- SSE subscription scoped by `workspace_id` and `task_id`.
- `Last-Event-ID` reconnect without losing events.
- Frontend: Task Timeline renders correctly in chronological order with event chain.
- Frontend: SSE events trigger `invalidateQueries()` — do not set cache directly (FP5).
- Frontend: `_capabilities` flags render correct buttons per task state.
- SSE down: banner "Real-time updates paused" displayed clearly.

**PP preconditions that must pass:**
- DNB7: `trace_id = correlation_id` — no separate traceId generation (dependency-cruiser rule).
- FP1–FP10 checklist passes in code review.

**Architecture test:**
- `test_sse_scope_isolation`: client in workspace A does not receive events from workspace B.
- `test_capabilities_not_role_derived`: no `user.role` check in frontend component files.

---

### Slice 7 — Sandbox Provisioning + Terminal

**Capability:** AgentInvocation can run tools in a Sandbox, terminal relay works.

**Services involved:** `execution-service`, `secret-broker`, `policy-service`

**Deliverables:**
- Sandbox provisioning with `policy_snapshot` freeze.
- `sandbox_attempt_index` — second attempt has index 2 (PP4).
- Secret injection via `secret-broker` — no secret values held at the execution layer.
- `/secrets` unmounted before `sandbox.terminated`.
- Egress deny-by-default: tool call to unlisted domain is blocked + `security.violation` emitted.
- Terminal relay: frontend terminal app → api-gateway → execution-service (no direct WebSocket).

**PP preconditions that must pass:**
- PP4: `test_sandbox_attempt_index_required`.
- PP7: `test_tool_idempotent_flag_required` — all tools have `idempotent` flag.

**Architecture test:**
- `test_sandbox_policy_snapshot_frozen`: policy_snapshot does not change after provisioning.
- `test_secrets_unmounted_before_terminated`: `sandbox.terminated` event is only emitted after `/secrets` unmount.
- `test_terminal_no_direct_socket` (frontend arch test): no `new WebSocket(sandboxUrl)` in terminal module.

---

### Slice 8 — Approval + Human-in-the-loop

**Capability:** AgentInvocation can pause to await human approval, timeout works correctly.

**Services involved:** `orchestrator-service`, `notification-service`, frontend `approval-center`

**Deliverables:**
- Step transitions `running → waiting_approval` when agent emits approval request.
- `notification-service` sends notification to approver.
- Dedup: same `approval_id` does not trigger two sends.
- Human approves → Step resumes.
- Human rejects → Step cancel cascade.
- Timeout: approval with no decision after `timeout_at` → `cancelled` — **watcher does not depend on scheduler** (PP8).
- `run.timed_out` → `run.cancelled` in same outbox transaction (PP6).

**PP preconditions that must pass:**
- PP6: `test_timed_out_emits_cancelled`.
- PP8: `test_approval_timeout_defensive_check`.

**Architecture test:**
- `test_approval_dedup`: two notification attempts for same `approval_id` → only one delivered.
- `test_timeout_without_scheduler`: simulate scheduler down, event trigger still resolves timeout.

---

### Slice 9 — Failure Recovery + Taint + Investigation Surfaces

**Capability:** System handles failure correctly, taint propagates, investigation surfaces work.

**Services involved:** All related services, frontend `investigation/`

**Deliverables:**
- Taint: `artifact_service` writes taint flag **before** outbox emit (PP5, DNB11).
- Taint propagation through lineage edges.
- Tainted artifact: download blocked, investigation surface displays taint origin.
- Policy violation cascade: violation → interrupt invocation → terminate sandbox → taint artifact.
- Rerun: Run failed → human triggers Rerun → new Run, old Run remains `failed` (DNB1).
- Artifact Lineage View: loads within < 2 seconds.
- Taint Investigation View: displays propagation path + blocked downloads.
- Approval Audit View: queryable, exportable.
- Degraded mode: `policy-service` down → 403 all requests, banner displayed.

**PP preconditions that must pass:**
- PP5: `test_taint_db_before_outbox`.
- DNB1: `test_run_no_resume`.
- DNB11: taint write order enforced.

**Architecture test:**
- `test_taint_propagation_downstream_only`: taint does not propagate upstream to parent.
- `test_policy_down_fail_closed`: mock policy-service down → all requests → 403.
- `test_degraded_mode_banner`: SSE down → frontend displays degraded indicator.

---

## 5. Architecture Gates

Gates are measurable checkpoints. No gate may be skipped or deferred.

### Gate 1 — No Hidden Bypass

**Timing:** After Slice 3 (early Phase B).

**Pass conditions:**
- `test_no_status_write_outside_orchestrator` passes.
- `test_artifact_no_direct_write` passes.
- `test_agent_no_direct_provider_key` passes.
- `dependency-cruiser` 0 violations.
- `import-linter` 0 violations.
- No cross-schema FK in any migration.

**Significance:** No service can bypass the state machine, artifact isolation, or model gateway — by any means.

---

### Gate 2 — Reproducible Artifact Path

**Timing:** After Slice 5.

**Pass conditions:**
- `test_artifact_provenance_complete` passes — missing field → reject.
- `test_model_version_not_alias` passes.
- Every artifact in `ready` state has all 5 components in provenance tuple.
- Lineage DAG has no cycles (`test_lineage_cycle_rejected`).
- `artifact.tainted` event always has `artifact.tainted = true` in DB **before** the event is emitted.

**Significance:** Any artifact produced by the system can be fully traced and reproduced.

---

### Gate 3 — Recovery-Safe Orchestration

**Timing:** End of Phase B / beginning of Phase C.

**Pass conditions:**
- `test_orchestrator_startup_order` passes — outbox flush before accept.
- `test_agent_runtime_no_accept_before_reconcile` passes.
- `test_run_no_resume` passes — no code path resumes an old Run.
- `test_cancel_cascade_inside_out` passes.
- `test_timed_out_emits_cancelled` passes.
- Manual test: simulate simultaneous crash of Orchestrator and Agent Runtime → restart → state is consistent.

**Significance:** The system does not lose state, does not create zombie invocations, and has no split-brain after crash.

---

### Gate 4 — Security Boundary Intact

**Timing:** End of Phase C.

**Pass conditions:**
- `test_sandbox_policy_snapshot_frozen` passes.
- `test_secrets_unmounted_before_terminated` passes.
- `test_terminal_no_direct_socket` passes.
- `test_policy_down_fail_closed` passes.
- `test_taint_propagation_downstream_only` passes.
- `test_capabilities_not_role_derived` passes.
- Security violation correctly triggers cascade and taints related artifacts.
- Audit trail: every violation has an audit record with all required fields.

**Significance:** Security invariants from docs 08, 09, 10 are enforced by code, not just by convention.

---

## 6. Definition of Done

Applies to every slice, every PR merged to main:

### 6.1 Code

- [ ] Feature works end-to-end on the happy path.
- [ ] Error paths are handled — no silent failures.
- [ ] No `TODO: fix later` in production code paths.

### 6.2 Tests

- [ ] Unit tests for new domain logic.
- [ ] Integration tests for cross-service interaction (if applicable).
- [ ] Architecture tests related to this slice pass.
- [ ] Related infra tests pass.

### 6.3 Architecture Compliance

- [ ] PR checklist from doc 16 has been checked — no items unchecked.
- [ ] `dependency-cruiser` 0 violations after changes.
- [ ] `import-linter` 0 violations after changes.
- [ ] PP preconditions for this slice pass.

### 6.4 Events & Audit

- [ ] Every domain mutation requiring an event: outbox entry exists.
- [ ] Event type follows naming convention.
- [ ] Correlation ID is propagated correctly.
- [ ] Audit record is created for every permission decision in this slice.

### 6.5 Docs

- [ ] If slice reveals inconsistency with docs 00–16: inconsistency is noted and doc is updated or a CLARIFY note is created.
- [ ] No new architectural decision is embedded in code without a corresponding doc.

### 6.6 Forbidden patterns

- [ ] No pattern from FP1–FP10 (doc 14) is introduced.
- [ ] No pattern from Forbidden Recovery Actions FR1–FR10 (doc 12) is introduced.
- [ ] No DNB1–DNB12 is violated.

### 6.7 Observability

- [ ] Span attributes follow doc 11 section 3.4 for the span type being added.
- [ ] Error paths emit correct events.
- [ ] Related alert rules are verified (if slice adds a new failure mode).

---

## 7. Dependency Map per Phase

```
Phase A
  ├─ Infra setup (Docker Compose, DB, event bus)
  ├─ All service skeletons
  ├─ Schema + DB user setup
  ├─ Arch test infrastructure (dependency-cruiser, import-linter)
  └─ CI pipeline (lint → arch-test → build)

Phase B
  ├─ [requires Phase A complete]
  ├─ Slice 1: Auth + Workspace + Policy
  ├─ Slice 2: Task Submit + Orchestrator + Outbox  [requires Slice 1]
  ├─ Slice 3: Run/Step Lifecycle               [requires Slice 2]
  ├─ Slice 4: Model Gateway + AgentInvocation  [requires Slice 3]
  ├─ Slice 5: Artifact + Lineage               [requires Slice 4]
  │           ← Gate 1 check after Slice 3
  │           ← Gate 2 check after Slice 5
  └─ Slice 6: SSE + Timeline Frontend          [requires Slice 2, can parallel Slice 4-5]
              ← Gate 3 check after Phase B complete

Phase C
  ├─ [requires Phase B + Gate 1 + Gate 2 + Gate 3]
  ├─ Slice 7: Sandbox + Terminal               [requires Slice 3, Slice 4]
  ├─ Slice 8: Approval + Human-in-the-loop     [requires Slice 3, Slice 6]
  └─ Slice 9: Failure Recovery + Taint + Investigation  [requires Slice 5, 7, 8]
              ← Gate 4 check after Phase C complete

Phase D
  ├─ [requires Phase C + Gate 4]
  ├─ Hybrid topology (execution plane local)
  ├─ Multi-tenant isolation
  ├─ Model Gateway fallback
  ├─ Performance tuning to SLO targets
  └─ Compliance surfaces (export, audit UI polish)
```

---

## 8. Anti-patterns to Avoid at Roadmap Level

Common execution mistakes that this roadmap proactively prohibits:

| Anti-pattern | Consequence | Rule |
|---|---|---|
| Build an entire layer before building the next | No early end-to-end verification; bugs found late | Vertical slices only |
| Defer PP compliance to a "hardening sprint" | PPs are debt that cannot be repaid after the codebase grows | PP preconditions block merge |
| Merge "mostly working" code into main | DoD erodes gradually | DoD check is mandatory |
| "Refactor architecture after we have an MVP" | Architecture after MVP cannot be refactored cleanly | Architecture-first, not MVP-first |
| Skip gate review because of "deadline" | Gate violations accumulate; not detected before Phase D | Gates cannot be skipped or deferred |
| Frontend team builds UI before service API is stable | Frontend pulls backend backward | Slice order is mandatory: backend first |
| One developer owns multiple bounded contexts | Knowledge silos; service boundaries erode | Each service has a clear owner |

---

## 9. Intentionally Deferred Decisions

| Decision | Reason for deferral |
|---|---|
| Specific time per slice | Depends on team size, cannot be locked without knowing headcount |
| Sprint/iteration structure | Depends on team's working style |
| External dependency schedule (cloud infra, provider contracts) | Outside the control of architecture |
| Feature prioritization within Phase D | Phase D is expansion — order depends on actual deployment target |
| Specific load testing thresholds | Needs baseline from Phase C actual workload |

---

## 10. Conclusion of Architecture Docs 00–17

Docs 00–17 have locked:

| Group | Docs | Content |
|---|---|---|
| Vision & Principles | 00, 01, 02, 03 | Manifesto, goals, invariants, bounded contexts |
| Domain & Lifecycle | 04, 05, 06, 07 | Entity model, state machines, event contracts, API contracts |
| Security & Trust | 08, 09 | Sandbox security, permission model |
| Data & Observability | 10, 11 | Artifact lineage, observability model |
| Resilience | 12 | Failure & recovery model |
| Deployment | 13 | Topology (local/cloud/hybrid) |
| Application | 14, 15 | Frontend map, backend service map |
| Execution | 16, 17 | Repo conventions, implementation roadmap |
| Gate Review | GR | Cross-doc consistency, pressure points, DNB list |

The team can begin Phase A as soon as this document is finalized.
