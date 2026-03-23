# 15 — Backend Service Map

**Status:** Draft v1.0
**Dependencies:** 03 Bounded Contexts, 04 Core Domain Model, 06 Event Contracts, 09 Permission Model, 13 Deployment Topology, Gate Review 00–12
**Objective:** Lock the backend service list, ownership, DB/schema, command/event responsibilities, sync vs async interfaces, restart/recovery duties, and "must not do" constraints for each service.

---

## 1. Immutable Service Map Principles

**S1 — Each service owns a set of non-overlapping DB schemas.**
No schema is owned by two services. "Shared schema" is a prohibited pattern.

**S2 — State transition authority is inviolable.**
Only `orchestrator-service` may mutate `Task/Run/Step.*_status`. All other services read via API or events — no direct writes.

**S3 — Each service is responsible for its own post-crash reconciliation.**
There is no "global recovery manager." Each service has its own recovery duty, following the startup order from doc 13.

**S4 — Async-first, sync only when justified.**
Inter-service communication defaults to event-driven. Sync calls (HTTP/gRPC) are only permitted for: read queries needing immediate responses, commands needing instant user acknowledgment, or health checks.

**S5 — Services must not call external providers directly — they must go through the corresponding gateway.**
Model calls must go through `model-gateway`. Secret access must go through `secret-broker`. No domain service holds API keys directly.

---

## 2. Service Inventory

| # | Service Name | Bounded Context | DB Schema | Tier |
|---|---|---|---|---|
| SVC-01 | `orchestrator-service` | Task Orchestration (C3) | `orchestrator_core` | Critical |
| SVC-02 | `agent-runtime-service` | Agent Runtime (C4) | `agent_runtime` | Critical |
| SVC-03 | `artifact-service` | Artifact and File (C7) | `artifact_core` | Critical |
| SVC-04 | `execution-service` | Execution and Sandbox (C6) | `execution_core` | Critical |
| SVC-05 | `api-gateway` | Web Shell / Control (C11) | None | Critical |
| SVC-06 | `sse-gateway` | Web Shell / Control (C11) | None | Important |
| SVC-07 | `auth-service` | Identity and Access (C1) | `identity_core` | Critical |
| SVC-08 | `workspace-service` | Workspace (C2) | `workspace_core` | Critical |
| SVC-09 | `policy-service` | Identity and Access (C1) | `policy_core` | Critical |
| SVC-10 | `secret-broker` | Execution and Sandbox (C6) | `secret_core` | Critical |
| SVC-11 | `model-gateway` | Model Gateway (C9) | `model_gateway_core` | Critical |
| SVC-12 | `audit-service` | Event and Telemetry (C8) | `audit_core` | Critical |
| SVC-13 | `event-store-service` | Event and Telemetry (C8) | `event_core` | Critical |
| SVC-14 | `notification-service` | Human Control (C10) | `notification_core` | Important |
| SVC-15 | `telemetry-service` | Event and Telemetry (C8) | None | Supporting |

---

## 3. Service Detail

---

### SVC-01 `orchestrator-service`

**Purpose:** State transition authority for Task/Run/Step. Orchestrates the entire execution flow.

**DB Schema:** `orchestrator_core`
**Tables owned:** `tasks`, `runs`, `steps`, `approval_requests`, `retry_policies`, `outbox_orchestrator`

**Responsibilities:**

- Create and mutate Task/Run/Step state — **the only entity with this authority**
- Timeout watcher for ApprovalRequest (does not depend solely on a scheduler — PP8)
- Cascade cancel: Task → Run → Step (inside-out order from doc 05)
- Create new Run when human re-submits (do not resume old Run — DNB1)
- Emit command-like event `sandbox.terminate_requested` when Step is cancelled
- Defensively reconcile approval timeout when processing any event for that workspace

**Command interfaces (sync — received from api-gateway):**

| Command | Trigger | Action |
|---|---|---|
| `SubmitTask` | User | Validate, create Task, emit `task.submitted` |
| `CancelTask` | User / Policy | Cascade cancel, emit events |
| `ApproveGate` | User | Resolve approval, resume Run |
| `RejectGate` | User | Reject approval, cancel entity |
| `RerunTask` | User | Create new Run on a failed Task |

**Event published (outbox):**

All `task.*`, `run.*`, `step.*`, `approval.*` events listed in doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `agent_invocation.completed` | Advance Step → completed, check Run completion |
| `agent_invocation.failed` | Fail Step, propagate |
| `agent_invocation.interrupted` | Update Step, continue cascade |
| `sandbox.terminated` | Confirm cleanup, unblock if needed |
| `artifact.ready` | Confirm Run artifact finalized |
| `approval.timed_out` | Resolve gate, cancel entity |

**Recovery duty (PP2, PP3 from gate review):**

1. Flush outbox backlog.
2. Rebuild Task/Run/Step state from `event_core` log with `correlation_id`.
3. Resume timeout watchers.
4. Only then accept new commands.

**Must not do:**

- Direct write to any other service's schema.
- Self-grant permissions (delegate through `policy-service`).
- Call model provider directly.
- Resume a failed Run (DNB1).
- Transition `run.timed_out` without also emitting `run.cancelled` in the same outbox transaction.

---

### SVC-02 `agent-runtime-service`

**Purpose:** Run AgentInvocations, maintain the reasoning loop, orchestrate tool calls.

**DB Schema:** `agent_runtime`
**Tables owned:** `agent_invocations`, `tool_calls`, `runtime_states`, `outbox_agent_runtime`

**Responsibilities:**

- Receive AgentInvocation assignment from Orchestrator
- Maintain the reasoning loop and multi-turn state
- Dispatch tool calls via the Tool/Execution layer
- Call models through `model-gateway` — **not directly**
- Emit `agent_invocation.*` events
- After crash: reconcile invocation state from event log **before** accepting new work (PP3)

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `StartInvocation` | Orchestrator | Initialize AgentInvocation |
| `InterruptInvocation` | Orchestrator | Interrupt in-flight invocation |
| `ResumeWithHumanInput` | Orchestrator (relayed from user) | Resume `waiting_human` invocation |
| `DeliverToolResult` | execution-service | Resume `waiting_tool` invocation |

**Event published (outbox):**

All `agent_invocation.*` events from doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `sandbox.failed` | Interrupt affected invocation |
| `sandbox.terminated` | Confirm execution environment gone |

**Recovery duty (PP3 — critical):**

1. Query event log: all `agent_invocation.started` without a terminal event.
2. For each dangling invocation: emit `agent_invocation.interrupted` + trigger `sandbox.terminate_requested`.
3. Only after reconciliation accept new StartInvocation.

**Must not do:**

- Create or write artifacts directly (FD9, DNB6).
- Hold model provider API keys (S5).
- Call sandbox/execution layer directly — must go through command/event.
- Self-determine state transitions for Task/Run/Step.
- Write to `orchestrator_core` schema.

---

### SVC-03 `artifact-service`

**Purpose:** Single write point for all artifacts. Manages lineage, taint, and signed URLs.

**DB Schema:** `artifact_core`
**Tables owned:** `artifacts`, `artifact_lineage_edges`, `artifact_provenance`, `signed_url_records`, `outbox_artifact`

**Object storage:** separate, only `artifact-service` has write credentials (PP10).

**Responsibilities:**

- Receive artifact registration from agent-runtime or execution-service — **not directly from agent code**
- Validate that the provenance tuple is complete before accepting (PP9, L5 from doc 10)
- Validate that model_version is not an alias (PP9)
- Detect lineage cycles when writing edges
- Propagate taint: write DB flag **before** emitting event (PP5, DNB11)
- Issue and revoke signed URLs (doc 10 section 6.2)
- Archive artifacts per policy

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `RegisterArtifact` | agent-runtime-service | Create artifact in `pending` state |
| `FinalizeArtifact` | agent-runtime-service | Write data, validate checksum, → `ready` |
| `RecordLineageEdge` | agent-runtime-service | Write edge, detect cycle |
| `TaintArtifact` | Security event (internal) / admin API | Set taint = true, emit event |
| `UntaintArtifact` | Admin user (artifact:untaint) | Clear taint, write review record |
| `IssueSignedUrl` | User request via api-gateway | Check state×taint×permission, issue URL |
| `ArchiveArtifact` | Scheduler / user | Transition → archived |

**Event published (outbox):**

All `artifact.*` events from doc 06, including `artifact.lineage_recorded`, `artifact.tainted`, `artifact.untainted`.

**Event consumed:**

| Event | Action |
|---|---|
| `security.violation` | Taint related artifact if in writing/ready state |
| `run.cancelled` | Mark pending artifacts of that run → failed |

**Recovery duty:**

- Verify that no artifact in `writing` state is orphaned after crash.
- For artifacts in `writing` state without a checksum: transition → `failed`, retain partial data.

**Must not do:**

- Accept artifact content directly from sandbox or agent code.
- Delete any artifact (archive only).
- Mutate the `checksum` of an artifact that is already `ready`.
- Issue a signed URL for a `tainted` artifact without blocking (doc 10 section 6.2).
- Write artifact as `ready` when the provenance tuple is incomplete (FR7, DNB12).

---

### SVC-04 `execution-service`

**Purpose:** Manage sandbox lifecycle, terminal sessions, secret mounting, and network policy enforcement.

**DB Schema:** `execution_core`
**Tables owned:** `sandboxes`, `sandbox_attempts`, `terminal_sessions`, `execution_logs_meta`, `outbox_execution`

**Responsibilities:**

- Provision sandbox per policy snapshot (immutable after provisioning — P7, DNB9 implied)
- Manage `sandbox_attempt_index` — supporting 1-N per AgentInvocation (PP4 from gate review)
- Mount filesystem, inject secrets via `secret-broker`, apply network policy
- Enforce egress policy (deny-by-default)
- Unmount `/secrets` **before** emitting `sandbox.terminated`
- Terminate sandbox upon receiving `sandbox.terminate_requested`
- Relay tool execution results back to agent-runtime-service

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `ProvisionSandbox` | Orchestrator (via agent-runtime) | Create new sandbox, apply policy |
| `ExecuteTool` | agent-runtime-service | Run tool in sandbox, return result |
| `TerminateSandbox` | Orchestrator / internal | Cleanup, emit `sandbox.terminated` |

**Event published (outbox):**

All `sandbox.*` events from doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `sandbox.terminate_requested` | Trigger termination flow |
| `run.cancelled` | Terminate all sandboxes for that run |
| `agent_invocation.interrupted` | Terminate sandbox for that invocation |

**Recovery duty:**

1. Enumerate sandboxes still active in `execution_core`.
2. Cross-reference with orchestrator state (via API or event log).
3. Sandbox with no active run → terminate and emit `sandbox.terminated`.
4. Emit missing events if a repair workflow allows.

**Must not do:**

- Call model provider directly (model provider keys must not be present in the execution layer).
- Retain secret values after sandbox is terminated.
- Allow UI to call directly (I1, invariant from doc 02).
- Continue execution after receiving a terminate signal.
- Modify `policy_snapshot` after provisioning (P7).

---

### SVC-05 `api-gateway`

**Purpose:** The sole entry point for client requests. Authn/authz entry. Response shaping.

**DB Schema:** None.

**Responsibilities:**

- Authn (validate JWT/session via `auth-service`)
- Authz pre-check (forward permission check to `policy-service` before forwarding command)
- Route commands to the correct domain service
- Inject `correlation_id` (= new trace_id if new request) into headers
- Shape responses for the client
- Rate limiting per workspace/user

**Sync interfaces:**

All REST/gRPC endpoints of the system. No direct writes to domain schemas.

**Must not do (PP1 — critical):**

- Direct write to any domain schema (orchestrator, artifact, agent_runtime, etc.).
- Hold domain secrets (only hold auth material).
- Bypass policy check when forwarding commands.
- Create a correlation_id different from trace_id (DNB7).

---

### SVC-06 `sse-gateway`

**Purpose:** Push real-time events to clients via Server-Sent Events.

**DB Schema:** None.

**Responsibilities:**

- Subscribe to event stream from `event-store-service` by `workspace_id`, `task_id`, `run_id`
- Fan-out events to connected clients
- Support `Last-Event-ID` for client reconnect without losing events
- Rate-limit reconnect per workspace (prevent thundering herd)

**Must not do:**

- Change execution semantics when down (DNB8 implied — SSE is only an observation layer).
- Hold event state — stateless relay only.
- Expose events from workspace A to a workspace B client.

---

### SVC-07 `auth-service`

**Purpose:** Identity, authn, session management.

**DB Schema:** `identity_core`
**Tables owned:** `users`, `sessions`, `auth_providers`, `org_memberships`

**Responsibilities:**

- Authenticate users via provider (local, OAuth, SSO)
- Issue and validate session tokens / JWTs
- Provide user identity to other services

**Fail-closed rule:**

When `auth-service` is down, `api-gateway` must deny all requests (doc 12 L7, doc 13).

**Must not do:**

- Perform any domain logic orchestration.
- Hold agent/sandbox credentials.

---

### SVC-08 `workspace-service`

**Purpose:** Manage workspaces, members, workspace-level settings and connections.

**DB Schema:** `workspace_core`
**Tables owned:** `workspaces`, `workspace_members`, `workspace_settings`, `workspace_connections`, `repo_snapshots`

**Responsibilities:**

- CRUD workspaces
- Manage members and role assignment
- Manage workspace-level connections (Git, storage, connectors)
- Ingest repo snapshots (trigger, does not run execution itself)

**Event published:** `workspace.*` events if needed.

**Must not do:**

- Execute code or run agents.
- Provision secrets (delegated to `secret-broker`).
- Mutate Task/Run state.

---

### SVC-09 `policy-service`

**Purpose:** Source of truth for Policy, permission resolution, policy snapshot generation.

**DB Schema:** `policy_core`
**Tables owned:** `policies`, `policy_rules`, `secret_bindings_meta`

**Responsibilities:**

- Store and version Policy per workspace/task/agent
- Resolve permissions via the 7-layer resolution order (doc 09 section 5)
- Generate `policy_snapshot` for sandbox provisioning
- Provide permission decisions to `api-gateway` and `orchestrator-service`

**Fail-closed rule (critical):**

When `policy-service` is unreachable → all permission checks → DENY (doc 09, doc 12 L7).

**Must not do:**

- Enforce policy directly at the sandbox (the snapshot is frozen; enforcement is the responsibility of execution-service).
- Allow Agent Runtime to self-request policy expansion.

---

### SVC-10 `secret-broker`

**Purpose:** Manage SecretBindings, inject secrets into sandboxes per policy.

**DB Schema:** `secret_core`
**Tables owned:** `secret_bindings`, `secret_refs`

**Important note:** `secret_core` only stores `secret_ref` (pointers) — it never stores actual secret values. Secret values reside in an external vault/KMS.

**Responsibilities:**

- Validate SecretBinding per permissions (doc 09 FD2, FD5)
- Mount secrets into sandbox per request from `execution-service`
- Revoke secret mount after sandbox is terminated

**Fail-closed rule:**

If `secret-broker` is down when a sandbox needs secrets → the sandbox is not provisioned (fails at `preparing`).

**Must not do:**

- Store actual secret values in DB.
- Grant secrets to agents directly (only inject into sandbox environment).
- Allow the UI layer to query secret values.

---

### SVC-11 `model-gateway`

**Purpose:** The sole service permitted to call LLM providers. Routing, fallback, cost tracking.

**DB Schema:** `model_gateway_core`
**Tables owned:** `model_usage_records`, `provider_configs`, `budget_policies`

**Responsibilities:**

- Route model calls to providers per policy
- Failover to backup provider when primary is down
- Track token usage and cost per workspace/invocation
- Resolve model version alias → specific version **before** passing through (PP9, DNB12)
- Enforce budget policy

**Must not do:**

- Hold provider keys in requests from agent/sandbox.
- Call provider directly from sandbox (enforcement at Boundary C — doc 13).
- Return a model alias in usage records — must be the specific version.

---

### SVC-12 `audit-service`

**Purpose:** Append-only audit trail for all permission decisions.

**DB Schema:** `audit_core`
**Tables owned:** `audit_records`

**Durability requirement:** Higher SLA than regular logs. Separate backup. Append-only enforced at DB level (no UPDATE/DELETE permissions on `audit_records`).

**Responsibilities:**

- Receive audit writes from all services with permission decisions
- Enforce append-only (no update, no delete)
- Serve audit queries for compliance/admin surfaces

**Fail-closed behavior:**

- Permission.violation write fail → fail-safe deny + P1 alert (doc 09 section 9.3)
- permission.allowed write fail → allow action but alert P1

**Must not do:**

- Update or delete a written record.
- Share write credentials with any service outside the audit write path.

---

### SVC-13 `event-store-service`

**Purpose:** Durable event log. Append-only. Source of truth for history.

**DB Schema:** `event_core`
**Tables owned:** `domain_events`, `outbox_relay_state`

**Responsibilities:**

- Receive events from outbox relay of each service
- Store append-only
- Serve event replay by `correlation_id` or scope (doc 06 retention)
- Provide stream for `sse-gateway` and recovery consumers

**Must not do:**

- Update or delete events after writing.
- Allow services to direct-insert bypassing the outbox relay.

---

### SVC-14 `notification-service`

**Purpose:** Send approval requests, human-in-the-loop notifications.

**DB Schema:** `notification_core`
**Tables owned:** `approval_notifications`, `notification_delivery_log`

**Responsibilities:**

- Subscribe to events: `approval.requested`, `agent_invocation.waiting_human`
- Send notifications to the correct approver by role
- Dedup by `approval_id` (do not send twice for the same approval — PP6 related)
- Log delivery status

**Must not do:**

- Self-decide approve/reject.
- Hold domain state for approvals.

---

### SVC-15 `telemetry-service`

**Purpose:** Aggregation of metrics, traces, alerting.

**DB Schema:** No domain schema — uses time-series store and tracing backend.

**Responsibilities:**

- Collect spans (OpenTelemetry)
- Collect metrics
- Evaluate alert rules (doc 11 section 5)
- Dashboard data aggregation

**Must not do:**

- Perform any execution or state mutation.
- Expose secrets or raw user content in metrics/traces (O1 from doc 11).

---

## 4. Inter-service Communication Map

### 4.1 Sync calls (HTTP/gRPC) — for queries and command acknowledgment only

```
api-gateway
  → auth-service          (authn validation)
  → policy-service        (authz pre-check)
  → orchestrator-service  (SubmitTask, CancelTask, ApproveGate, etc.)
  → artifact-service      (IssueSignedUrl, query metadata)
  → workspace-service     (workspace/member queries)
  → model-gateway         (from agent-runtime-service)
  → secret-broker         (from execution-service, mount secrets)
  → policy-service        (from execution-service, at sandbox provisioning)
```

### 4.2 Async (event-driven) — primary inter-service protocol

```
orchestrator-service ──────► event-store-service (outbox relay)
agent-runtime-service ─────► event-store-service
artifact-service ───────────► event-store-service
execution-service ──────────► event-store-service

event-store-service ────────► sse-gateway (fan-out to clients)
event-store-service ────────► orchestrator-service (consumed events)
event-store-service ────────► agent-runtime-service (consumed events)
event-store-service ────────► artifact-service (consumed events)
event-store-service ────────► execution-service (consumed events)
event-store-service ────────► notification-service (approval/human events)
event-store-service ────────► telemetry-service (metrics derivation)
```

### 4.3 Direct DB access — schema ownership enforced

```
orchestrator-service ──► orchestrator_core (READ+WRITE)
agent-runtime-service ─► agent_runtime (READ+WRITE)
artifact-service ───────► artifact_core (READ+WRITE)
execution-service ──────► execution_core (READ+WRITE)
auth-service ───────────► identity_core (READ+WRITE)
workspace-service ──────► workspace_core (READ+WRITE)
policy-service ─────────► policy_core (READ+WRITE)
secret-broker ──────────► secret_core (READ+WRITE)
model-gateway ──────────► model_gateway_core (READ+WRITE)
audit-service ──────────► audit_core (APPEND ONLY)
event-store-service ────► event_core (APPEND ONLY for domain_events)
notification-service ───► notification_core (READ+WRITE)

api-gateway: NO direct DB write to any domain schema
sse-gateway: NO DB schema
telemetry-service: NO domain schema
```

---

## 5. Pressure Points → Service Mapping

Every pressure point from the gate review must be addressed by a specific service:

| Pressure Point | Responsible Service | Mechanism |
|---|---|---|
| PP1 — State transition only through Orchestrator | `orchestrator-service` | Single domain method; no direct write from other services; enforced by DB credential isolation |
| PP2 — Orchestrator crash recovery | `orchestrator-service` | Flush outbox → rebuild from event log → resume watchers → accept commands |
| PP3 — Agent Engine rebuild after crash | `agent-runtime-service` | Query event log for dangling invocations → interrupt → only then accept new work |
| PP4 — Sandbox 1-N per AgentInvocation | `execution-service` | `sandbox_attempt_index` field; query filter `is_active = true` |
| PP5 — Taint write before event emit | `artifact-service` | DB write in outbox transaction before relay; taint does not depend on event |
| PP6 — `run.timed_out` → `run.cancelled` in same transaction | `orchestrator-service` | Two outbox entries in the same DB transaction |
| PP7 — Tool idempotency contract enforcement | `execution-service` + tool registry | `idempotent` flag mandatory in tool definition; CI idempotency test |
| PP8 — Approval timeout does not depend on scheduler | `orchestrator-service` | Defensive timeout check when processing any event for that workspace |
| PP9 — Model version must not be an alias | `model-gateway` | Resolve alias → version before passing; validate at artifact registration |
| PP10 — Artifact table isolation | `artifact-service` | Separate DB schema, separate DB user, separate object storage credentials |

---

## 6. Service Recovery Sequence (consolidated from doc 13)

```
Phase 1 — Infrastructure
  database + object storage + event infrastructure + audit storage

Phase 2 — Control services
  auth-service, policy-service, secret-broker, model-gateway, audit-service

Phase 3 — Artifact plane
  artifact-service
  (must be ready before orchestrator because orchestrator confirms artifact finalization)

Phase 4 — Orchestration plane
  orchestrator-service
  (rebuild from event log, flush outbox, resume watchers)

Phase 5 — Runtime plane
  agent-runtime-service
  (reconcile dangling invocations from event log)

Phase 6 — Execution plane
  execution-service
  (reconcile sandbox state, terminate orphaned sandboxes)

Phase 7 — API/SSE surface
  api-gateway, sse-gateway

Phase 8 — Supporting
  notification-service, telemetry-service
```

---

## 7. Do-Not-Break Enforcement per Service

| DNB | Enforced by service(s) |
|---|---|
| DNB1 — Run does not resume | `orchestrator-service` (RerunTask creates new Run) |
| DNB2 — Fail closed | `api-gateway`, `policy-service`, `auth-service` |
| DNB3 — Security violation does not auto-recover | `execution-service`, `orchestrator-service` |
| DNB4 — Degraded mode does not auto-escalate | `policy-service` (fail-closed), `api-gateway` |
| DNB5 — Recovery produces events + audit | All services with recovery duty |
| DNB6 — Artifact creation only through artifact-service | `artifact-service` (credential isolation), `agent-runtime-service` (no direct write) |
| DNB7 — trace_id = correlation_id | `api-gateway` (inject), all services (propagate) |
| DNB8 — Execution trace ≠ provenance trace | `telemetry-service` (separate views), `artifact-service` (provenance API) |
| DNB9 — Agent cannot self-escalate permissions | `execution-service` (policy_snapshot freeze), `policy-service` |
| DNB10 — State transition authority at Orchestrator | `orchestrator-service` + DB credential isolation |
| DNB11 — Taint write before event emit | `artifact-service` (outbox transaction order) |
| DNB12 — Model version must not be an alias | `model-gateway` (resolve), `artifact-service` (validate at registration) |

---

## 8. Intentionally Deferred Decisions

| Decision | Reason for deferral |
|---|---|
| Specific internal API schema (request/response) | Depends on doc 07 API Contracts — needs review before implementation |
| gRPC vs REST for inter-service sync | Depends on deployment mode and team preference |
| Service mesh (Istio, Envoy) vs application-level authN | Depends on infrastructure choice in doc 13 per mode |
| Multi-instance Orchestrator (leader election vs single-writer) | Depends on actual scale requirements — needs decision before cloud deployment |
| Agent Runtime worker pool sizing | Needs baseline from actual workload |
| Tool registry service (separate vs embedded in execution-service) | Needs review when Tool and Connector Context grows more complex |

---

## 9. Next Steps

The next document is **14 — Frontend Application Map**: module tree, routing, state management, SSE integration, and the constraint "frontend must not hold source of truth" adhering strictly to the service surface locked in this document.
