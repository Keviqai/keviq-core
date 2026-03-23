# Architecture Gate Review — Docs 00–12

**Document type:** Review, not spec
**Scope:** Docs 00–12 (entire core architecture set)
**Purpose:** Confirm cross-doc consistency before proceeding to 13–17
**Result per item:** PASS / CLARIFY / GAP

---

## 1. Cross-doc Consistency

### 1.1 Entity ownership vs. lifecycle vs. event — PASS

Ownership chain in doc 04 aligns correctly with the state machine in doc 05 and event family in doc 06:

| Entity | Owner (04) | States (05) | Event family (06) |
|---|---|---|---|
| Task | Orchestrator | ✓ aligned | task.* ✓ |
| Run | Orchestrator | ✓ aligned | run.* ✓ |
| Step | Orchestrator | ✓ aligned | step.* ✓ |
| AgentInvocation | Agent Engine | ✓ aligned | agent_invocation.* ✓ |
| Sandbox | Execution layer | ✓ aligned | sandbox.* ✓ |
| Artifact | Artifact service | ✓ aligned | artifact.* ✓ |

No ownership misalignment detected.

---

### 1.2 Sandbox can be recreated for the same AgentInvocation — CLARIFY

**Issue:** Doc 12 section 4.3 states: *"Creating a new Sandbox for the same AgentInvocation is acceptable if the failure is infra-level and has no side effects."*

Doc 04 defines `Sandbox.agent_invocation_id` as a required FK, implying 1-1. Doc 05 does not describe the "new Sandbox for existing AgentInvocation" scenario.

**Potential conflict:** If a Sandbox fails at `provisioning → failed` before the AgentInvocation transitions to `running`, then:
- AgentInvocation is still `initializing`.
- Execution layer creates a new Sandbox.
- The new Sandbox has `agent_invocation_id` pointing to the same original AgentInvocation.
- But the old Sandbox is at `failed → terminating → terminated` — two Sandboxes with the same FK exist concurrently for a brief period.

**Needs to be locked down:** Doc 04 must explicitly state that `Sandbox.agent_invocation_id` is NOT UNIQUE — an AgentInvocation can have multiple Sandbox records (only one active at any given time). An `is_active` field or `sandbox_attempt_index` needs to be added.

---

### 1.3 AgentInvocation `compensated` → What is the Step state — GAP

**Issue:** Doc 05 describes the AgentInvocation lifecycle where `compensated` is terminal. But there is no rule specifying what state the parent Step of this AgentInvocation transitions to when the AgentInvocation reaches `compensated`.

**Three possibilities, none chosen yet:**
1. Step → `failed` (compensation = unrecoverable error at the Step level).
2. Step → `completed` with flag `compensation_applied` (successful compensation = valid outcome).
3. Step → `cancelled` (compensation is cleanup, not a result).

**Needs to be locked down:** This is a real gap. Recommendation: `compensated` AgentInvocation → Step `failed` with `error_detail.compensation_applied = true`. Rationale: compensation means side effects occurred and had to be undone — that is a failure, not a success.

---

### 1.4 `run.timed_out` generates two events — CLARIFY

**Issue:** Doc 05 defines: `running → timed_out → cancelled (system cleanup)`. This means `timed_out` is not terminal — it must proceed to `cancelled`.

Doc 06 has both `run.timed_out` and `run.cancelled` as two separate events. An implementor may emit only `run.timed_out` and forget to emit `run.cancelled`.

**Needs to be locked down:** Add a note to doc 06: *"`run.timed_out` cannot be the final event of a Run. `run.cancelled` must be emitted immediately after by the Orchestrator within the same transaction/outbox."*

---

### 1.5 Taint flag is state, event is only notification — PASS with note

Doc 10 correctly locked this down: *"Taint is state, not an event. If the taint propagation event fails to emit, the taint must still be set on the artifact."*

Doc 12 table L6 confirms: `taint propagation event fail to emit → retry emit — taint flag still holds`.

Consistent. However: the implementor must know to write the taint flag to DB **before** emitting the event — not after. This ordering must be documented in the service implementation guide.

---

### 1.6 Policy snapshot in Sandbox is immutable — PASS

Doc 08 (EP3), Doc 09 (P7), Doc 12 (FR8) are all consistent: `policy_snapshot` is locked after the Sandbox leaves `provisioning`. No doc opens an exception.

---

## 2. No Hidden Bypass

### 2.1 API can bypass state machine — CRITICAL GAP

**Issue:** The current doc set locks down the state machine correctly, but no doc explicitly describes the enforcement mechanism at the DB/API layer.

Example: Nothing prevents a service from calling `UPDATE runs SET run_status = 'running' WHERE id = ?` directly on a Run that is `failed` — this completely bypasses the state machine.

**Potential bypass paths:**
- Direct DB write from internal service (bypassing Orchestrator).
- Recovery script by ops team writing directly through DB.
- Bug in Orchestrator calling the wrong method.

**Needs to be locked down in doc 15 (Backend Service Map) and doc 16 (Repo Conventions):** Every state transition must go through a single method in the Orchestrator domain service — no direct DB updates to `*_status` fields anywhere outside that method. Enforce via architecture test / linting rule.

---

### 2.2 Artifact creation can bypass Artifact service — GAP

**Issue:** Doc 04, 09 (FD9), 10 (L6), 12 (FR7) all assert that `artifact_service` is the sole entry point. But if the Agent Engine has write access to the same DB, nothing prevents a direct insert.

**Needs to be locked down in doc 15:** The artifact table must be exclusively owned by the Artifact service. Other services must not have DB credentials to write to the artifact table. Enforce via DB-level permissions (separate schema or separate DB user).

---

### 2.3 Orchestrator rebuild after crash — does not bypass state machine — PASS with pressure note

Doc 12 section 4.1 states: *"Orchestrator must rebuild state from event log — not from in-memory state."*

This is correct and does not create a bypass. However, this is **implementation pressure point #1** (see section 5).

---

### 2.4 Permission check can be bypassed if Policy store is down — PASS

Doc 09 + Doc 12 (L7) are consistent: Policy store unreachable → fail closed (deny all). There is no fail-open path in the current doc set.

---

### 2.5 Approval can be bypassed if timeout is handled incorrectly — CLARIFY

**Issue:** Doc 05 states that when `timeout_at` expires → approval `timed_out` → parent entity `cancelled`. But who watches `timeout_at`? If the scheduler misses the timeout (scheduler down), the approval request hangs indefinitely and the Run cannot progress further.

**Needs to be locked down in doc 12 or doc 15:** The Orchestrator must have a timeout watcher process. If the watcher misses a cycle, the approval must be resolved on the watcher's next run — not wait for the next event.

---

## 3. Terminal Semantics Alignment

### 3.1 Cross-doc terminal states table

| Entity | Terminal states | Notes |
|---|---|---|
| Task | `completed`, `failed`, `cancelled`, `archived` | `archived` is permanently terminal |
| Run | `completed`, `failed`, `cancelled`, `timed_out`* | *`timed_out` → `cancelled` is mandatory (see 1.4) |
| Step | `completed`, `failed`, `skipped`, `cancelled` | `skipped` is terminal — cannot be unshipped |
| AgentInvocation | `completed`, `failed`, `interrupted`, `compensated` | `compensated` → Step state needs to be locked down (see 1.3) |
| Sandbox | `terminated` | `failed` is a mid-state → always resolves to `terminated` |
| Artifact | `ready`, `failed`, `superseded`, `archived` | `superseded` is still readable and downloadable |
| Approval | `approved`, `rejected`, `timed_out` | All are terminal |

### 3.2 Sandbox `failed` is not terminal — CLARIFY

**Issue:** Doc 05 Sandbox lifecycle: `failed → terminating → terminated`. This means `failed` is a mid-state — Sandbox must always proceed through `terminated`.

However, in the alert table in doc 11, some places treat `sandbox.failed` as a terminal event. And doc 12 table L3 states *"`sandbox.failed` → interrupt AgentInvocation → fail Step"* — this is correct, but the Sandbox must still continue to `terminated` afterward.

**Needs to be locked down:** Add a clear note: *"Sandbox `failed` is an intermediate state. Regardless of outcome, `sandbox.terminated` is the mandatory final state and event of every Sandbox. No Sandbox ends its lifecycle at `failed`."*

---

### 3.3 `archived` is permanently terminal — PASS

Doc 04, 05, 10 are consistent: Artifact/Task cannot leave `archived`. There is no state transition from `archived` back to any other state.

---

### 3.4 `tainted` is not a state, it is a property — PASS

Doc 10 designed this correctly: `tainted` is a boolean property on Artifact, not a state in the state machine. An Artifact that is `ready + tainted` still has state `ready` — but access rules are restricted. Consistent with doc 09 and doc 11.

---

## 4. Operational Truth Alignment

### 4.1 Source of truth map

| Layer | Entity | Source of truth | Conflict if misaligned |
|---|---|---|---|
| Identity | User | Auth service | Auth down → deny all (doc 12 L7) |
| Workspace | Workspace, Member, Policy, SecretBinding | Workspace service DB | Policy unreachable → fail closed |
| Orchestration | Task, Run, Step | Orchestrator DB + Event log | Rebuild from event log after crash |
| Execution | AgentInvocation | Agent Engine DB + Event log | Potential disagreement with Orchestrator (see 4.2) |
| Sandbox | Sandbox metadata | Execution layer DB | Sandbox terminated = cleaned up |
| Storage | Artifact content | Storage layer | Checksum = ground truth |
| Artifact metadata | Artifact | Artifact service DB | Lineage + provenance fields |
| History | All events | Event store | Append-only, no modifications |
| Permission decisions | Audit records | Audit log | Cannot be reconstructed if lost |

### 4.2 Orchestrator / Agent Engine can disagree after dual crash — GAP

**Issue:** Doc 12 section 4.1: *"Orchestrator rebuilds from event log."* But if both the Orchestrator **and** Agent Engine crash simultaneously:

- Orchestrator rebuilds: sees `run.started`, `step.started`, `agent_invocation.started` — concludes AgentInvocation is `running`.
- Agent Engine restarts: has no in-memory state — concludes no AgentInvocation is running.
- System enters split-brain: Orchestrator believes AgentInvocation is `running`, Agent Engine has no context.

**Needs to be locked down in doc 15:** Agent Engine must persist AgentInvocation state to DB **synchronously** (not just in-memory) and must also be capable of rebuilding from event log, same as Orchestrator. On restart, Agent Engine must reconcile state with event log before accepting new requests.

---

### 4.3 `run_config` lock at transition boundary — CLARIFY

**Issue:** Doc 05: `run_config` is locked when the Run leaves `queued`. Doc 12 section 4.1: Orchestrator restart may re-process the `queued → preparing` transition.

If the transition already occurred (run_config already locked) but the `run.preparing` event was not yet emitted (crash immediately after DB write), the Orchestrator restart will see the Run still at `queued` in the event log but the DB already at `preparing`.

**Needs to be locked down:** State machine transitions must use an **event-sourcing pattern**: state is only read from the event log, not directly from DB, **or** DB write and event emit must go in the same outbox transaction. The two sources cannot be allowed to diverge.

---

### 4.4 Audit record is non-reconstructible — PASS with pressure note

Doc 09 section 9.3: If audit write fails with permission.violation → fail-safe deny. This is correct. But audit records cannot be reconstructed after loss (unlike the event log which can rebuild the state machine).

**Pressure note:** The audit store must have a higher durability SLA than the regular event store. Doc 13 must reflect this in the deployment topology.

---

## 5. Implementation Pressure Points

These are the 10 points where the development team is most likely to make mistakes, and which need to be locked down in docs 13–17:

---

**PP1 — State transition enforcement at DB layer**

Easy to get wrong: Developer writes `repository.save(run)` after directly assigning `run.status = 'running'`, bypassing the state machine.

Required: Single domain method per transition. Architecture test: no file other than `OrchestratorDomainService` is allowed to call methods that write `run_status`.

---

**PP2 — Orchestrator crash recovery — partial event log**

Easy to get wrong: Orchestrator rebuilds state from event log, but the outbox had not yet relayed some events before the crash. Rebuilt state is missing transitions.

Required: Outbox relay must run before the Orchestrator accepts any new requests after restart. "Startup readiness" = outbox fully flushed.

---

**PP3 — Agent Engine / Orchestrator split-brain after dual crash**

Easy to get wrong: Agent Engine restarts without reconciling with event log — assumes no in-flight AgentInvocation exists.

Required: Agent Engine startup must query the event log for all `agent_invocation.started` without a corresponding terminal event, and interrupt them before accepting new requests.

---

**PP4 — Sandbox 1-N with AgentInvocation**

Easy to get wrong: Code assumes `sandbox.agent_invocation_id` is unique — query `WHERE agent_invocation_id = ?` returns one row, but there may be multiple rows (attempt 1 failed, attempt 2 active).

Required: Add `sandbox_attempt_index` to the Sandbox entity. Queries must filter `WHERE agent_invocation_id = ? AND is_active = true`.

---

**PP5 — Taint write before event emit**

Easy to get wrong: Code emits `artifact.tainted` event before writing `tainted = true` to DB. If the DB write fails after event emit, downstream consumers have already acted on the taint but the DB has no record.

Required: Taint write to DB must go in the same outbox transaction as the event emit. DB write first, outbox relay after.

---

**PP6 — `run.timed_out` does not emit `run.cancelled`**

Easy to get wrong: Developer sees `run.timed_out` as a "sufficient" event and does not emit `run.cancelled` afterward.

Required: The `timed_out` state transition must trigger **two** outbox entries: `run.timed_out` and `run.cancelled`, within the same transaction.

---

**PP7 — Tool idempotency contract is not enforced**

Easy to get wrong: Tool is retried (because it declares `idempotent: true`) but is not actually idempotent (e.g., tool sends email, inserts DB row).

Required: Tool registration must have an `idempotency_proof` field — not self-declared. CI must run idempotency tests for all tools before shipping.

---

**PP8 — Approval timeout watcher is missed**

Easy to get wrong: Scheduler down → approval timeout is not triggered → Run hangs indefinitely at `waiting_approval`.

Required: Orchestrator must check approval timeouts when processing any event related to that workspace — not relying solely on the scheduler. Defensive timeout check is mandatory.

---

**PP9 — Artifact provenance tuple incomplete at write time**

Easy to get wrong: Artifact is created with `root_type = generated` but `model_version` is only an alias (`latest`) not a specific version. Artifact passes validation and is promoted to `ready` with an invalid reproducibility tuple.

Required: Artifact service must validate that `model_version` is not an alias before accepting artifact registration. Model Gateway must resolve the alias to a specific version before passing it downstream.

---

**PP10 — Direct DB access to artifact table from non-artifact service**

Easy to get wrong: Developer writes a migration script or debug tool that queries the artifact table directly to "fix" data, bypassing lineage and event trail.

Required: Artifact table resides in a separate DB schema with separate credentials. Only the `artifact_service` service account has WRITE permission. All "fixes" must go through the Artifact service API.

---

## 6. Do-Not-Break List before proceeding to 13–17

The following decisions **must not be changed** during the writing of docs 13–17 or during implementation. If topology, service map, or repo structure conflicts with any of these items — the topology must change, not these items:

| # | Decision | Origin |
|---|---|---|
| DNB1 | Run never resumes — only Rerun creates a new Run | doc 05, 12 |
| DNB2 | EP fails closed — never fails open | doc 09, 12 |
| DNB3 | Security violation does not auto-recover | doc 12 F6 |
| DNB4 | Degraded mode does not auto-escalate permissions | doc 12 section 7.2 |
| DNB5 | Recovery must have event + audit | doc 12 F7 |
| DNB6 | `artifact_service` is the sole entry point for artifact creation | doc 10 L6, 09 FD9 |
| DNB7 | `trace_id = correlation_id` — do not create two separate IDs | doc 11 O5 |
| DNB8 | Execution trace and provenance trace are two separate observation systems | doc 11 O6 |
| DNB9 | Agent cannot self-elevate permissions via prompt or tool call | doc 09 P2 |
| DNB10 | Every state transition must go through Orchestrator domain service | doc 05, gap PP1 |
| DNB11 | Taint write to DB before event emit — not after | gap PP5 |
| DNB12 | Model version must not be an alias at artifact registration | gap PP9 |

---

## 7. Gate Review Conclusion

**Overall status:** The 00–12 doc set qualifies as the architecture constitution. No conflict is severe enough to block proceeding.

**Must be addressed before coding:**

| Severity | Count | Action |
|---|---|---|
| Critical GAP | 3 | API bypass state machine (PP1), Artifact table isolation (PP10), Agent Engine rebuild (PP3) — must be locked down in doc 15 |
| CLARIFY | 5 | Sandbox 1-N (PP4), run.timed_out dual event (1.4), AgentInvocation compensated → Step state (1.3), Approval watcher (PP8), run_config lock boundary (4.3) — add notes to corresponding docs |
| Pressure notes | 10 | PP1–PP10 — must appear explicitly in doc 16 (Repo Conventions) and doc 17 (Roadmap) |

**Next processing order:**
13 → 15 → 14 → 16 → 17 (in the agreed order, starting from doc 13 Deployment Topology).
