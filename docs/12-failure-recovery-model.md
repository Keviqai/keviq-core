# 12 — Failure & Recovery Model

**Status:** Draft v1.0
**Dependencies:** 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model, 10 Artifact Lineage Model, 11 Observability Model
**Goal:** Lock down failure taxonomy, recovery principles, retry semantics per layer, compensation vs retry vs rerun, duplicate side-effect prevention, degraded modes, and the complete failure → response matrix.

---

## 1. Failure Taxonomy

### 1.1 Distinguishing Detectability and Recoverability

This is the most important distinction in the entire document:

| | Definition | Examples |
|---|---|---|
| **Detectable** | The system can recognize that a failure has occurred | Sandbox crash, model timeout, artifact write error |
| **Observable** | The failure has sufficient context for root cause investigation | Failure with full trace, event chain, error detail |
| **Recoverable** | The system can automatically or with human input return to a consistent state | Transient network error, model rate limit |
| **Auto-recoverable** | The system is allowed to self-recover without requiring a human decision | Retry idempotent tool call after transient error |

**Hard rule:** Detectable ≠ auto-recoverable. The system must not auto-recover simply because it detected a failure. Each failure type must have explicit recovery authorization in this document.

### 1.2 Failure layers

Failures are classified by the bounded context where they occur — not grouped by symptom:

| Layer | Scope | Example failures |
|---|---|---|
| **L1 — Orchestration** | Task, Run, Step lifecycle | Orchestrator crash mid-Run, Step dependency deadlock |
| **L2 — Runtime / Agent** | AgentInvocation, reasoning loop | Model hallucination loop, agent fails to terminate, multi-turn exceeds limit |
| **L3 — Sandbox** | Sandbox provisioning, execution, policy | Container crash, OOM, policy violation, egress block |
| **L4 — Model Gateway** | LLM provider calls | Timeout, rate limit, provider outage, malformed response |
| **L5 — Eventing** | Event publish, consume, delivery | Event bus down, consumer lag, duplicate delivery, lost event |
| **L6 — Artifact / Provenance** | Artifact write, lineage, taint | Partial write, incomplete provenance, lineage cycle, taint propagation |
| **L7 — Permission / Security** | Permission check, policy enforcement | EP fail open, audit write fail, violation not caught |
| **L8 — Realtime / SSE** | Client push, connection | SSE stream drop, message lag, client reconnect storm |

---

## 2. Failure Invariants

**F1 — Failure must not silently corrupt state.**
When a failure occurs, the entity must transition to an explicit terminal state (`failed`, `interrupted`, `cancelled`) per the state machine in doc 05. Entities must not remain in an ambiguous state.

**F2 — Recovery must not skip event emission.**
Every state transition during recovery — whether auto-retry or human-triggered rerun — must emit a corresponding event per doc 06. There is no "silent fix."

**F3 — Retry must not replay side effects that have already been performed.**
Before retrying, the system must verify whether side effects from the previous attempt have already occurred. Idempotency checks are mandatory, not optional.

**F4 — Partial artifact data must be preserved and flagged.**
When an artifact write fails, partial data must not be deleted. The artifact transitions to `failed` with the `partial_data_available` flag per doc 10.

**F5 — Sandbox failure must not leak into AgentInvocation logic.**
A Sandbox crash is an infrastructure failure — not an agent failure. The AgentInvocation receives `interrupted`, not `failed`. The two lifecycles must not be conflated (doc 05).

**F6 — Security failures must not be auto-recovered.**
Permission violations, policy breaches, and taint detections are terminal. There is no auto-retry. Only a human with the correct permissions can decide the next step.

**F7 — Recovery must be observable and auditable.**
Every recovery action — including auto-retry — must have an event, trace span, and audit record. Recovery that is not observable = recovery that is not trustworthy.

**F8 — Degraded mode must have clear boundaries.**
When the system runs degraded (a service is down), it must be precisely known which capabilities remain and which are lost. Users must not be led to believe the system is fully operational when it is not.

---

## 3. Recovery Principles

### 3.1 Three recovery directions

| Direction | Meaning | When to use |
|---|---|---|
| **Retry** | Re-execute the exact same unit (step, tool call, model call) with the same input | Transient failure, idempotent operation |
| **Compensation** | Perform a reverse action to undo side effects that have already been committed | Failure after side effects have been committed |
| **Rerun** | Create an entirely new Run (do not resume the old Run) | Run-level failure, non-idempotent failure |

**Hard decision from doc 05: A Run must never be resumed.** All run-level failures lead to a Rerun — not a Run retry.

### 3.2 Escalation path

```
Failure detected
  → Can it be retried safely? (idempotent, transient, within retry budget)
      YES → Auto-retry with backoff → if budget exhausted → Fail unit
      NO  → Fail unit immediately
  → Has compensation handler?
      YES → Compensate → emit compensation events
      NO  → Fail unit, propagate up
  → Propagate to parent:
      Step fail → Run decides (retry Step? fail Run?)
      Run fail  → Task decides (rerun? fail Task?)
      Task fail → Human decides (re-submit?)
```

---

## 4. Retry Semantics per Layer

### 4.1 L1 — Orchestration failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Orchestrator crash mid-Run | Auto-recover | Orchestrator restart | Recover Run from event log — do not create a new Run | Do not re-emit `run.started` if already exists |
| Step dependency deadlock (circular wait) | No | — | Fail Run | None |
| Orchestrator loses Event Store connection | Degrade + alert | Operator | — | Do not emit events until connection is restored |
| Approval timeout | No retry | — | `waiting_approval → cancelled` per state machine | None |

**Orchestrator recovery after crash:** The Orchestrator must rebuild state from the event log (`correlation_id` based replay) — not from in-memory state. This is why the event store is the source of truth.

### 4.2 L2 — Runtime / Agent failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Model call transient error (5xx, timeout) | Auto-retry | Agent Engine | AgentInvocation-level (do not create a new AgentInvocation) | Do not re-send if request was already acknowledged |
| Agent loop fails to terminate | No | — | Interrupt AgentInvocation (terminate sandbox) | |
| Agent exceeds max turns | No | — | Fail AgentInvocation | Do not create additional model calls |
| AgentInvocation interrupted (cascade from Step cancel) | No | — | Compensation if handler exists | Do not retry after interrupt |
| Tool call transient error | Auto-retry (if tool declares idempotent) | Agent Engine | Tool call level | Verify tool side effect has not already occurred before retry |
| Tool call non-idempotent error | No | — | Fail Step | None |

**Tool idempotency contract:** Tools must declare `idempotent: true/false` at registration time. The Agent Engine only auto-retries tool calls with `idempotent: true`.

### 4.3 L3 — Sandbox failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Container provisioning fail (transient) | Auto-retry | Sandbox Manager | Create new Sandbox (do not retry same Sandbox) | None |
| OOM / resource exhaustion | No auto-retry | Operator alert | Fail AgentInvocation, escalate | Requires human review of resource limits |
| Policy violation | No | — | Violation cascade (doc 08): block → fail step → interrupt → terminate | None |
| Sandbox crash mid-execution | No auto-retry | — | `sandbox.failed` → interrupt AgentInvocation → fail Step | Do not taint artifact if no write occurred |
| Egress block (expected, policy) | No retry | — | Block tool call, emit `security.violation` | |
| Egress block (transient network) | Retry tool call (if idempotent) | Agent Engine | Tool call level | Sandbox does not directly retry |

**Creating a new Sandbox ≠ retrying a Run.** A new Sandbox for the same AgentInvocation is acceptable if the failure is infra-level and has no side effects.

### 4.4 L4 — Model Gateway / Provider failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Provider HTTP 429 (rate limit) | Auto-retry with backoff | Model Gateway | Request level — transparent to Agent | Do not call provider a second time for the same request while awaiting response |
| Provider HTTP 5xx (transient) | Auto-retry (max 3) | Model Gateway | Request level | Idempotency key must be sent with request |
| Provider timeout | Auto-retry (max 2) | Model Gateway | Request level | Cancel old request before retry |
| Provider outage (all endpoints down) | Failover to backup provider | Model Gateway | Transparent to Agent if backup available | Record `model_gateway.fallback_activated` metric |
| Malformed response from provider | No retry | — | Fail AgentInvocation | |
| Provider returns content violating policy | No retry | — | Flag and fail AgentInvocation | Taint artifact if output was partially written |

**Idempotency key with provider:** The Model Gateway must send a `request_id` (= `agent_invocation_id:attempt_number`) with every provider request. If the provider supports it, use it to detect duplicates.

### 4.5 L5 — Eventing failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Event bus down (publisher cannot write) | Queue locally (outbox) | Publisher (via outbox relay) | Message level — transparent if using outbox | Do not drop events — outbox ensures durability |
| Consumer lag (slow processing) | No retry — this is a throughput issue | Operator | Scale consumer | None |
| Duplicate delivery (at-least-once) | Idempotency check before processing | Consumer | Message level | Do not process if `event_id` already exists in idempotency store |
| Lost event (not in store after crash) | Cannot retry a lost event | — | Orchestrator rebuilds from entity state | Alert ops team |
| Consumer crash mid-processing | Requeue message | Message broker | Message level | Consumer must checkpoint before ack |

**A lost event is the most severe failure in L5.** The reason the outbox pattern is mandatory for critical publishers (doc 06 section 6.2) is to prevent this scenario.

### 4.6 L6 — Artifact / Provenance failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Artifact write partial (network/storage blip) | Auto-retry write | Artifact service | Write operation level | Preserve partial data — do not delete before retry |
| Artifact write fail (storage full) | No | — | Fail artifact, alert ops | None |
| Provenance tuple incomplete | No | — | Fail artifact with `failure_reason: incomplete_provenance` | Do not transition to `ready` |
| Lineage cycle detected | No | — | Reject edge, emit `lineage_cycle_rejected` alert | Do not write edge |
| Taint propagation event fails to emit | Retry emit | Artifact service | Event emit level | Keep taint flag on artifact — taint does not depend on event |
| Checksum mismatch after write | No | — | Fail artifact, alert | Do not promote to `ready` |

**Taint is state, not an event.** If a taint propagation event fails, the taint must still be set on the artifact. The event is only a notification — not the mechanism.

### 4.7 L7 — Permission / Security enforcement failure

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| EP fail open (enforcement point cannot check) | No auto-recover | — | Fail-safe: deny action, alert P0 | Do not allow action to proceed when EP fails |
| Audit write failure | No retry of action | — | Alert P1, allow/deny still occurs (per doc 09) | None |
| Policy store unreachable | Deny all | — | All permission checks → denied until recovery | None |
| Permission.violation event fails to emit | Retry emit | Permission service | Event emit level | Violation has already occurred — do not undo |

**EP fail-safe = fail closed.** When an enforcement point cannot determine the policy, the default is DENY. Never fail open.

### 4.8 L8 — Realtime / SSE degradation

| Failure | Retry? | Who retries | Retry scope | Side effects to prevent |
|---|---|---|---|---|
| Client SSE connection drop | Auto-reconnect | Client | Connection level | Client must send `Last-Event-ID` to receive missed events |
| SSE server overload | No, backpressure | — | Operator scales | Do not drop events — buffer with TTL |
| SSE message lag > SLO | Alert P1 | Operator | — | None |
| Client reconnect storm (thundering herd) | Jitter backoff | Client | Connection level | Server must rate-limit reconnects per workspace |

---

## 5. Compensation vs Retry vs Rerun

### 5.1 When to use Compensation

Compensation is used when a failure occurs **after a side effect has been committed** and that side effect needs to be undone:

- AgentInvocation has written partial output to an external system (via tool call) → need to call the tool's compensate endpoint.
- An artifact was partially promoted to `superseded` but the process failed → need to roll back the `superseded` state.

**Compensation is not retry.** Compensation performs the reverse action — it does not re-perform the original action.

**Compensation must have a pre-declared handler.** Improvising compensation at failure time is not permitted.

### 5.2 When to use Retry

Retry is used when:
- The failure is transient (network blip, rate limit, timeout).
- The operation is idempotent (re-executing does not create additional side effects).
- The retry budget has not been exhausted.

**Retry budget:** Each operation type has its own retry budget (max attempts + total time window). When the budget is exhausted → fail the unit, do not continue retrying.

### 5.3 When to use Rerun

Rerun is used when:
- The Run has failed and needs to be re-executed from the beginning.
- A human has reviewed and decided to try again.
- The failure is not a security/permission violation.

**Rerun creates an entirely new Run.** The old Run retains its `failed` state — it is not deleted or modified. Lineage of artifacts from the old Run is preserved.

### 5.4 Decision matrix

```
Failure occurs
  │
  ├─ Security / permission violation?
  │   YES → Terminal. Human decision only. No retry, no auto-compensation.
  │
  ├─ Side effects already committed?
  │   YES + compensation handler exists → Compensate, then fail unit
  │   YES + no handler                  → Fail unit, record "uncompensated side effect"
  │   NO                                → May retry if idempotent + transient
  │
  ├─ Failure transient + operation idempotent + budget remaining?
  │   YES → Auto-retry with backoff
  │   NO  → Fail unit
  │
  └─ Unit level?
      Tool call / model call → Fail Step if retries exhausted
      Step                  → Fail Run
      Run                   → Fail Task (human decides rerun)
      Task                  → Human re-submit
```

---

## 6. Duplicate Side-Effect Prevention

### 6.1 Idempotency check before every side effect

Before performing any side effect during a retry:

1. Check whether the side effect has already occurred (via idempotency store or entity state).
2. If already occurred: skip, do not re-execute.
3. If not yet occurred: execute and record in the idempotency store.

### 6.2 Most dangerous side effects if duplicated

| Side effect | Consequence if duplicated | Prevention mechanism |
|---|---|---|
| `run.started` emitted twice | Orchestrator creates 2 independent Step sequences | Outbox + event_id idempotency check |
| Artifact finalization runs twice | Checksum overwrite, lineage corruption | Artifact service checks state before writing |
| Approval notification sent twice | User receives 2 approval requests | Approval dedup by `approval_id` |
| Sandbox provisioned twice | 2 Sandboxes running the same AgentInvocation | Sandbox Manager lock per `agent_invocation_id` |
| Taint propagation runs twice | Duplicate taint records | Idempotent taint write — check before setting |
| `task.cancelled` cascade runs twice | Run/Step cancelled twice | State check before cascade — only cascade if entity is not yet terminal |

### 6.3 Idempotency store requirements

- Store `event_id` and `operation_id` with TTL = retention window (doc 06).
- Must be durable — not in-memory only.
- Lookup must be < 10ms p99.

---

## 7. Degraded Modes

When a service is down, the system must have clear boundaries about which capabilities remain and which are lost.

### 7.1 Degraded mode matrix

| Service down | Capabilities remaining | Capabilities lost | User-visible |
|---|---|---|---|
| **Orchestrator** | Read existing tasks/artifacts | Create tasks, run executions, approvals | Banner: "Task execution unavailable" |
| **Agent Engine** | Task/run view, artifact download | Run agents, any Run execution | Banner: "Agent execution unavailable" |
| **Sandbox Manager** | Task/run view | Any Run requiring a sandbox | Banner: "Execution unavailable" |
| **Model Gateway** | Task/run view, artifact view | Any Run calling an LLM | Banner: "AI model unavailable" |
| **Artifact Service** | Task/run view (metadata) | Artifact download, artifact finalization | Warning on artifact list |
| **Event Store** | All real-time features off | Timeline view, SSE, realtime status | Banner: "Real-time updates unavailable" |
| **Auth service** | None | Everything | Hard block at gateway |
| **Observability stack** | All features continue running | Monitoring, alerting | Alert to ops, not user-facing |
| **SSE server** | Polling fallback (if implemented) | Real-time push | UI polls instead of SSE |

### 7.2 Degraded mode must not auto-escalate permissions

When the Policy store is unreachable: all permission checks must default to DENY. Do not expand permissions to "keep the system running." (F invariant F6 + doc 09 section 7.)

### 7.3 Degraded mode must be user-visible

Users must not be led to believe the system is fully operational when it is actually degraded. Every degraded mode must:
- Display a clear banner in the UI.
- Emit a `system.degraded` event with the affected scope.
- Alert the ops team per severity tier (doc 11).

---

## 8. Operator-visible Recovery Surfaces

These surfaces supplement the Investigation Surfaces from doc 11, specifically for recovery workflows:

### 8.1 Failed Run Queue

A list of `failed` Runs not yet reviewed by a human — with sufficient context for the operator/user to decide whether to rerun:
- Error summary + error layer (L1–L8).
- Retry history: how many retries were attempted, at which step.
- Artifact partial data status.
- Compensation status (if applicable).
- Quick actions: "Rerun" (create a new Run), "Archive" (close without rerun).

### 8.2 Compensation Audit Log

A list of all compensation actions that have been performed:
- AgentInvocation ID, tool call ID that was compensated.
- Compensation result: success/fail.
- Uncompensated side effects (if no handler existed).

### 8.3 Degraded Mode Dashboard

A real-time view of service health and capability availability — clearly distinguishing "service up" from "capability available":
- For each service: `liveness`, `readiness`, `dependency` status.
- For each capability: available / degraded / unavailable.
- Active degraded mode alerts.

---

## 9. Mapping Failure → Event / Alert / Audit

| Failure | Event emitted | Alert | Audit record |
|---|---|---|---|
| Run failed | `run.failed` | P2 (routine) / P1 (if burst) | Not mandatory |
| Sandbox policy violation | `security.violation`, `sandbox.failed` | P1 | Mandatory |
| EP fail open | `permission.violation` | P0 | Mandatory |
| Artifact provenance incomplete | `artifact.failed` | P2 | Not mandatory |
| Artifact taint propagated | `artifact.tainted` | P1 | Mandatory |
| Lineage cycle rejected | `artifact.lineage_cycle_rejected` | P2 | Not mandatory |
| Event lost (outbox relay fail) | `system.event_loss_detected` | P0 | Mandatory |
| All model providers down | `model_gateway.all_providers_down` | P0 | Not mandatory |
| Agent escalation attempt | `security.violation` | P1 | Mandatory |
| Audit write failure | `system.audit_write_failed` | P1 | N/A (this is the failure itself) |
| Orchestrator rebuild from event log | `system.orchestrator_recovered` | P2 | Mandatory |
| Compensation success | `agent_invocation.compensated` | None | Mandatory |
| Compensation fail | `agent_invocation.compensation_failed` | P1 | Mandatory |

---

## 10. Forbidden Recovery Actions

The following actions are never permitted under any failure circumstance:

| # | Forbidden | Reason |
|---|---|---|
| FR1 | Resume a `failed` Run — only create a new Run | Keeps lineage clean, state machine is not bypassed |
| FR2 | Auto-recover after security/permission violation | F6 invariant — a security terminal is terminal |
| FR3 | Retry a non-idempotent tool call after failure | Prevents duplicate side effects outside the system |
| FR4 | Delete partial artifact data when write fails | L4 invariant from doc 10 — partial data must be preserved |
| FR5 | Modify an already-written event in the event store to "fix" a failure | Events are facts — do not modify, only write corrections |
| FR6 | Fail open when Policy store is unreachable | Always fail closed |
| FR7 | Write artifact as `ready` when the provenance tuple is incomplete | L5 invariant from doc 10 |
| FR8 | Clear the taint flag without an `artifact:untaint` actor | Security invariant from doc 09 + doc 10 |
| FR9 | Skip audit records during recovery actions | F7 invariant — recovery must be auditable |
| FR10 | Propagate compensation automatically without a declared handler | Improvised compensation is more dangerous than leaving the error |

---

## 11. Intentionally Deferred Decisions

| Item | Reason not yet locked |
|---|---|
| Specific retry budgets (attempt count, time window) per operation type | Requires baseline data from actual operations |
| Compensation handler registry — schema and registration flow | Depends on the tool contract layer (doc 07) |
| Circuit breaker thresholds per provider/service | Requires tuning based on deployment and actual SLOs |
| Chaos engineering policy (deliberate failure injection) | Not part of the architecture layer — belongs to QA/ops process |
| Partial run replay (replay from step N instead of from the beginning) | Complex; requires evaluation of the reproducibility tuple before deciding |

---

## 12. Next Steps

The core document set (00–12) now fully describes the "system intent." The remaining work is to close the architecture shell:

- **13 — Deployment Topology:** local / cloud / hybrid, service placement, network boundary.
- **14 — Frontend Application Map:** module tree, routing, state management, SSE integration.
- **15 — Backend Service Map:** service list, ownership, inter-service contracts.
- **16 — Repo Structure Conventions:** monorepo vs polyrepo, naming, module boundaries.
- **17 — Implementation Roadmap:** Phase A/B/C per the locked architecture, vertical slices, milestone criteria.
