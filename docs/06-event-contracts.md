# 06 — Event Contracts

**Status:** Draft v1.0
**Dependencies:** 04 Core Domain Model, 05 State Machines
**Objective:** Lock down the entire event model — standard envelope, ordering guarantees, idempotency, retry semantics, retention/replay policy, and complete mapping from state transitions to mandatory events.

---

## 1. General Principles of the Event Model

### 1.1 An Event Is Something That Happened — Not an Internal Reminder

Every event in this system is a **fact** — reflecting something that has already occurred, not an intention or request. This means:

- An event cannot be "cancelled" after it has been emitted.
- A consumer must not reject a fact event because it "doesn't want to process it" — it may only idempotently ignore it if already processed.
- Event names are always in **past tense**: `task.completed`, `sandbox.terminated`, not `task.complete` or `sandbox.terminate`.

### 1.2 Separation of Fact Events and Command-like Events

The system uses two types of events with different semantics. They must not be mixed:

| Type | Semantics | Example | Emitted By |
|---|---|---|---|
| **Fact event** | Something that happened, irreversible | `sandbox.terminated`, `artifact.ready` | Service that owns the entity |
| **Command-like event** | Request for a service to perform an action | `sandbox.terminate_requested` | Orchestrator |

Command-like events exist only in the **cascade shutdown flow** (Task cancel → Run cancel → ... → Sandbox terminate). All other cases use fact events only.

Command-like events must be named with the suffix `_requested` for absolute differentiation. No exceptions.

### 1.3 Events Are the Source of Truth for History

The event store is append-only. No entity may modify event content after it has been written. If an event was written incorrectly, the remedy is to write a **correction event** — not to edit the original event.

### 1.4 No Global Ordering — Only Scoped Ordering

The system **does not guarantee** total ordering across the entire event stream. Ordering is only guaranteed within scopes that have business significance (see section 4).

---

## 2. Standard Event Envelope

Every event — regardless of aggregate, type, or context — must conform to the following envelope. No service may add fields to the envelope. Additional fields may only be placed in `payload`.

```json
{
  "event_id":              "<UUID>",
  "event_type":            "<aggregate>.<action>",
  "schema_version":        "1.0",

  "workspace_id":          "<UUID>",
  "task_id":               "<UUID | null>",
  "run_id":                "<UUID | null>",
  "step_id":               "<UUID | null>",
  "agent_invocation_id":   "<UUID | null>",
  "sandbox_id":            "<UUID | null>",
  "artifact_id":           "<UUID | null>",

  "correlation_id":        "<UUID>",
  "causation_id":          "<UUID | null>",

  "occurred_at":           "<ISO 8601 timestamp with timezone>",
  "emitted_by": {
    "service":             "<string>",
    "instance_id":         "<string>"
  },

  "actor": {
    "type":                "<user | agent | system | scheduler>",
    "id":                  "<string>"
  },

  "payload":               { }
}
```

### 2.1 Rules for Populating Context IDs

- Populate all context IDs relevant to the event. For example: `sandbox.terminated` must populate `workspace_id`, `task_id`, `run_id`, `step_id`, `agent_invocation_id`, `sandbox_id`.
- IDs that are not relevant should be set to `null` — do not omit the field.
- `workspace_id` is **always required** — no event may omit it.

### 2.2 `event_type` Naming Convention

Format: `<aggregate>.<past_tense_verb>`

Valid aggregates: `task`, `run`, `step`, `agent_invocation`, `sandbox`, `artifact`, `approval`

Valid examples: `task.completed`, `sandbox.terminated`, `artifact.ready`
Invalid examples: `taskCompleted`, `sandbox_terminate`, `artifact-ready`

### 2.3 `schema_version`

Each `event_type` has its own `schema_version`. When a payload schema change is not backward-compatible, the version must be incremented and consumer support for the old version must be maintained for at least **2 release cycles**.

---

## 3. Correlation / Causation Chain

### 3.1 `correlation_id`

Links all events belonging to the same **execution context**. In this system, each `run_id` generates a unique `correlation_id` when the Run is created. All events within a Run — including Step, AgentInvocation, Sandbox, and Artifact events — carry the same `correlation_id`.

**Rules:**
- The `correlation_id` of a Run = UUID generated when the `run.queued` event is emitted.
- All events originating within that Run must copy this `correlation_id`.
- When a Task spawns multiple Runs, each Run has its own `correlation_id`.

### 3.2 `causation_id`

Indicates which event directly caused the current event. Used to trace the causal chain.

**Example of a cancel cascade chain:**

```
task.cancelled          (causation_id: null — user triggered)
  └── run.cancelled     (causation_id: task.cancelled.event_id)
        └── step.cancelled  (causation_id: run.cancelled.event_id)
              └── agent_invocation.interrupted  (causation_id: step.cancelled.event_id)
                    └── sandbox.terminate_requested  (causation_id: agent_invocation.interrupted.event_id)
                          └── sandbox.terminating    (causation_id: sandbox.terminate_requested.event_id)
                                └── sandbox.terminated  (causation_id: sandbox.terminating.event_id)
```

**Rules:**
- If an event was emitted due to another event, `causation_id` = `event_id` of the causal event.
- If an event was emitted due to a direct actor action (user, scheduler), `causation_id` = `null`.
- `causation_id` never points to an event belonging to a different `correlation_id` — there is no cross-run causation.

---

## 4. Ordering Guarantees and Non-guarantees

### 4.1 Guaranteed Ordering (Within-scope)

| Scope | Ordering Guarantee | Mechanism |
|---|---|---|
| Within a `run_id` | Run events are ordered by `occurred_at` | Partition key = `run_id` |
| Within a `task_id` | Task events are ordered | Partition key = `task_id` |
| Within a `sandbox_id` | `provisioned → executing → idle → terminated` ordered | Partition key = `sandbox_id` |
| Within an `artifact_id` | `registered → writing → ready/failed → archived` ordered | Partition key = `artifact_id` |

### 4.2 Ordering NOT Guaranteed (Cross-scope)

- Between two different Runs within the same Task.
- Between Step A and Step B running in parallel within the same Run.
- Between AgentInvocation events and Sandbox events if they occur simultaneously.
- Between `artifact.ready` events of two different Artifacts.

### 4.3 Handling Cross-scope Ordering When Needed

Use `causation_id` to infer causal ordering. Use `occurred_at` only for estimation, not to enforce ordering logic. Consumers must not assume total ordering across different scopes.

---

## 5. Idempotency Rules

### 5.1 Principle

Every event consumer **must** process idempotently based on `event_id`. If the same `event_id` appears twice, the consumer must:
- Detect the duplicate via `event_id`.
- Skip the second occurrence entirely — no reprocessing, no error reporting.
- Not emit any downstream events due to the duplicate.

### 5.2 Idempotency Store

Consumers must maintain their own idempotency store. Store processed `event_id` values for at least the **retention window** (see section 7). Do not rely on the event bus for deduplication.

### 5.3 Events Requiring Strict Idempotency

| Event | Reason |
|---|---|
| `run.completed` | Must not trigger artifact finalization twice |
| `artifact.ready` | Must not trigger downstream pipeline twice |
| `sandbox.terminated` | Must not trigger cleanup twice |
| `approval.approved` | Must not resume a Run twice |
| `task.cancelled` | Must not cascade cancel twice |

---

## 6. Retry Semantics

### 6.1 Delivery Guarantee

The entire system uses **at-least-once delivery**. Consumers must be idempotent. Exactly-once is not guaranteed at the transport layer.

### 6.2 Outbox Pattern — Mandatory for the Following Publishers

Publishers must use a **transactional outbox** (write the event to the database in the same transaction as the state mutation, then relay to the event bus) to ensure events are not lost if the service crashes mid-operation:

| Publisher | Reason Outbox Is Mandatory |
|---|---|
| Orchestrator emits `run.started` | State mutation and event must be atomic |
| Orchestrator emits `task.completed` | Artifact confirmation and event must be atomic |
| Artifact service emits `artifact.ready` | Checksum write and event must be atomic |
| Orchestrator emits `task.cancelled` | Cascade trigger and event must be atomic |

### 6.3 Retry Policy by Event Type

| Event Type | Retry | Backoff | Max Attempts | On Exhaustion |
|---|---|---|---|---|
| Fact events (state transition) | Yes | Exponential + jitter | 5 | Dead letter queue |
| Command-like events (`*_requested`) | Yes | Exponential | 3 | Alert + DLQ |
| Approval events | Yes | Linear | 3 | Alert ops team |
| Artifact events | Yes | Exponential + jitter | 5 | DLQ + alert |

### 6.4 Events Must Not Replay Side Effects

The following terminal events **must not cause repeated side effects** even if delivered multiple times:

- `sandbox.terminated` → must not terminate an already-terminated sandbox.
- `artifact.ready` → must not overwrite an already-`ready` artifact.
- `run.completed` → must not transition an already-`completed` Run to another state.
- `approval.approved` / `approval.rejected` → must not process the decision twice.

Consumers must check the current state of the entity before processing a terminal event.

---

## 7. Retention and Replay Policy

### 7.1 Hot Retention (Queryable, Low Latency)

| Scope | Retention Period | Reason |
|---|---|---|
| All events | 30 days | Debug, audit, short-term replay |

### 7.2 Cold Retention (Archived, Higher Latency)

| Scope | Retention Period |
|---|---|
| All events | 1 year |
| Enterprise workspace events | Per contract (minimum 3 years) |

### 7.3 Replay Semantics

- **Replay is allowed:** In debug mode, consumers may replay events from a specific `correlation_id`.
- **Production side effects must not be replayed:** Replay must not trigger real sandboxes, must not write real artifacts, must not send real approval notifications.
- Replay must run in **dry-run mode** with the flag `is_replay: true` in the envelope context.
- Consumers must check `is_replay` and skip all real side effects if this flag is set.

---

## 8. Event Families by Aggregate

### 8.1 task.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `task.submitted` | User submits task | `task_type`, `input_config_hash` | Fact |
| `task.started` | Orchestrator creates the first Run | `first_run_id` | Fact |
| `task.approval_requested` | Orchestrator encounters an approval gate | `approval_id`, `approver_role`, `prompt` | Fact |
| `task.approved` | User approves | `approval_id`, `decided_by_id` | Fact |
| `task.rejected` | User rejects | `approval_id`, `decided_by_id`, `reason` | Fact |
| `task.completed` | All required Runs are done | `artifact_ids`, `duration_ms` | Fact |
| `task.failed` | Orchestrator determines unrecoverable | `error_code`, `error_summary`, `failed_run_id` | Fact |
| `task.cancelled` | User or Policy cancels | `cancelled_by_type`, `cancelled_by_id`, `reason` | Fact |
| `task.archived` | Scheduled archival | `archived_at` | Fact |

### 8.2 run.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `run.queued` | Orchestrator creates a Run | `trigger_type`, `run_config_hash` | Fact |
| `run.preparing` | Orchestrator begins preparation | | Fact |
| `run.started` | Sandbox ready, first Step created | `first_step_id` | Fact |
| `run.approval_requested` | Approval gate within Run | `approval_id`, `approver_role` | Fact |
| `run.approved` | User approves | `approval_id`, `decided_by_id` | Fact |
| `run.completing` | All Steps finished | `artifact_ids_pending_finalization` | Fact |
| `run.completed` | Artifacts finalized | `artifact_ids`, `duration_ms`, `total_cost_usd` | Fact |
| `run.failed` | Unrecoverable error | `error_code`, `error_summary`, `failed_step_id` | Fact |
| `run.cancelled` | Cascade from Task or User | `cancelled_by_type`, `cancelled_by_id` | Fact |
| `run.timed_out` | Exceeded timeout | `timeout_limit_ms` | Fact |

### 8.3 step.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `step.started` | Orchestrator begins Step | `step_type`, `sequence`, `input_snapshot_hash` | Fact |
| `step.approval_requested` | Orchestrator encounters an approval gate | `approval_id`, `approver_role`, `prompt` | Fact |
| `step.approved` | User approves | `approval_id`, `decided_by_id` | Fact |
| `step.blocked` | Dependency not satisfied | `blocking_reason`, `blocking_step_id` | Fact |
| `step.unblocked` | Dependency resolved | `resolved_by` | Fact |
| `step.completed` | Step completed | `output_snapshot_hash`, `duration_ms` | Fact |
| `step.failed` | Unrecoverable error | `error_code`, `error_detail_hash` | Fact |
| `step.skipped` | Condition false | `skip_reason` | Fact |
| `step.cancelled` | Cascade from Run | | Fact |

### 8.4 agent_invocation.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `agent_invocation.started` | Agent Engine begins | `agent_id`, `model_id` | Fact |
| `agent_invocation.waiting_human` | Agent asks the user | `question_summary`, `timeout_at` | Fact |
| `agent_invocation.human_responded` | User provides input | `responded_by_id` | Fact |
| `agent_invocation.waiting_tool` | Tool call dispatched | `tool_name`, `tool_call_id` | Fact |
| `agent_invocation.tool_result_received` | Tool returns result | `tool_call_id`, `success` | Fact |
| `agent_invocation.completed` | Agent finished successfully | `prompt_tokens`, `completion_tokens`, `total_cost_usd` | Fact |
| `agent_invocation.failed` | Logic/model error | `error_code`, `error_detail` | Fact |
| `agent_invocation.interrupted` | Orchestrator interrupts | `interrupted_by`, `reason` | Fact |
| `agent_invocation.compensating` | Agent Engine begins rollback | `compensation_reason` | Fact |
| `agent_invocation.compensated` | Rollback completed | | Fact |

### 8.5 sandbox.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `sandbox.terminate_requested` | Orchestrator requests termination | `requested_by`, `reason` | **Command-like** |
| `sandbox.provisioned` | Execution layer finishes creating sandbox | `sandbox_type`, `resource_limits_hash` | Fact |
| `sandbox.executing` | Begins executing a command | `tool_call_id` | Fact |
| `sandbox.idle` | Command completed, waiting for next command | `last_tool_call_id` | Fact |
| `sandbox.failed` | Crash, OOM, policy violation | `failure_type`, `policy_violation_detail` | Fact |
| `sandbox.terminating` | Begins shutdown | `termination_reason` | Fact |
| `sandbox.terminated` | Shutdown complete | `terminated_at`, `termination_reason` | Fact |

**Note:** `sandbox.terminate_requested` is the only command-like event in the entire sandbox family. All other events are facts.

### 8.6 artifact.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `artifact.registered` | Artifact service creates a record | `artifact_type`, `run_id`, `step_id` | Fact |
| `artifact.writing` | Begins writing to storage | `storage_ref` | Fact |
| `artifact.ready` | Write complete, checksum verified | `checksum`, `size_bytes`, `storage_ref` | Fact |
| `artifact.failed` | Write failed | `failure_reason`, `partial_data_available` | Fact |
| `artifact.superseded` | New artifact in lineage created | `superseded_by_artifact_id` | Fact |
| `artifact.archived` | Moved to cold storage | `archived_storage_ref` | Fact |

### 8.7 approval.*

| Event Type | Trigger | Key Payload Fields | Fact or Command-like |
|---|---|---|---|
| `approval.requested` | Orchestrator creates ApprovalRequest | `approval_id`, `target_type`, `target_id`, `approver_role`, `prompt`, `timeout_at` | Fact |
| `approval.approved` | User approves | `approval_id`, `decided_by_id`, `decided_at` | Fact |
| `approval.rejected` | User rejects | `approval_id`, `decided_by_id`, `reason` | Fact |
| `approval.timed_out` | Timeout without a decision | `approval_id`, `timed_out_at` | Fact |

---

## 9. Invalid — Absolutely Prohibited

### 9.1 Event Integrity

- Modifying event content after it has been written to the event store.
- Deleting events from the event store (even incorrect events — only correction events may be written).
- An event without `workspace_id`.
- An event without a globally unique `event_id`.
- An event with an `occurred_at` timestamp in the future.

### 9.2 Naming and Semantics

- Using event names that are not past tense (except the `_requested` suffix for command-like events).
- Placing business logic in `event_type` instead of `payload`.
- A single event carrying both fact and command semantics.
- Cross-run `causation_id` — `causation_id` must not point to an event of a different `correlation_id`.

### 9.3 Ordering and Delivery

- Consumers assuming global ordering across different aggregates.
- Consumers processing events without checking the idempotency store first.
- Terminal events (`run.completed`, `artifact.ready`, `sandbox.terminated`) causing side effects when delivered a second time.
- Replaying events with `is_replay: true` triggering real sandboxes, real artifact writes, or real approval notifications.

### 9.4 Publishers

- A service that does not own an aggregate emitting events for that aggregate. For example: the Agent Engine must not emit `artifact.*` events — that is the Artifact service's responsibility.
- A publisher not using the outbox for mandatory events (see section 6.2), instead calling the event bus directly after a DB write.

---

## 10. Mapping from State Transitions (doc 05) to Mandatory Events

### 10.1 Task

| State Transition | Mandatory Event |
|---|---|
| `draft → pending` | `task.submitted` |
| `pending → running` | `task.started` |
| `running → waiting_approval` | `task.approval_requested` + `approval.requested` |
| `waiting_approval → running` | `task.approved` + `approval.approved` |
| `waiting_approval → cancelled` | `task.rejected` + `approval.rejected` |
| `running → completed` | `task.completed` |
| `running → failed` | `task.failed` |
| `* → cancelled` | `task.cancelled` |
| `* → archived` | `task.archived` |

### 10.2 Run

| State Transition | Mandatory Event |
|---|---|
| Run is created | `run.queued` |
| `queued → preparing` | `run.preparing` |
| `preparing → running` | `run.started` |
| `running → waiting_approval` | `run.approval_requested` + `approval.requested` |
| `waiting_approval → running` | `run.approved` + `approval.approved` |
| `running → completing` | `run.completing` |
| `completing → completed` | `run.completed` |
| `* → failed` | `run.failed` |
| `* → cancelled` | `run.cancelled` |
| `running → timed_out` | `run.timed_out` |

### 10.3 Step

| State Transition | Mandatory Event |
|---|---|
| `pending → running` | `step.started` |
| `running → waiting_approval` | `step.approval_requested` + `approval.requested` |
| `waiting_approval → running` | `step.approved` + `approval.approved` |
| `running → blocked` | `step.blocked` |
| `blocked → running` | `step.unblocked` |
| `running → completed` | `step.completed` |
| `* → failed` | `step.failed` |
| `pending → skipped` | `step.skipped` |
| `* → cancelled` | `step.cancelled` |

### 10.4 AgentInvocation

| State Transition | Mandatory Event |
|---|---|
| `initializing → running` | `agent_invocation.started` |
| `running → waiting_human` | `agent_invocation.waiting_human` |
| `waiting_human → running` | `agent_invocation.human_responded` |
| `running → waiting_tool` | `agent_invocation.waiting_tool` |
| `waiting_tool → running` | `agent_invocation.tool_result_received` |
| `* → completed` | `agent_invocation.completed` |
| `* → failed` | `agent_invocation.failed` |
| `* → interrupted` | `agent_invocation.interrupted` + `sandbox.terminate_requested` |
| `* → compensating` | `agent_invocation.compensating` |
| `compensating → compensated` | `agent_invocation.compensated` |

### 10.5 Sandbox

| State Transition | Mandatory Event |
|---|---|
| `provisioning → ready` | `sandbox.provisioned` |
| `ready/idle → executing` | `sandbox.executing` |
| `executing → idle` | `sandbox.idle` |
| `* → failed` | `sandbox.failed` |
| Receives `sandbox.terminate_requested` | `sandbox.terminating` |
| `terminating → terminated` | `sandbox.terminated` |

### 10.6 Artifact

| State Transition | Mandatory Event |
|---|---|
| `pending` is created | `artifact.registered` |
| `pending → writing` | `artifact.writing` |
| `writing → ready` | `artifact.ready` |
| `* → failed` | `artifact.failed` |
| `ready → superseded` | `artifact.superseded` |
| `* → archived` | `artifact.archived` |

---

## 11. Intentionally Deferred Decisions

| Item | Reason for Deferral |
|---|---|
| Detailed schema of each `payload` | Depends on API Contracts (doc 07) — payload must be consistent with API response shape |
| Dead letter queue handling and alert routing | Depends on the Observability model (doc 11) |
| Specific event bus technology (Kafka, NATS, Postgres LISTEN/NOTIFY) | Depends on deployment topology (doc 13) |
| `is_replay` propagation mechanism | Depends on implementation of replay infrastructure |
| Detailed correction event convention | Sufficient to lock down after encountering a few real-world correction cases |

---

## 12. Next Steps

The next document is **07 — API Contracts**: locking down the surface area of each service — endpoints, request/response shapes, auth, versioning, and mapping from the event model to API semantics. The event payload schema (section 11) will be locked down in parallel with doc 07.
