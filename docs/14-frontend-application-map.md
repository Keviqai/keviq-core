# 14 — Frontend Application Map

**Status:** Draft v1.0
**Dependencies:** 03 Bounded Contexts, 05 State Machines, 06 Event Contracts, 11 Observability Model, 13 Deployment Topology, 15 Backend Service Map
**Objective:** Lock the module tree, routing, state model, SSE integration, permission-aware rendering, investigation surfaces, and forbidden patterns — adhering strictly to the service surface from doc 15 without pulling architecture backward.

---

## 1. Frontend Invariants

The following principles must not be violated by any component, hook, store, or routing decision:

**F1 — The frontend is a shell, control surface, and investigation surface — nothing more.**
All domain truth resides in the backend. The frontend is where rendering, controlling, and observing happen — not where decisions are made or data is stored.

**F2 — The frontend does not hold source of truth for any domain entity.**
`Task`, `Run`, `Step`, `Artifact`, `AgentInvocation`, `Sandbox`, `Approval` — all are server state. The frontend only caches for rendering. A page reload must correctly rebuild from query APIs without losing anything important.

**F3 — The frontend must not have its own state machine for domain lifecycle.**
No Redux reducer or Zustand store may independently track `taskStatus`, `runStatus`, `stepStatus` with its own transition logic. The state machine belongs to `orchestrator-service`. The frontend only renders status received from API/SSE.

**F4 — The frontend must not infer permissions on the client.**
Permission checks must not be performed by reading the user role on the client and showing/hiding buttons. The backend returns capability flags per resource — the frontend renders based on those flags. No hard-coding `if (role === 'admin')` in components.

**F5 — The frontend must not self-merge or compute lineage.**
The lineage graph comes only from the `artifact-service` API. The frontend renders the DAG from returned data — no self-joining, no self-inferring.

**F6 — The Terminal UI must not be a backdoor that bypasses policy.**
The terminal component only relays input/output with the execution surface via API. No direct WebSocket to the sandbox. No "raw mode" bypassing policy.

**F7 — SSE events are not source of truth — only a real-time update layer.**
SSE is used for fast updates and query cache invalidation. If SSE events are missed, reloading or refetching from the API must yield correct results. The UI must not depend on SSE to have valid state.

**F8 — Optimistic updates are allowed only very sparingly and must have rollback.**
Only applicable to lightweight actions with no security implications (e.g., renaming a task). Never apply optimistic updates to Run status, approval decisions, or artifact status.

---

## 2. Application Module Tree

Modules are organized by service surface and investigation purpose — not by "convenient screens."

```
agent-os-web/
  apps/
    shell/                    ← Shell app: layout, navigation, window management
    workspace/                ← Workspace context: overview, members, settings
    task-monitor/             ← Task + Run lifecycle: create, view, control
    artifact-explorer/        ← Artifact list, search, download
    lineage-viewer/           ← Artifact DAG, provenance view
    approval-center/          ← Approval queue, decision UI
    terminal-app/             ← Terminal relay UI
    audit-viewer/             ← Audit records, compliance surfaces
    investigation/            ← Investigation surfaces from doc 11
    settings/                 ← Workspace policy, secrets, integrations
    notification-center/      ← Approval notifications, human-in-the-loop prompts

  packages/
    ui-core/                  ← Design system, base components
    server-state/             ← Query hooks (TanStack Query wrappers)
    live-state/               ← SSE subscription, reconnect, event buffer
    ui-state/                 ← Panel/window/filter/layout state (Zustand)
    routing/                  ← Route definitions, guards, breadcrumbs
    permissions/              ← Capability flag types, rendering utilities
    domain-types/             ← TypeScript types mirrored from API schema
    charts/                   ← Timeline charts, DAG renderer, waterfall
```

### 2.1 Rationale for separating `server-state`, `live-state`, `ui-state` into 3 packages

| Package | Contains | Does not contain |
|---|---|---|
| `server-state` | TanStack Query queries/mutations, API client | Domain lifecycle logic |
| `live-state` | SSE connection, event buffer, `Last-Event-ID` cursor, reconnect | Business state |
| `ui-state` | Panel open/close, filter values, layout preferences, local form state | Domain entity state |

If these three layers are mixed, the frontend will inevitably build its own state machine.

---

## 3. Routing Tree

Routes adhere strictly to the object model from doc 04. No routing by component convenience.

```
/
├── /workspaces
│     ├── /workspaces/:workspaceId                          (workspace overview)
│     ├── /workspaces/:workspaceId/tasks                    (task list)
│     │     └── /workspaces/:workspaceId/tasks/:taskId      (task detail + timeline)
│     │           └── /runs/:runId                          (run detail + step waterfall)
│     ├── /workspaces/:workspaceId/artifacts                (artifact list)
│     │     └── /artifacts/:artifactId                      (artifact detail)
│     │           └── /artifacts/:artifactId/lineage        (lineage DAG view)
│     │           └── /artifacts/:artifactId/taint          (taint investigation)
│     ├── /workspaces/:workspaceId/approvals                (approval queue)
│     │     └── /approvals/:approvalId                      (approval detail + decision)
│     ├── /workspaces/:workspaceId/terminal                 (terminal sessions)
│     ├── /workspaces/:workspaceId/audit                    (audit log viewer)
│     ├── /workspaces/:workspaceId/settings
│     │     ├── /settings/members
│     │     ├── /settings/policies
│     │     ├── /settings/secrets
│     │     └── /settings/integrations
│     └── /workspaces/:workspaceId/investigate              (investigation hub)

/notifications                                              (cross-workspace notification center)
/account                                                    (user profile, auth settings)
```

### 3.1 Route naming rules

- Use entity names from the domain model (`tasks`, `runs`, `artifacts`, `approvals`) — do not use component names (`agent-panel`, `debug-view`, `ai-chat`).
- `runId` is a child of `taskId` in terms of context but may be a standalone route because Runs need their own deep links.
- Investigation surfaces have their own routes — they are not embedded inside modals.

---

## 4. State Management Model

### 4.1 Three state layers — must not be mixed

```
┌─────────────────────────────────────────────────────┐
│                   SERVER STATE                       │
│  TanStack Query — Task, Run, Step, Artifact,         │
│  Approval, Workspace, Member, Policy, Audit          │
│  Source: REST/GraphQL API from api-gateway           │
│  Invalidation: triggered by SSE events              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  LIVE EVENT STATE                    │
│  SSE stream buffer, Last-Event-ID cursor,            │
│  subscription scope (workspace/task/run)             │
│  Role: fast UI update + query invalidation trigger   │
│  NOT source of truth — supplement only               │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    UI STATE                          │
│  Panel open/close, active tab, filter values,        │
│  form draft, layout preferences, notification read   │
│  Stored: Zustand + localStorage (non-critical only) │
│  Never: domain entity status, permission state       │
└─────────────────────────────────────────────────────┘
```

### 4.2 Query invalidation strategy

SSE event → decide whether to invalidate query cache:

| SSE Event received | Query to invalidate |
|---|---|
| `task.started`, `task.completed`, `task.failed`, `task.cancelled` | `tasks/:taskId` |
| `run.started`, `run.completed`, `run.failed` | `tasks/:taskId/runs`, `runs/:runId` |
| `step.completed`, `step.failed` | `runs/:runId/steps` |
| `agent_invocation.waiting_human` | `runs/:runId` + trigger approval notification |
| `artifact.ready`, `artifact.tainted` | `artifacts/:artifactId`, `tasks/:taskId/artifacts` |
| `approval.requested` | `approvals` list |
| `sandbox.failed`, `sandbox.terminated` | `runs/:runId` (to display sandbox status) |

**Rule:** SSE events must not be used to **set** values directly into the query cache. SSE may only be used to **invalidate** — refetching from the API is the source of truth.

The only exception: append-only timeline events (`step.started`, `step.completed`, etc.) may be optimistically appended to the timeline list to reduce latency — with an `is_optimistic: true` flag that will be reconciled upon query refetch.

### 4.3 Forbidden state patterns

- `const [taskStatus, setTaskStatus] = useState(...)` for domain entities.
- Reducer with self-transition: `case 'TASK_STARTED': return { ...state, status: 'running' }`.
- Derived permission: `const canCancel = user.role === 'admin'`.
- Local lineage computation: `const ancestors = computeAncestors(artifacts)`.

---

## 5. SSE / Realtime Model

### 5.1 Subscription lifecycle

```
Component mount / route enter workspace
  → Subscribe SSE: scope = workspace_id
  → Optionally narrow scope: task_id, run_id when user is viewing

User navigates away
  → Unsubscribe or downscope (keep workspace-level, drop task-level)

Connection drop
  → Auto-reconnect with Last-Event-ID header
  → Reconnect with jitter backoff (doc 12 L8)
  → Missed events are replayed by sse-gateway from event store
```

### 5.2 SSE event consumption flow

```
SSE event received
  → Parse envelope (event_id, event_type, correlation_id, payload)
  → Update Last-Event-ID cursor (persist in session storage — not redux)
  → Route to handler by event_type:
      task.* → invalidate task queries
      run.* → invalidate run queries + append timeline
      artifact.ready / tainted → invalidate artifact queries
      agent_invocation.waiting_human → trigger approval/input prompt
      approval.requested → refresh approval queue
      sandbox.failed → surface warning on run view
  → handler: invalidateQueries() or appendToTimeline()
```

### 5.3 Subscription scope rules

- Do not subscribe to the entire event stream — must scope by `workspace_id` at minimum.
- When user views Task detail: additionally narrow by `task_id`.
- When user views Run detail: additionally narrow by `run_id`.
- Cross-workspace events must never be mixed.

### 5.4 SSE degradation behavior

If SSE is down: the UI still functions via polling fallback (if available) or clearly displays "Real-time updates paused — data may be stale." A manual refresh button is exposed. The user must not be led to believe the system is real-time when it is not (doc 12 section 7.3).

---

## 6. Permission-aware Rendering Model

### 6.1 Principle: Backend returns capability flags

The backend API response for each resource must include a `_capabilities` object:

```json
{
  "id": "task_abc",
  "title": "Audit repo",
  "task_status": "running",
  "_capabilities": {
    "can_cancel": true,
    "can_approve": false,
    "can_view_run": true,
    "can_download_artifact": true,
    "can_rerun": false
  }
}
```

The frontend renders based on `_capabilities` — it does not infer permissions from user roles.

### 6.2 Why permissions must not be inferred on the client

- Permission resolution is 7 layers deep (doc 09 section 5) — the client lacks sufficient context.
- Roles can be `(own)` — the client does not know full resource ownership.
- Policy-gated capabilities depend on workspace policy — the client has no policy store.
- Frontend-inferred permissions can be bypassed via DevTools.

### 6.3 Capability flag rendering pattern

```tsx
// CORRECT — render based on capability from server
function TaskActions({ task }) {
  return (
    <>
      {task._capabilities.can_cancel && (
        <Button onClick={() => cancelTask(task.id)}>Cancel</Button>
      )}
      {task._capabilities.can_rerun && (
        <Button onClick={() => rerunTask(task.id)}>Rerun</Button>
      )}
    </>
  )
}

// FORBIDDEN — infer permission on client
function TaskActions({ task, user }) {
  const canCancel = user.role === 'admin' || task.createdBy === user.id  // ❌
  ...
}
```

### 6.4 Artifact access rendering

The artifact view must check `state × taint` before rendering the download button — per the access matrix from doc 10 section 6.1. The backend returns `_capabilities.can_download` with taint already factored in. The frontend does not perform its own check.

Tainted artifact: display a clear taint badge. The download button is hidden unless `_capabilities.can_download = true` (which is true only if the user has `artifact:untaint` and the artifact has been untainted).

---

## 7. Investigation Surfaces

These are the 6 surfaces that differentiate Agent OS from a typical AI dashboard. Each surface has its own route, data source, and audience (from doc 11 section 6).

### 7.1 Task Timeline

**Route:** `/workspaces/:workspaceId/tasks/:taskId`
**Data:** `GET /tasks/:taskId/timeline`
**Audience:** User, Developer, Operator

**Must display:**
- Chronological timeline from `task.submitted` to terminal state.
- All Runs within the task with status badge, duration bar.
- Approval gates: who requested, who decided, waiting time.
- Error summary if failed.
- Link to Run timeline for each Run.

**Component requirements:**
- The timeline must not self-compute from Step data — it must use the timeline API.
- Approval history must be fetched from the `approval-center` API, not self-joined.

### 7.2 Run Timeline (Step Waterfall)

**Route:** `/runs/:runId`
**Data:** `GET /runs/:runId/steps` + `GET /runs/:runId/agent-invocations`
**Audience:** Developer, Operator

**Must display:**
- Waterfall view of Steps (sequential and parallel).
- For each Step: status, duration, input/output snapshot hash (not raw content).
- AgentInvocation details: model, tokens, cost, tool call count.
- Sandbox: class, duration, violation flag.
- Artifacts produced in the Run with taint badge.
- Error detail for failed Steps.
- Link to distributed trace (external tracing backend).

### 7.3 Sandbox Session View

**Route:** `/runs/:runId/sandbox/:sandboxId`
**Data:** `GET /sandboxes/:sandboxId/session`
**Audience:** Developer, Security/Admin

**Must display:**
- Sandbox lifetime.
- Sequence of tool calls/commands.
- Policy violations if any.
- Network egress attempts with allow/deny status.
- Termination reason.

**Constraint:** Do not display raw agent reasoning or raw message content — only metadata and actions.

### 7.4 Artifact Lineage View

**Route:** `/artifacts/:artifactId/lineage`
**Data:** `GET /artifacts/:artifactId/lineage/graph` + `GET /artifacts/:artifactId/provenance`
**Audience:** Security/Admin, Developer, Auditor
**SLO:** Load within < 2 seconds (from doc 11 O2)

**Must display:**
- DAG visualization: nodes are artifacts, edges are lineage edge types.
- Node color by `state × taint`: ready/clean, ready/tainted, failed, archived.
- Hover node: artifact type, created_at, run/step/model context.
- Provenance completeness indicator: 5/5 or which fields are missing.
- Taint propagation path if tainted.

**Component requirements:**
- The DAG renderer must handle cycle detection (the backend already rejects cycles but the frontend must gracefully degrade if receiving malformed data).
- Do not self-compute ancestor/descendant — only render from API response.

### 7.5 Taint Investigation View

**Route:** `/artifacts/:artifactId/taint`
**Data:** `GET /artifacts/:artifactId/taint-status` + downstream artifacts
**Audience:** Security/Admin

**Must display:**
- Taint origin: violation / manual / propagation / model anomaly.
- Propagation path: which artifact received taint from this one.
- Downstream impact count.
- Blocked download attempts (from audit log).
- Untaint history.
- Link to security violation event.

### 7.6 Approval Audit View

**Route:** `/workspaces/:workspaceId/audit`
**Data:** `GET /audit?type=approval&...`
**Audience:** Admin, Auditor

**Must display:**
- Approval request list with filters: Task/Run/Step/approver/date range.
- For each approval: target, required role, prompt text, decision, decided_by, decision time.
- Timeout events.
- Export to CSV/JSON for compliance.

---

## 8. Module → Backend Service Mapping

Each frontend module knows exactly which backend service(s) it calls. Calling "whichever endpoint seems convenient" is not allowed:

| Frontend Module | Primary Backend Service(s) | Event subscriptions |
|---|---|---|
| `shell/` | `api-gateway` (authn), `workspace-service` | workspace-level SSE |
| `workspace/` | `workspace-service`, `policy-service` (read) | workspace.* |
| `task-monitor/` | `orchestrator-service` (via api-gateway) | task.*, run.*, step.*, approval.* |
| `artifact-explorer/` | `artifact-service` | artifact.* |
| `lineage-viewer/` | `artifact-service` (lineage API) | artifact.tainted, artifact.untainted |
| `approval-center/` | `orchestrator-service` (via api-gateway) | approval.* |
| `terminal-app/` | `execution-service` (via api-gateway, terminal relay) | sandbox.* |
| `audit-viewer/` | `audit-service` | None (pull-based) |
| `investigation/` | `artifact-service`, `audit-service`, `orchestrator-service` | Scope-narrow per investigation |
| `settings/` | `workspace-service`, `policy-service`, `secret-broker` (metadata only) | None |
| `notification-center/` | `notification-service` | approval.requested, agent_invocation.waiting_human |

---

## 9. Forbidden Frontend Patterns

The following patterns are absolutely prohibited. If discovered during code review, they must be reverted:

| # | Forbidden Pattern | Reason | Alternative |
|---|---|---|---|
| FP1 | Own state machine for Task/Run/Step in reducer/store | F3 invariant — the state machine belongs to Orchestrator | Render status from server state |
| FP2 | `if (user.role === 'admin')` to show/hide controls | F4 invariant — permission inferred on client | Use `_capabilities` flags from API |
| FP3 | Self-compute lineage ancestors/descendants on client | F5 invariant | Call `artifact-service` lineage API |
| FP4 | Terminal component opens WebSocket directly to sandbox | F6 invariant — bypasses policy | Terminal relay via `api-gateway` → `execution-service` |
| FP5 | SSE event handler `set`s values directly into query cache | F7 invariant | Use `invalidateQueries()` then refetch |
| FP6 | Optimistic update for approval decision, Run status, artifact taint | F8 invariant | Server-confirmed update only |
| FP7 | LocalStorage for domain entities (task, run, artifact) | F2 invariant | Server state only |
| FP8 | Hard-code model list, provider list, capability list on client | These lists change per policy/config | Fetch from model-gateway / policy API |
| FP9 | URL pattern `/agent-panel`, `/debug-view` not following object model | Routes must follow domain language | Use `/tasks/:id`, `/runs/:id` |
| FP10 | Render artifact download button without checking `_capabilities.can_download` | State × taint check must be on backend | Render based on capability flag |

---

## 10. Non-functional Frontend Requirements

### 10.1 Performance

- Task timeline: render within < 1 second with 100 events.
- Artifact lineage DAG: render within < 2 seconds with 50 nodes (SLO from doc 11).
- SSE reconnect: no UI flicker — skeleton loading during reconnect.

### 10.2 Accessibility

- All actions have a keyboard shortcut alternative.
- Investigation surfaces have a table alternative for DAG visualization (screen reader support).

### 10.3 Error states

- Network error: retry indicator, no silent failure.
- Permission denied: clearly display "you do not have permission to perform this action" — do not hide elements without explanation.
- SSE down: banner "Real-time updates paused" with manual refresh button.
- Artifact tainted: clear badge, download disabled, link to taint investigation.

### 10.4 Progressive loading

- Server state uses loading/error/success states — no blank screens.
- Lineage DAG: render root nodes first, expand by depth.
- Timeline: paginate by event window — do not load all 10,000 events into memory.

---

## 11. Intentionally Deferred Decisions

| Decision | Reason for deferral |
|---|---|
| Specific framework (Next.js vs Vite + React Router) | Depends on deployment mode — Next.js for cloud, Vite for electron/local |
| DAG renderer library | Needs evaluation with real lineage data |
| Official `_capabilities` field format | Depends on API Contracts (doc 07) |
| Polling fallback interval when SSE is down | Requires tuning per UX requirements |
| Micro-frontend vs monorepo bundling strategy | Depends on team size and deployment cadence |
| Offline mode / local-first cache | Depends on local-first topology requirements |

---

## 12. Next Steps

The next document is **16 — Repo Structure Conventions**: locking the monorepo layout, module naming, boundary enforcement, and mapping pressure points PP1–PP10 to linting/architecture test rules — so that the codebase from day one cannot accidentally violate the architecture.
