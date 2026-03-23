# 14 — Frontend Application Map

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 03 Bounded Contexts, 05 State Machines, 06 Event Contracts, 11 Observability Model, 13 Deployment Topology, 15 Backend Service Map  
**Mục tiêu:** Khóa module tree, routing, state model, SSE integration, permission-aware rendering, investigation surfaces, và forbidden patterns — bám đúng service surface của doc 15 mà không kéo ngược kiến trúc.

---

## 1. Frontend Invariants

Những nguyên tắc sau không được vi phạm bởi bất kỳ component, hook, store, hay routing decision nào:

**F1 — Frontend là shell, control surface, và investigation surface — không hơn.**  
Mọi domain truth nằm ở backend. Frontend là nơi render, điều khiển, và quan sát — không phải nơi quyết định hay lưu trữ.

**F2 — Frontend không giữ source of truth cho bất kỳ domain entity nào.**  
`Task`, `Run`, `Step`, `Artifact`, `AgentInvocation`, `Sandbox`, `Approval` — tất cả đều là server state. Frontend chỉ cache để render. Reload trang phải rebuild đúng từ query APIs mà không mất gì quan trọng.

**F3 — Frontend không được có state machine riêng cho domain lifecycle.**  
Không có Redux reducer hay Zustand store tự tracking `taskStatus`, `runStatus`, `stepStatus` với transition logic riêng. State machine là của `orchestrator-service`. Frontend chỉ render status nhận từ API/SSE.

**F4 — Frontend không suy ra permission ở client.**  
Permission check không được thực hiện bằng cách đọc user role ở client rồi ẩn/hiện button. Backend trả về capability flags cho từng resource — frontend render theo flags đó. Không hard-code `if (role === 'admin')` trong component.

**F5 — Frontend không tự merge hay compute lineage.**  
Lineage graph chỉ đến từ `artifact-service` API. Frontend render DAG từ dữ liệu được trả về — không tự join, không tự infer.

**F6 — Terminal UI không được là cửa hậu bypass policy.**  
Terminal component chỉ relay input/output với execution surface qua API. Không có direct WebSocket tới sandbox. Không có "raw mode" bypass policy.

**F7 — SSE event không là source of truth — chỉ là real-time update layer.**  
SSE dùng để cập nhật nhanh và invalidate query cache. Nếu SSE bị miss, reload hoặc refetch từ API phải cho kết quả đúng. UI không được phụ thuộc vào SSE để có state hợp lệ.

**F8 — Optimistic update chỉ được dùng rất hạn chế và phải có rollback.**  
Chỉ áp dụng cho action nhẹ không có security implication (VD: đổi tên task). Không bao giờ optimistic update trạng thái Run, approval decision, hay artifact status.

---

## 2. Application Module Tree

Module được tổ chức theo service surface và investigation purpose — không theo "màn hình tiện".

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
    investigation/            ← Investigation surfaces từ doc 11
    settings/                 ← Workspace policy, secrets, integrations
    notification-center/      ← Approval notifications, human-in-the-loop prompts

  packages/
    ui-core/                  ← Design system, base components
    server-state/             ← Query hooks (TanStack Query wrappers)
    live-state/               ← SSE subscription, reconnect, event buffer
    ui-state/                 ← Panel/window/filter/layout state (Zustand)
    routing/                  ← Route definitions, guards, breadcrumbs
    permissions/              ← Capability flag types, rendering utilities
    domain-types/             ← TypeScript types mirror từ API schema
    charts/                   ← Timeline charts, DAG renderer, waterfall
```

### 2.1 Lý do tách `server-state`, `live-state`, `ui-state` thành 3 package riêng

| Package | Chứa gì | Không chứa gì |
|---|---|---|
| `server-state` | TanStack Query queries/mutations, API client | Domain lifecycle logic |
| `live-state` | SSE connection, event buffer, `Last-Event-ID` cursor, reconnect | Business state |
| `ui-state` | Panel open/close, filter values, layout preferences, local form state | Domain entity state |

Nếu trộn ba layer này, sẽ không tránh được việc frontend tự dựng state machine riêng.

---

## 3. Routing Tree

Route bám đúng object model từ doc 04. Không dùng route theo component convenience.

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

- Dùng tên entity từ domain model (`tasks`, `runs`, `artifacts`, `approvals`) — không dùng tên component (`agent-panel`, `debug-view`, `ai-chat`).
- `runId` là child của `taskId` về mặt context nhưng có thể là standalone route vì Run cần deep-link riêng.
- Investigation surfaces có route riêng — không embed chìm trong modal.

---

## 4. State Management Model

### 4.1 Ba layer state — không được trộn

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
| `sandbox.failed`, `sandbox.terminated` | `runs/:runId` (để hiện sandbox status) |

**Quy tắc:** SSE event không được dùng để **set** giá trị trực tiếp vào query cache. SSE chỉ được dùng để **invalidate** — refetch từ API mới là source of truth.

Ngoại lệ duy nhất: append-only timeline events (`step.started`, `step.completed`, v.v.) có thể được optimistically appended vào timeline list để giảm latency — với flag `is_optimistic: true` và sẽ bị reconcile khi query refetch.

### 4.3 Forbidden state patterns

- `const [taskStatus, setTaskStatus] = useState(...)` cho domain entity.
- Reducer tự transition: `case 'TASK_STARTED': return { ...state, status: 'running' }`.
- Derived permission: `const canCancel = user.role === 'admin'`.
- Local lineage computation: `const ancestors = computeAncestors(artifacts)`.

---

## 5. SSE / Realtime Model

### 5.1 Subscription lifecycle

```
Component mount / route enter workspace
  → Subscribe SSE: scope = workspace_id
  → Optionally narrow scope: task_id, run_id khi user đang xem

User navigates away
  → Unsubscribe hoặc downscope (giữ workspace-level, drop task-level)

Connection drop
  → Auto-reconnect với Last-Event-ID header
  → Reconnect với jitter backoff (doc 12 L8)
  → Missed events được replay bởi sse-gateway từ event store
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
  → handler: invalidateQueries() hoặc appendToTimeline()
```

### 5.3 Subscription scope rules

- Không subscribe toàn bộ event stream — phải scope theo `workspace_id` minimum.
- Khi user xem Task detail: narrow thêm `task_id`.
- Khi user xem Run detail: narrow thêm `run_id`.
- Cross-workspace event không bao giờ được lẫn.

### 5.4 SSE degradation behavior

Nếu SSE down: UI vẫn hoạt động bằng polling fallback (nếu có) hoặc thông báo rõ "Real-time updates paused — data may be stale". Nút manual refresh được expose. Không được để user nghĩ hệ đang real-time khi thực ra không (doc 12 mục 7.3).

---

## 6. Permission-aware Rendering Model

### 6.1 Nguyên tắc: Backend trả về capability flags

Backend API response cho mỗi resource phải include một `_capabilities` object:

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

Frontend render theo `_capabilities` — không suy ra permission từ user role.

### 6.2 Tại sao không suy ra permission ở client

- Permission resolution là 7-tầng (doc 09 mục 5) — client không có đủ context.
- Role có thể là `(own)` — client không biết resource ownership đầy đủ.
- Policy-gated capabilities phụ thuộc workspace policy — client không có policy store.
- Frontend suy permission = frontend có thể bị bypass bằng DevTools.

### 6.3 Capability flag rendering pattern

```tsx
// CORRECT — render theo capability từ server
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

// FORBIDDEN — suy permission ở client
function TaskActions({ task, user }) {
  const canCancel = user.role === 'admin' || task.createdBy === user.id  // ❌
  ...
}
```

### 6.4 Artifact access rendering

Artifact view phải check `state × taint` trước khi render download button — theo đúng access matrix từ doc 10 mục 6.1. Backend trả `_capabilities.can_download` đã tính xét taint. Frontend không tự check.

Tainted artifact: hiển thị taint badge rõ ràng. Download button ẩn trừ khi `_capabilities.can_download = true` (chỉ đúng nếu user có `artifact:untaint` và artifact đã được untaint).

---

## 7. Investigation Surfaces

Đây là 6 surfaces phân biệt Agent OS với dashboard AI thông thường. Mỗi surface có route riêng, data source riêng, và audience riêng (từ doc 11 mục 6).

### 7.1 Task Timeline

**Route:** `/workspaces/:workspaceId/tasks/:taskId`  
**Data:** `GET /tasks/:taskId/timeline`  
**Audience:** User, Developer, Operator

**Phải hiển thị:**
- Trục thời gian chronological từ `task.submitted` đến terminal state.
- Tất cả Run trong task với status badge, duration bar.
- Approval gates: ai yêu cầu, ai quyết định, waiting time.
- Error summary nếu failed.
- Link sang Run timeline của từng Run.

**Component requirements:**
- Timeline không được tự compute từ Step data — phải dùng timeline API.
- Approval history phải fetch từ `approval-center` API, không tự join.

### 7.2 Run Timeline (Step Waterfall)

**Route:** `/runs/:runId`  
**Data:** `GET /runs/:runId/steps` + `GET /runs/:runId/agent-invocations`  
**Audience:** Developer, Operator

**Phải hiển thị:**
- Waterfall view của Steps (sequential và parallel).
- Với mỗi Step: status, duration, input/output snapshot hash (không phải raw content).
- AgentInvocation details: model, tokens, cost, tool call count.
- Sandbox: class, duration, violation flag.
- Artifacts tạo ra trong Run với taint badge.
- Error detail cho failed Step.
- Link sang distributed trace (external tracing backend).

### 7.3 Sandbox Session View

**Route:** `/runs/:runId/sandbox/:sandboxId`  
**Data:** `GET /sandboxes/:sandboxId/session`  
**Audience:** Developer, Security/Admin

**Phải hiển thị:**
- Thời gian sống của Sandbox.
- Sequence of tool calls/commands.
- Policy violations nếu có.
- Network egress attempts với allow/deny status.
- Termination reason.

**Constraint:** Không hiển thị raw agent reasoning hay raw message content — chỉ metadata và actions.

### 7.4 Artifact Lineage View

**Route:** `/artifacts/:artifactId/lineage`  
**Data:** `GET /artifacts/:artifactId/lineage/graph` + `GET /artifacts/:artifactId/provenance`  
**Audience:** Security/Admin, Developer, Auditor  
**SLO:** Load trong < 2 giây (từ doc 11 O2)

**Phải hiển thị:**
- DAG visualization: nodes là artifacts, edges là lineage edge types.
- Màu node theo `state × taint`: ready/clean, ready/tainted, failed, archived.
- Hover node: artifact type, created_at, run/step/model context.
- Provenance completeness indicator: 5/5 hay thiếu field nào.
- Taint propagation path nếu tainted.

**Component requirements:**
- DAG renderer phải handle cycle detection (backend đã reject nhưng frontend phải graceful degrade nếu nhận malformed data).
- Không tự compute ancestor/descendant — chỉ render từ API response.

### 7.5 Taint Investigation View

**Route:** `/artifacts/:artifactId/taint`  
**Data:** `GET /artifacts/:artifactId/taint-status` + downstream artifacts  
**Audience:** Security/Admin

**Phải hiển thị:**
- Taint origin: violation / manual / propagation / model anomaly.
- Propagation path: artifact nào nhận taint từ đây.
- Downstream impact count.
- Blocked download attempts (từ audit log).
- Untaint history.
- Link sang security violation event.

### 7.6 Approval Audit View

**Route:** `/workspaces/:workspaceId/audit`  
**Data:** `GET /audit?type=approval&...`  
**Audience:** Admin, Auditor

**Phải hiển thị:**
- Approval request list với filter: Task/Run/Step/approver/date range.
- Với mỗi approval: target, required role, prompt text, decision, decided_by, decision time.
- Timeout events.
- Export sang CSV/JSON cho compliance.

---

## 8. Module → Backend Service Mapping

Mỗi frontend module biết rõ backend service nào mình gọi. Không được gọi "bất kỳ endpoint nào thấy tiện":

| Frontend Module | Primary Backend Service(s) | Event subscriptions |
|---|---|---|
| `shell/` | `api-gateway` (authn), `workspace-service` | workspace-level SSE |
| `workspace/` | `workspace-service`, `policy-service` (read) | workspace.* |
| `task-monitor/` | `orchestrator-service` (qua api-gateway) | task.*, run.*, step.*, approval.* |
| `artifact-explorer/` | `artifact-service` | artifact.* |
| `lineage-viewer/` | `artifact-service` (lineage API) | artifact.tainted, artifact.untainted |
| `approval-center/` | `orchestrator-service` (qua api-gateway) | approval.* |
| `terminal-app/` | `execution-service` (qua api-gateway, terminal relay) | sandbox.* |
| `audit-viewer/` | `audit-service` | Không (pull-based) |
| `investigation/` | `artifact-service`, `audit-service`, `orchestrator-service` | Scope-narrow per investigation |
| `settings/` | `workspace-service`, `policy-service`, `secret-broker` (metadata only) | Không |
| `notification-center/` | `notification-service` | approval.requested, agent_invocation.waiting_human |

---

## 9. Forbidden Frontend Patterns

Những pattern sau bị cấm tuyệt đối. Nếu phát hiện trong code review, phải revert:

| # | Forbidden Pattern | Lý do | Alternative |
|---|---|---|---|
| FP1 | State machine riêng cho Task/Run/Step trong reducer/store | F3 invariant — state machine là của Orchestrator | Render status từ server state |
| FP2 | `if (user.role === 'admin')` để ẩn/hiện control | F4 invariant — permission suy ở client | Dùng `_capabilities` flags từ API |
| FP3 | Tự compute lineage ancestors/descendants ở client | F5 invariant | Gọi `artifact-service` lineage API |
| FP4 | Terminal component mở WebSocket thẳng tới sandbox | F6 invariant — bypass policy | Terminal relay qua `api-gateway` → `execution-service` |
| FP5 | SSE event handler `set` giá trị trực tiếp vào query cache | F7 invariant | Dùng `invalidateQueries()` rồi refetch |
| FP6 | Optimistic update cho approval decision, Run status, artifact taint | F8 invariant | Server-confirmed update only |
| FP7 | LocalStorage cho domain entity (task, run, artifact) | F2 invariant | Server state only |
| FP8 | Hard-code model list, provider list, capability list ở client | Những list này thay đổi theo policy/config | Fetch từ model-gateway / policy API |
| FP9 | URL pattern `/agent-panel`, `/debug-view` không bám object model | Route phải follow domain language | Dùng `/tasks/:id`, `/runs/:id` |
| FP10 | Render artifact download button mà không check `_capabilities.can_download` | State × taint check phải ở backend | Render theo capability flag |

---

## 10. Non-functional Frontend Requirements

### 10.1 Performance

- Task timeline: render trong < 1 giây với 100 events.
- Artifact lineage DAG: render trong < 2 giây với 50 nodes (SLO từ doc 11).
- SSE reconnect: không flicker UI — skeleton loading trong khi reconnect.

### 10.2 Accessibility

- Mọi action có keyboard shortcut alternative.
- Investigation surfaces có table alternative cho DAG visualization (screen reader support).

### 10.3 Error states

- Network error: retry indicator, không silent fail.
- Permission denied: rõ ràng hiển thị "bạn không có quyền làm việc này" — không ẩn element mà không giải thích.
- SSE down: banner "Real-time updates paused" với manual refresh button.
- Artifact tainted: badge rõ ràng, download disabled, link sang taint investigation.

### 10.4 Progressive loading

- Server state dùng loading/error/success states — không blank screen.
- Lineage DAG: render root nodes trước, expand theo depth.
- Timeline: paginate theo event window — không load toàn bộ 10,000 events lên memory.

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Framework cụ thể (Next.js vs Vite + React Router) | Phụ thuộc deployment mode — Next.js cho cloud, Vite cho electron/local |
| DAG renderer library | Cần evaluate với real lineage data |
| `_capabilities` field format chính thức | Phụ thuộc API Contracts (doc 07) |
| Polling fallback interval khi SSE down | Cần tuning theo UX requirement |
| Micro-frontend vs monorepo bundling strategy | Phụ thuộc team size và deployment cadence |
| Offline mode / local-first cache | Phụ thuộc local-first topology requirements |

---

## 12. Bước tiếp theo

Tài liệu tiếp theo là **16 — Repo Structure Conventions**: khóa monorepo layout, module naming, boundary enforcement, và ánh xạ pressure points PP1–PP10 vào linting/architecture test rules — để codebase từ ngày đầu không thể accidentally vi phạm kiến trúc.
