# 11 — Observability Model

**Status:** Draft v1.0
**Dependencies:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model, 10 Artifact Lineage Model
**Goal:** Lock down how the system is observed — who sees what, to make which decisions — including signal taxonomy, trace model, health model, alert model, and investigation surfaces.

---

## 1. Observability Goals

Observability is not "log everything." It is the ability to answer specific questions without needing to read source code or SSH into a server.

### 1.1 Three questions observability must be able to answer

| Question | Type | Audience |
|---|---|---|
| "What is the system doing right now?" | Real-time operational | Operator, user |
| "How did X happen?" | Post-hoc execution trace | Developer, operator |
| "Where did this artifact come from and is it trustworthy?" | Provenance investigation | Security, admin, auditor |

### 1.2 Distinguishing Execution Trace and Provenance Trace

These two concepts are related but must not be conflated:

| | Execution Trace | Provenance Trace |
|---|---|---|
| **Answers** | What the system did, in what order, how long it took | Where this artifact came from, through what steps |
| **Time axis** | Chronological — left to right | Causal — bottom to top (root to leaf) |
| **Unit** | Step, AgentInvocation, Sandbox session | Artifact, lineage edge, input snapshot |
| **Used for** | Debug latency, reproduce errors, understand flow | Verify trust, audit security, reproduce artifact |
| **Source** | Spans/traces, event stream | Lineage graph, provenance tuple, artifact events |

### 1.3 Who observability serves

| Actor | Needs to see | Does not need to see |
|---|---|---|
| **User (task owner)** | Task/Run timeline, artifact status, approval queue | Sandbox internals, infra metrics |
| **Developer** | Full execution trace, error detail, tool call sequence, agent reasoning steps | Infra-level hardware metrics |
| **Operator** | Service health, resource utilization, error rates, alert queue | Agent reasoning content |
| **Security/Admin** | Taint events, violation events, audit trail, lineage investigation | User task content (unless needed) |
| **Auditor** | Audit records, approval history, permission decisions | Internal implementation detail |

---

## 2. Signals

The system uses 6 signal types, each with different characteristics regarding cardinality, latency, and retention.

### 2.1 Logs

Unstructured to semi-structured text. Used for detailed debugging and error investigation.

**Mandatory rules:**
- Every log entry must include: `timestamp`, `service`, `level`, `correlation_id`, `workspace_id` (if context is available).
- Logs must not contain secret values, provider keys, or raw user message content.
- Standard log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`.
- `DEBUG` logs are disabled by default in production — only enabled per-correlation-id when debugging.

**Retention:** 7 days hot, 30 days cold.

### 2.2 Metrics

Numeric time-series. Used for monitoring, alerting, and capacity planning.

**Taxonomy:**

| Prefix | Meaning | Examples |
|---|---|---|
| `task.*` | Task-level metrics | `task.created_total`, `task.completed_duration_ms` |
| `run.*` | Run-level metrics | `run.active_count`, `run.failed_total` |
| `agent.*` | AgentInvocation-level metrics | `agent.tokens_used_total`, `agent.cost_usd_total` |
| `sandbox.*` | Sandbox-level metrics | `sandbox.provisioning_duration_ms`, `sandbox.violation_total` |
| `artifact.*` | Artifact-level metrics | `artifact.tainted_total`, `artifact.write_duration_ms` |
| `model_gateway.*` | Model Gateway metrics | `model_gateway.latency_ms`, `model_gateway.error_rate` |
| `permission.*` | Permission decision metrics | `permission.denied_total`, `permission.violation_total` |
| `service.*` | Infra-level service health | `service.up`, `service.request_rate`, `service.p99_latency` |

**Cardinality rule:** Labels must not use `artifact_id`, `run_id`, or any UUID as a label value — this will explode metrics cardinality. Use `workspace_id`, `task_type`, `sandbox_class`, `model_id` as labels.

**Retention:** 15 days hot (high-resolution), 1 year downsampled.

### 2.3 Traces (Distributed Tracing)

Structured spans following the OpenTelemetry standard. Used to trace execution flow across multiple services.

**Mandatory trace hierarchy:**

```
Trace (correlation_id = trace_id)
  └── Span: Task execution
        └── Span: Run (run_id)
              └── Span: Step (step_id)
                    └── Span: AgentInvocation (agent_invocation_id)
                          ├── Span: Model call
                          ├── Span: Tool call
                          └── Span: Sandbox session (sandbox_id)
                                └── Span: Command execution
```

**Required on every span:**
- `workspace_id`, `task_id`, `run_id` (propagated from parent)
- `span.kind`: `SERVER`, `CLIENT`, `INTERNAL`
- Spans must not contain secrets or raw user content in attributes.

**Sampling strategy:**
- 100% sampling for spans with `error = true` or `duration > SLO_threshold`.
- 10% sampling for normal spans in production.
- 100% sampling in staging and debug mode.

**Retention:** 3 days hot (queryable), 14 days cold (aggregated).

### 2.4 Events (from Event Store — doc 06)

The event store is the historical source of truth. The observability layer consumes the event stream to build materialized views, alerts, and investigation surfaces.

**Observability consumes events to:**
- Build the task/run timeline view.
- Trigger alerts when certain event patterns occur.
- Feed the artifact lineage investigation view.
- Power the approval audit view.

Events are not logs — they must not be treated as logs, and log content must not be duplicated into the event store.

**Retention:** Per doc 06 — 30 days hot, 1 year cold.

### 2.5 Lineage Context

A special signal unique to this system. When an artifact `failed`, is `tainted`, or has its download blocked, the observability layer must pull and surface **lineage context** consisting of:

- Artifact root type and provenance tuple.
- The full parent chain up to root.
- The Run/Step/AgentInvocation/Tool/Model that produced the artifact.
- Taint propagation path (if tainted).
- Reproducibility tuple completeness check.

Lineage context must be retrievable within **< 2 seconds** from an artifact_id. This is the SLO for the investigation surface.

### 2.6 Audit Records

From doc 09 — every permission decision (allow/deny/violation) has an audit record. The observability layer aggregates audit records to:
- Power the taint investigation view.
- Feed the security dashboard.
- Support compliance audit export.

---

## 3. Trace Model

### 3.1 Trace ID = Correlation ID

`correlation_id` from the event envelope (doc 06) = `trace_id` in OpenTelemetry. Do not create two separate IDs. All spans within a Run carry the same `trace_id`.

### 3.2 Propagation path

```
User request
  → API Gateway (inject trace_id = correlation_id)
    → Orchestrator (propagate)
      → Agent Engine (propagate)
        → Model Gateway (propagate — write to provider request header if provider supports it)
        → Tool Execution (propagate)
          → Sandbox Sidecar (propagate)
      → Artifact Service (propagate)
      → Event Store (write correlation_id into event)
```

### 3.3 Cross-service context propagation

Uses the W3C `traceparent` header. All HTTP/gRPC calls between services must propagate this header.

For async/event-driven paths: `correlation_id` and `causation_id` in the event envelope serve as the propagation mechanism — headers are not used.

### 3.4 Required span attributes by span type

**Span: AgentInvocation**

| Attribute | Notes |
|---|---|
| `agent.id` | Agent definition ID |
| `agent.model_id` | Model used |
| `agent.prompt_tokens` | After invocation completes |
| `agent.completion_tokens` | After invocation completes |
| `agent.cost_usd` | After invocation completes |
| `agent.tool_call_count` | Number of tool calls |
| `agent.status` | Final result |

**Span: Sandbox session**

| Attribute | Notes |
|---|---|
| `sandbox.id` | |
| `sandbox.class` | |
| `sandbox.termination_reason` | After terminated |
| `sandbox.policy_violation` | `true` if any violation occurred |

**Span: Artifact write**

| Attribute | Notes |
|---|---|
| `artifact.id` | |
| `artifact.type` | |
| `artifact.provenance_complete` | `true/false` |
| `artifact.tainted` | `true/false` |

---

## 4. Health Model

### 4.1 Service health tiers

| Tier | Services | SLO uptime | Health check interval |
|---|---|---|---|
| **Critical** | Orchestrator, Auth, Event Store, Model Gateway | 99.9% | 10 seconds |
| **Important** | Agent Engine, Artifact Service, Sandbox Manager | 99.5% | 15 seconds |
| **Supporting** | Observability stack, Audit Log, Notification | 99.0% | 30 seconds |

### 4.2 Health check dimensions

Each service must report 4 dimensions:

| Dimension | Meaning | Endpoint |
|---|---|---|
| `liveness` | Is the service alive | `GET /healthz/live` |
| `readiness` | Is the service ready to receive traffic | `GET /healthz/ready` |
| `dependency` | Are the service's dependencies OK | `GET /healthz/deps` |
| `saturation` | Queue depth, connection pool, memory pressure | Metrics |

### 4.3 SSE stream health

SSE streams (real-time push to UI) have their own health checks because they are long-lived connections:

- `sse.active_connections`: number of currently active connections.
- `sse.reconnect_rate`: client reconnect frequency (indicator of instability).
- `sse.message_lag_ms`: latency from event emission to client receipt.

SLO: `sse.message_lag_ms` < 500ms at the 95th percentile.

### 4.4 Model Gateway health

The Model Gateway must not only perform internal health checks but also monitor external providers:

- `model_gateway.provider_latency_ms` per provider.
- `model_gateway.provider_error_rate` per provider.
- `model_gateway.provider_rate_limit_remaining` per provider.
- `model_gateway.fallback_activated_total`: number of failovers to backup provider.

---

## 5. Alert Model

### 5.1 Alert severity levels

| Severity | Meaning | Response SLA | Notification |
|---|---|---|---|
| `P0 — Critical` | System is down, data is at risk of loss | 5 minutes | PagerDuty + Slack |
| `P1 — High` | Critical functionality affected, degraded | 30 minutes | Slack + Email |
| `P2 — Medium` | Issue affecting some users, workaround exists | 4 hours | Slack |
| `P3 — Low` | Anomaly, warning, needs monitoring | 24 hours | Dashboard only |

### 5.2 Alert groups

**Group 1: Operational alerts (for Operators)**

| Alert | Severity | Trigger condition |
|---|---|---|
| `orchestrator_down` | P0 | Orchestrator fails readiness check for > 30 seconds |
| `event_store_write_failure` | P0 | Event store write error rate > 1% within 1 minute |
| `model_gateway_all_providers_down` | P0 | All providers have error rate > 50% |
| `sandbox_manager_capacity_exhausted` | P1 | Sandbox queue depth > threshold |
| `artifact_service_write_lag` | P1 | Artifact write duration p99 > 30 seconds |
| `sse_message_lag_high` | P1 | `sse.message_lag_ms` p95 > 500ms |
| `audit_write_failure` | P1 | Audit log write failure (per doc 09 — fail-safe alert) |
| `model_gateway_provider_degraded` | P2 | One provider has error rate > 10% |
| `run_queue_depth_growing` | P2 | Run queue depth growing continuously for > 5 minutes |

**Group 2: Security & lineage alerts (for Security/Admin)**

| Alert | Severity | Trigger condition |
|---|---|---|
| `sandbox_policy_violation` | P1 | Any `security.violation` event |
| `taint_propagation_cascade` | P1 | Artifact taint propagation affects > 5 artifacts within 1 minute |
| `download_blocked_tainted_artifact` | P2 | `artifact:download` denied due to taint — monitor pattern |
| `incomplete_provenance_artifact` | P2 | Artifact transitions to `failed` with `failure_reason: incomplete_provenance` |
| `lineage_cycle_rejected` | P2 | Artifact service rejects lineage edge due to cycle |
| `agent_escalation_attempt` | P1 | Agent attempts privilege escalation via prompt/tool call |
| `permission_violation_burst` | P1 | > 10 `permission.violation` events within 5 minutes from the same `workspace_id` |
| `artifact_ready_without_events` | P2 | Artifact reaches `ready` without a preceding `artifact.writing` event |

**Group 3: Artifact lineage alerts (from doc 10) — separate group**

| Alert | Severity | Trigger |
|---|---|---|
| `artifact_tainted_propagation` | P1 | Taint propagates to artifact in lineage chain |
| `artifact_incomplete_provenance` | P2 | Provenance tuple is missing required fields |
| `artifact_lineage_cycle` | P2 | Cycle detected when writing edge |
| `artifact_download_blocked_taint` | P2 | Download attempt blocked due to taint |
| `artifact_ready_without_expected_events` | P2 | Artifact reaches `ready` without the expected event chain |

### 5.3 Silence policy

- Silenced alerts must have: an owner, a reason, and an expiry time.
- P0 alerts must not be silenced for more than 1 hour without an incident record.
- Silence must not auto-renew — each extension requires manual confirmation.

### 5.4 Alerts must not fire during dry-run / replay mode

When `is_replay: true` (from doc 06), the alert engine must suppress all alerts generated from that event — except security alerts.

---

## 6. Investigation Surfaces

### 6.1 Task Timeline

**Answers:** "How did this task unfold?"

**Must display:**
- A chronological timeline from `task.submitted` to terminal state.
- All Runs within the Task with status and duration.
- All approval gates: who requested, who decided, how long.
- All errors and cancellations with reasons.
- Direct link to the Run timeline.

**Audience:** User (task owner), Developer, Operator.

### 6.2 Run Timeline

**Answers:** "How did this Run execute, step by step?"

**Must display:**
- Waterfall view of Steps (may be parallel).
- For each Step: status, duration, input/output snapshot hash.
- AgentInvocation detail: model, tokens, cost, tool call sequence.
- Sandbox session: class, duration, violations (if any).
- Artifacts produced during this Run with status and taint status.
- Error detail if Step/AgentInvocation failed.
- Distributed trace span (link to tracing backend).

**Audience:** Developer, Operator.

### 6.3 Sandbox Session View

**Answers:** "What did the Sandbox do during this session?"

**Must display:**
- Sandbox lifetime.
- Sequence of commands/tool calls executed.
- Policy violations (if any): violation type, timestamp, blocked action.
- Network egress attempts: domain, allow/deny, timestamp.
- `termination_reason`.
- Link to the corresponding AgentInvocation.

**Audience:** Developer, Security/Admin.

**Note:** This view does not display raw reasoning or message content — only metadata and actions.

### 6.4 Artifact Lineage View

**Answers:** "Where did this artifact come from and is it trustworthy?"

**Must display:**
- DAG visualization of lineage from root to the current artifact.
- For each artifact in the DAG: state, taint status, root type, created_at.
- Provenance tuple completeness check (are all 5 components present).
- Taint propagation path if the artifact is currently tainted: which parent artifact caused it.
- Run/Step/AgentInvocation/Tool/Model associated with each node in the DAG.
- Download history (who downloaded, when).

**SLO:** The full lineage view must load within < 2 seconds from an `artifact_id`.

**Audience:** Security/Admin, Developer, Auditor.

### 6.5 Taint Investigation View

**Answers:** "Why was this artifact tainted, and what other artifacts are affected?"

**Must display:**
- Taint origin: source of the taint (security violation / manual / propagation / model anomaly).
- Propagation path: which artifacts received taint from this artifact.
- Downstream impact: all child/descendant artifacts affected.
- Blocked actions: download attempts blocked due to this taint.
- Untaint history if the artifact was previously untainted and re-tainted.
- Link to the security violation event (if source is a violation).

**Audience:** Security/Admin.

### 6.6 Approval Audit View

**Answers:** "Who approved/rejected what, when, and in what context?"

**Must display:**
- All approval requests in the workspace with filters by Task/Run/Step/approver.
- For each approval: target, requester, required approver role, prompt shown to the approver.
- Decision: who decided, decision time, reason (if rejected).
- Timeout events.
- Link to Task/Run/Step context.
- Export to CSV/JSON for compliance audit.

**Audience:** Admin, Auditor.

---

## 7. Observability Invariants

The following principles must not be violated by any implementation or optimization:

**O1 — Observability must not expose secrets or raw user content.**
Spans, logs, metrics, and investigation surfaces must not contain secret values, provider keys, or raw message content from users/agents.

**O2 — Artifact lineage must be queryable from artifact_id within < 2 seconds.**
This is a hard SLO. If the lineage graph is too large, the Artifact service must maintain materialized ancestors/descendants.

**O3 — Audit records must not be omitted even when the observability stack is degraded.**
Audit write failure → fail-safe behavior per doc 09 (section 9.3). A degraded observability stack must not disable the audit trail.

**O4 — Alerts must not fire during replay mode.**
`is_replay: true` events must be filtered before entering the alert engine. The only exception: security alerts still fire if the replay detects a new violation.

**O5 — Trace ID = Correlation ID — two separate IDs must not be created.**
If two IDs are created, traces will not correlate with event history.

**O6 — Execution trace and provenance trace must not be conflated.**
These two views serve different purposes and must have separate UI surfaces.

---

## 8. Intentionally Deferred Decisions

| Item | Reason not yet locked |
|---|---|
| Specific technology (Prometheus, Grafana, Jaeger, Loki, etc.) | Depends on deployment mode — local vs cloud vs hybrid |
| Specific sampling rates and adaptive sampling logic | Requires real-world tuning based on workload |
| PII/content redaction pipeline in logs | Complex depending on jurisdiction and deployment; needs its own design |
| Multi-tenant metrics isolation (workspace A cannot see workspace B metrics) | Depends on deployment topology and tenant model |
| SLO error budget and burn rate alerting | Requires baseline data from actual operations |
| Specific dashboard layouts | Not part of the architecture layer — belongs to the UX layer |

---

## 9. Next Steps

The next document is **12 — Failure & Recovery Model**: locking down how the system handles failure at each layer — sandbox failure, model timeout, event duplication, partial artifact write, subtask failure cascade, and retry semantics that prevent repeated side effects. The Observability model (doc 11) serves as the foundation for failure recovery to be observable and verifiable from the outside.
