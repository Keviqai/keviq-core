# 05 — State Machines

**Status:** Draft v1.0
**Dependencies:** 04 Core Domain Model
**Objective:** Lock down the operational lifecycle of every dynamic entity in the system — serving as the foundation for Event Contracts (06), API Contracts (07), and observability/recovery logic.

Each state machine is written according to a fixed framework:
1. Purpose of the lifecycle
2. List of valid states
3. Valid state transitions
4. Actors permitted to trigger transitions
5. Mandatory side effects
6. Events that must be emitted
7. What is invalid and must be rejected

---

## 1. Task Lifecycle

### 1.1 Purpose

A Task is the declaration of a user's business intent. The Task lifecycle reflects the lifespan of that intent — from creation to outcome or cancellation. A Task does not execute itself — it spawns Runs for execution.

### 1.2 Valid States

| State | Meaning |
|---|---|
| `draft` | Task is being drafted, not yet ready for execution |
| `pending` | Task has been submitted, awaiting orchestrator scheduling |
| `running` | At least one Run is currently active |
| `waiting_approval` | Task is paused awaiting human approval at the Task level |
| `completed` | All required Runs have finished and produced artifacts |
| `failed` | Task ended due to an unrecoverable error |
| `cancelled` | Task was cancelled by user or policy |
| `archived` | Task has been completed/cancelled and moved to storage |

### 1.3 Valid State Transitions

```
draft ──────────────────────────► pending
pending ────────────────────────► running
pending ────────────────────────► cancelled
running ────────────────────────► waiting_approval
running ────────────────────────► completed
running ────────────────────────► failed
running ────────────────────────► cancelled
waiting_approval ───────────────► running          (approved)
waiting_approval ───────────────► cancelled         (rejected or timeout)
completed ──────────────────────► archived
failed ─────────────────────────► pending           (human re-submit)
failed ─────────────────────────► archived
cancelled ──────────────────────► archived
```

**There is no reverse transition from `completed` → `running`.** If re-execution is needed, create a new Task or create a new Run on the existing Task.

### 1.4 Actors Permitted to Trigger Transitions

| Transition | Permitted Actor |
|---|---|
| `draft → pending` | User (submit) |
| `pending → running` | Orchestrator |
| `pending → cancelled` | User, Policy enforcement |
| `running → waiting_approval` | Orchestrator (upon encountering an approval gate) |
| `running → completed/failed` | Orchestrator |
| `running → cancelled` | User, Policy enforcement |
| `waiting_approval → running` | User (approver), Policy (auto-approve) |
| `waiting_approval → cancelled` | User (reject), Policy (timeout) |
| `failed → pending` | User (re-submit) |
| `*/→ archived` | System (scheduled archival) |

### 1.5 Mandatory Side Effects

- `pending → running`: Orchestrator creates the first Run.
- `running → cancelled`: **All active child Runs must be terminated.** No Run may continue after the Task is cancelled.
- `running → failed`: Orchestrator writes an error summary to the Task. All active child Runs are terminated.
- `completed`: Orchestrator confirms that at least one `ready` Artifact exists for this Task.
- `failed → pending`: Orchestrator creates a new Run — does not resume an old Run.

### 1.6 Events That Must Be Emitted

| Event | When |
|---|---|
| `task.submitted` | `draft → pending` |
| `task.started` | `pending → running` |
| `task.approval_requested` | `running → waiting_approval` |
| `task.approved` | `waiting_approval → running` |
| `task.rejected` | `waiting_approval → cancelled` |
| `task.completed` | `running → completed` |
| `task.failed` | `running → failed` |
| `task.cancelled` | `* → cancelled` |
| `task.archived` | `* → archived` |

### 1.7 Invalid — Must Be Rejected

- Transition `completed → running` or `completed → pending` — not permitted.
- Transition `cancelled → running` — not permitted. A new Task must be created.
- Any layer other than the Orchestrator transitioning Task state (except User cancel and User re-submit).
- Task marked `completed` when no `ready` Artifact exists.
- Task in `waiting_approval` transitioning to `running` without an actor.

---

## 2. Run Lifecycle

### 2.1 Purpose

A Run is a specific execution instance of a Task. It records the entire process from start to outcome. Multiple Runs can exist on the same Task (retry, manual re-run, experimental). A Run cannot be resumed — if it fails, create a new Run.

### 2.2 Valid States

| State | Meaning |
|---|---|
| `queued` | Run has been created, awaiting resources |
| `preparing` | Orchestrator is preparing the sandbox, loading config, binding secrets |
| `running` | Currently executing Steps |
| `waiting_approval` | Paused awaiting approval at the Run/Step level |
| `completing` | All Steps finished, finalizing artifacts |
| `completed` | Run ended successfully with artifacts |
| `failed` | Run ended due to an error |
| `cancelled` | Run was cancelled |
| `timed_out` | Run exceeded the time limit |

### 2.3 Valid State Transitions

```
queued ─────────────────────────► preparing
queued ─────────────────────────► cancelled
preparing ──────────────────────► running
preparing ──────────────────────► failed        (config/secret load error)
preparing ──────────────────────► cancelled
running ────────────────────────► waiting_approval
running ────────────────────────► completing
running ────────────────────────► failed
running ────────────────────────► cancelled
running ────────────────────────► timed_out
waiting_approval ───────────────► running
waiting_approval ───────────────► cancelled
completing ─────────────────────► completed
completing ─────────────────────► failed        (artifact write error)
timed_out ──────────────────────► cancelled     (system cleanup)
```

**Runs do not have `resume`.** When a Run fails or is cancelled, it is permanently terminated. The Orchestrator creates a new Run if retry is needed.

### 2.4 Actors Permitted to Trigger Transitions

| Transition | Actor |
|---|---|
| `queued → preparing` | Orchestrator |
| `queued/preparing/running → cancelled` | User, Policy, Task cancellation cascade |
| `preparing → running` | Orchestrator |
| `running → waiting_approval` | Orchestrator (approval gate within a Step) |
| `running → completing/failed/timed_out` | Orchestrator |
| `waiting_approval → running` | User (approver), Policy (auto-approve) |
| `waiting_approval → cancelled` | User (reject), Policy (timeout) |
| `completing → completed/failed` | Orchestrator (after artifact finalization) |

### 2.5 Mandatory Side Effects

- `queued → preparing`: Lock `run_config` — modifications are not permitted after this step.
- `preparing → running`: Orchestrator initializes the first Step.
- `running → cancelled` (due to Task cancel cascade): All active Steps and AgentInvocations must terminate.
- `running → timed_out`: Equivalent to cancel — terminate all Steps, AgentInvocations, and child Sandboxes.
- `completing → completed`: Artifact service confirms all Artifacts have a valid `checksum`.
- `completing → failed`: Partial artifacts (if any) are retained with status `failed`, not deleted.

### 2.6 Events That Must Be Emitted

| Event | When |
|---|---|
| `run.queued` | Run is created |
| `run.preparing` | `queued → preparing` |
| `run.started` | `preparing → running` |
| `run.approval_requested` | `running → waiting_approval` |
| `run.approved` | `waiting_approval → running` |
| `run.completing` | `running → completing` |
| `run.completed` | `completing → completed` |
| `run.failed` | `* → failed` |
| `run.cancelled` | `* → cancelled` |
| `run.timed_out` | `running → timed_out` |

### 2.7 Invalid — Must Be Rejected

- Resuming a Run that is `failed`, `cancelled`, or `timed_out` — not permitted.
- Modifying `run_config` after the Run leaves `queued`.
- `completed` while Steps are still running.
- `completed` while Artifacts have not been finalized.
- Any Step continuing to run after the Run has transitioned to `cancelled`.

---

## 3. Step Lifecycle

### 3.1 Purpose

A Step is the smallest trace unit within a Run. All timeline, observability, and recovery operations are anchored to Steps. A Step does not make logic decisions on its own — it is a unit of record for "what was done, what was the input, what was the output, what was the state".

### 3.2 Valid States

| State | Meaning |
|---|---|
| `pending` | Step has been created, awaiting completion of the previous Step |
| `running` | Step is currently executing |
| `waiting_approval` | Step is paused awaiting human approval before continuing |
| `blocked` | Step cannot continue due to an unsatisfied dependency (not an approval) |
| `completed` | Step completed successfully |
| `failed` | Step ended with an error |
| `skipped` | Step was skipped due to a logic condition |
| `cancelled` | Step was cancelled because the Run was cancelled |

**Distinguishing `waiting_approval` from `blocked`:**
- `waiting_approval`: The Step can continue immediately upon human approval. The system is waiting for a person.
- `blocked`: The Step cannot continue because a technical condition is not yet satisfied (e.g., a dependency Step has not finished, a resource is not ready). The system is waiting for the system.

### 3.3 Valid State Transitions

```
pending ─────────────────────────► running
pending ─────────────────────────► skipped       (condition false)
pending ─────────────────────────► cancelled
running ─────────────────────────► waiting_approval
running ─────────────────────────► blocked
running ─────────────────────────► completed
running ─────────────────────────► failed
running ─────────────────────────► cancelled
waiting_approval ────────────────► running        (approved)
waiting_approval ────────────────► cancelled      (rejected)
blocked ─────────────────────────► running        (dependency resolved)
blocked ─────────────────────────► failed         (dependency failed/timeout)
blocked ─────────────────────────► cancelled
```

### 3.4 Actors Permitted to Trigger Transitions

| Transition | Actor |
|---|---|
| `pending → running/skipped` | Orchestrator |
| `running → waiting_approval` | Orchestrator (upon encountering an approval gate) |
| `running → blocked` | Orchestrator (dependency check) |
| `running → completed/failed` | Orchestrator |
| `waiting_approval → running` | User (approver) |
| `waiting_approval → cancelled` | User (reject) |
| `blocked → running` | Orchestrator (dependency watcher) |
| `blocked → failed` | Orchestrator (dependency resolution timeout) |
| `* → cancelled` | Run cancellation cascade |

### 3.5 Mandatory Side Effects

- `pending → running`: Record `started_at`, record `input_snapshot`.
- `running → completed`: Record `completed_at`, record `output_snapshot`.
- `running → failed`: Record `error_detail`.
- `running → waiting_approval`: Orchestrator issues an approval request, records the information the approver needs.
- `blocked → failed`: Orchestrator records the dependency failure reason in `error_detail`.
- `* → cancelled` (cascade from Run): The Step must not emit any further side effects after being cancelled.

### 3.6 Events That Must Be Emitted

| Event | When |
|---|---|
| `step.started` | `pending → running` |
| `step.approval_requested` | `running → waiting_approval` |
| `step.approved` | `waiting_approval → running` |
| `step.blocked` | `running → blocked` |
| `step.unblocked` | `blocked → running` |
| `step.completed` | `running → completed` |
| `step.failed` | `* → failed` |
| `step.skipped` | `pending → skipped` |
| `step.cancelled` | `* → cancelled` |

### 3.7 Invalid — Must Be Rejected

- A Step transitioning state without a parent Run in `running` or `waiting_approval`.
- `completed` when `output_snapshot` has not been recorded.
- `waiting_approval` and `blocked` existing simultaneously on the same Step.
- A Step continuing after its parent Run has been `cancelled`.

---

## 4. AgentInvocation Lifecycle

### 4.1 Purpose

An AgentInvocation is a single call into the agent runtime — encompassing the entire reasoning loop, tool calls, and multi-turn interactions. Its lifecycle must describe: a successful invocation, a failed invocation, an interrupted invocation, one awaiting human input, and one that has been compensated after failure.

### 4.2 Valid States

| State | Meaning |
|---|---|
| `initializing` | Agent runtime is being initialized, context is being loaded |
| `running` | Agent is in the reasoning/tool-use loop |
| `waiting_human` | Agent has issued a question/request for user input |
| `waiting_tool` | Agent is waiting for a tool call result to complete |
| `completed` | Agent finished successfully with output |
| `failed` | Agent ended with an unrecoverable error |
| `interrupted` | Invocation was stopped externally (Run cancel, timeout, policy violation) |
| `compensating` | Performing rollback/cleanup after failure (if compensation logic exists) |
| `compensated` | Compensation completed |

### 4.3 Valid State Transitions

```
initializing ───────────────────► running
initializing ───────────────────► failed          (context load error)
initializing ───────────────────► interrupted
running ────────────────────────► waiting_human
running ────────────────────────► waiting_tool
running ────────────────────────► completed
running ────────────────────────► failed
running ────────────────────────► interrupted
waiting_human ──────────────────► running          (human responded)
waiting_human ──────────────────► interrupted      (timeout / cancel)
waiting_tool ───────────────────► running          (tool result received)
waiting_tool ───────────────────► failed           (tool error, non-retryable)
waiting_tool ───────────────────► interrupted
failed ─────────────────────────► compensating     (if compensation handler exists)
failed ─────────────────────────► (terminal)       (if no compensation handler)
interrupted ────────────────────► compensating     (if cleanup is needed)
interrupted ────────────────────► (terminal)
compensating ───────────────────► compensated
compensating ───────────────────► failed           (compensation also failed)
```

### 4.4 Relationship with Sandbox

- When AgentInvocation → `interrupted`: The Sandbox must be terminated. The Sandbox does not transition to `terminated` on its own — it receives a terminate signal from the Execution layer when the AgentInvocation is interrupted.
- When the Sandbox is unexpectedly terminated externally: The AgentInvocation must transition to `interrupted`, not `failed`. `failed` is reserved for logic/model errors only.
- These two lifecycles **must not be conflated**: a Sandbox can be `terminated` while the AgentInvocation is still `compensating`.

### 4.5 Actors Permitted to Trigger Transitions

| Transition | Actor |
|---|---|
| `initializing → running` | Agent Engine |
| `running → waiting_human` | Agent Engine (agent decides to ask the user) |
| `running → waiting_tool` | Agent Engine (tool call is dispatched) |
| `running → completed/failed` | Agent Engine |
| `waiting_human → running` | User (via UI/API), with input recorded in the Step |
| `waiting_tool → running/failed` | Tool/Execution layer (returns result) |
| `* → interrupted` | Orchestrator (cascade from Run/Step cancel or policy) |
| `failed/interrupted → compensating` | Agent Engine (if compensation handler exists) |
| `compensating → compensated/failed` | Agent Engine |

### 4.6 Mandatory Side Effects

- `initializing → running`: Record `started_at`, snapshot `input_messages`.
- `running → waiting_human`: Orchestrator notifies the UI that a question is awaiting the user.
- `completed`: Record `output_messages`, `tool_calls`, `prompt_tokens`, `completion_tokens`, `total_cost_usd`.
- `* → interrupted`: Send terminate signal to the corresponding Sandbox.
- `compensating → compensated`: Record cleanup result in the Step `output_snapshot`.

### 4.7 Events That Must Be Emitted

| Event | When |
|---|---|
| `agent_invocation.started` | `initializing → running` |
| `agent_invocation.waiting_human` | `running → waiting_human` |
| `agent_invocation.waiting_tool` | `running → waiting_tool` |
| `agent_invocation.completed` | `* → completed` |
| `agent_invocation.failed` | `* → failed` |
| `agent_invocation.interrupted` | `* → interrupted` |
| `agent_invocation.compensating` | `* → compensating` |
| `agent_invocation.compensated` | `compensating → compensated` |

### 4.8 Invalid — Must Be Rejected

- `completed` when `output_messages` or `total_cost_usd` has not been recorded.
- Agent self-transitioning to `interrupted` — only the Orchestrator may interrupt.
- AgentInvocation continuing to `running` after its parent Step has been `cancelled`.
- Creating an Artifact directly from the Agent Engine — must go through the Artifact service.

---

## 5. Sandbox Lifecycle

### 5.1 Purpose

A Sandbox is an ephemeral execution environment. The Sandbox lifecycle is entirely independent of the Agent's reasoning — it only reflects the state of the runtime environment, not the logic of the work.

### 5.2 Valid States

| State | Meaning |
|---|---|
| `provisioning` | Sandbox is being created (container/VM spin up) |
| `ready` | Sandbox is ready to receive execution commands |
| `executing` | Sandbox is executing a command |
| `idle` | Sandbox is waiting for the next command (between tool calls) |
| `terminating` | Sandbox is being shut down |
| `terminated` | Sandbox has fully stopped |
| `failed` | Sandbox encountered an unrecoverable error (crash, OOM, policy violation) |

### 5.3 Valid State Transitions

```
provisioning ───────────────────► ready
provisioning ───────────────────► failed
ready ──────────────────────────► executing
ready ──────────────────────────► terminating    (signal from Orchestrator)
executing ──────────────────────► idle
executing ──────────────────────► failed         (execution error, policy violation)
executing ──────────────────────► terminating    (signal from Orchestrator)
idle ───────────────────────────► executing
idle ───────────────────────────► terminating
failed ─────────────────────────► terminating    (cleanup)
terminating ────────────────────► terminated
```

### 5.4 Relationship with AgentInvocation

- When AgentInvocation → `interrupted`: The Execution layer sends a terminate signal → Sandbox `terminating → terminated`.
- When Sandbox → `failed` unexpectedly: The Execution layer notifies the Orchestrator → Orchestrator interrupts the AgentInvocation.
- The Sandbox must not decide on its own to interrupt the AgentInvocation — it only reports its state.

### 5.5 Actors Permitted to Trigger Transitions

| Transition | Actor |
|---|---|
| `provisioning → ready/failed` | Execution layer |
| `ready/idle → executing` | Execution layer (receives tool call from Agent Engine) |
| `executing → idle` | Execution layer (tool call completed) |
| `executing/idle/ready → terminating` | Execution layer (receives terminate signal from Orchestrator) |
| `failed → terminating` | Execution layer (auto cleanup) |
| `terminating → terminated` | Execution layer |

**The UI layer must not call the Sandbox directly — this is an immutable invariant.**

### 5.6 Mandatory Side Effects

- `provisioning → ready`: Record `started_at`, apply `policy_snapshot` and `resource_limits`.
- `executing → failed` (policy violation): Record the violation in the audit log before transitioning to `terminating`.
- `terminating → terminated`: Record `terminated_at`, `termination_reason`. All data within the sandbox is wiped — there is no persistence after `terminated`.

### 5.7 Events That Must Be Emitted

| Event | When |
|---|---|
| `sandbox.provisioned` | `provisioning → ready` |
| `sandbox.executing` | `ready/idle → executing` |
| `sandbox.idle` | `executing → idle` |
| `sandbox.failed` | `* → failed` |
| `sandbox.terminating` | `* → terminating` |
| `sandbox.terminated` | `terminating → terminated` |

### 5.8 Invalid — Must Be Rejected

- Sandbox persisting internal state after `terminated`.
- Sandbox receiving commands directly from the UI layer.
- Sandbox continuing to `executing` after receiving a terminate signal.
- `policy_snapshot` being modified after the Sandbox leaves `provisioning`.

---

## 6. Artifact Lifecycle

### 6.1 Purpose

An Artifact is a long-lived output. The Artifact lifecycle must be forward-only immutable — no silent mutations are permitted after `ready`. Partial data from failures must be retained and clearly marked.

### 6.2 Valid States

| State | Meaning |
|---|---|
| `pending` | Artifact has been registered, no data yet |
| `writing` | Data is being written to storage |
| `ready` | Artifact is complete, has a checksum, and is readable |
| `failed` | The write process failed — partial data (if any) is retained |
| `superseded` | Artifact has been replaced by a newer artifact in the same lineage |
| `archived` | Artifact has been moved to cold storage, still readable |

### 6.3 Valid State Transitions

```
pending ─────────────────────────► writing
pending ─────────────────────────► failed         (unable to initialize storage)
writing ─────────────────────────► ready
writing ─────────────────────────► failed          (write error)
ready ───────────────────────────► superseded      (when a new artifact in the lineage is created)
ready ───────────────────────────► archived
superseded ──────────────────────► archived
failed ──────────────────────────► archived        (retains partial data, clearly marked)
```

**There are no reverse state transitions.** `ready → writing` is absolutely invalid.
**There is no `deleted` state.** Artifacts can only be `archived`.

### 6.4 Handling Failed Artifacts

- Partial data (if any) **must be retained** — not deleted.
- `checksum` is left empty or set to `null`.
- `artifact_status = failed` with `metadata.failure_reason` clearly stating the cause.
- A `failed` Artifact can still have its partial data read for debugging purposes.
- A `failed` Artifact **must not be used as input** for subsequent Steps/Runs.

### 6.5 Actors Permitted to Trigger Transitions

| Transition | Actor |
|---|---|
| `pending → writing` | Artifact service (after AgentInvocation completes) |
| `writing → ready` | Artifact service (after checksum verification) |
| `writing/pending → failed` | Artifact service |
| `ready → superseded` | Artifact service (when a new artifact is created in the lineage) |
| `ready/superseded/failed → archived` | System (scheduled archival) |

**AgentInvocation and Agent Engine must not directly create or write Artifacts.**

### 6.6 Mandatory Side Effects

- `writing → ready`: Record `checksum` (SHA-256), record `size_bytes`. This checksum is **permanently immutable**.
- `ready → superseded`: Record `superseded_by_artifact_id` in metadata.
- `* → archived`: Move file to cold storage tier, update `storage_ref`.

### 6.7 Events That Must Be Emitted

| Event | When |
|---|---|
| `artifact.registered` | `pending` is created |
| `artifact.writing` | `pending → writing` |
| `artifact.ready` | `writing → ready` |
| `artifact.failed` | `* → failed` |
| `artifact.superseded` | `ready → superseded` |
| `artifact.archived` | `* → archived` |

### 6.8 Invalid — Must Be Rejected

- Mutating the content of a `ready` Artifact — absolutely not permitted.
- Deleting a `failed` Artifact — must archive, not delete.
- Using a `failed` Artifact as input for a Run/Step.
- `checksum` being modified after the Artifact reaches `ready`.
- Artifact being created directly from the Agent Engine, bypassing the Artifact service.

---

## 7. Approval Flow

### 7.1 Purpose

The approval flow is a mechanism for pausing operations while awaiting a human decision. It can exist at the Task, Run, or Step level — and must not distort the lifecycle of the containing entity.

### 7.2 Approval Levels

| Level | When to Use | Impact |
|---|---|---|
| **Task** | Need to approve the overall strategy before any Run begins | Task enters `waiting_approval`, no Runs are created |
| **Run** | Need to approve a specific execution before it continues | Run enters `waiting_approval`, running Steps are paused |
| **Step** | Need to approve a specific action before the Step continues | Step enters `waiting_approval`, Run remains `running` |

**Step-level approval is the most common** — for example: approving before an agent executes a destructive command.

### 7.3 ApprovalRequest Entity (Embedded, Not an Aggregate)

An ApprovalRequest is not a standalone entity — it is recorded through Events and Step/Run/Task metadata.

| Field | Type | Description |
|---|---|---|
| `approval_id` | UUID | |
| `target_type` | enum | `task`, `run`, `step` |
| `target_id` | UUID | |
| `requested_by` | enum | `orchestrator`, `policy` |
| `requested_at` | timestamp | |
| `approver_role` | string | Role permitted to approve |
| `prompt` | text | Information displayed to the approver |
| `timeout_at` | timestamp | After this point, automatically rejected |
| `decision` | enum | `pending`, `approved`, `rejected`, `timed_out` |
| `decided_by_id` | UUID → User | |
| `decided_at` | timestamp | |

### 7.4 Timeout Behavior

- When `timeout_at` is reached without a decision: The Approval automatically transitions to `timed_out`.
- `timed_out` is equivalent to `rejected` in lifecycle terms — the parent entity transitions to `cancelled`.
- Policy can configure `timed_out → auto_approved` instead of `cancelled` (opt-in).

### 7.5 Events That Must Be Emitted

| Event | When |
|---|---|
| `approval.requested` | ApprovalRequest is created |
| `approval.approved` | User approves |
| `approval.rejected` | User rejects |
| `approval.timed_out` | Timeout without a decision |

### 7.6 Invalid

- An Approval being automatically approved without an actor (unless Policy explicitly allows auto-approve).
- The same target having two active ApprovalRequests simultaneously.
- An ApprovalRequest existing after the parent entity has been `cancelled` or `completed`.

---

## 8. Summary: Cascade on Cancel

This is the point most likely to cause inconsistency — must be locked down clearly:

```
Task cancelled
  └── all Runs in [queued, preparing, running, waiting_approval] → cancelled
        └── all Steps in [pending, running, waiting_approval, blocked] → cancelled
              └── all AgentInvocations in [initializing, running, waiting_human, waiting_tool] → interrupted
                    └── all Sandboxes in [provisioning, ready, executing, idle] → terminating → terminated
```

**Termination order: inside-out** — Sandbox first, then AgentInvocation, then Step, then Run, then Task.
**No side effects are permitted after an entity has been `cancelled`.**

---

## 9. Intentionally Deferred Decisions

| Item | Reason for Deferral |
|---|---|
| Specific retry policy (retry count, backoff strategy) | Depends on the Policy model (doc 09) |
| Detailed compensation logic for AgentInvocation | Depends on each agent type and tool type |
| Auto-approve conditions in Policy | Depends on the Permission model (doc 09) |
| Approval routing (who receives notifications) | Depends on the Member/role model |
| Archival schedule and cold storage policy | Depends on deployment topology (doc 13) |

---

## 10. Next Steps

The next document is **06 — Event Contracts**: locking down the standard schema for all events listed in this document, including payload structure, idempotency key, ordering assumptions, retry semantics, and correlation/causation chain.
