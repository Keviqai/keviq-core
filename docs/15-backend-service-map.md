# 15 — Backend Service Map

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 03 Bounded Contexts, 04 Core Domain Model, 06 Event Contracts, 09 Permission Model, 13 Deployment Topology, Gate Review 00–12  
**Mục tiêu:** Khóa danh sách service backend, ownership, DB/schema, command/event responsibilities, sync vs async interfaces, restart/recovery duties, và "không được làm gì" cho từng service.

---

## 1. Nguyên tắc Service Map Bất biến

**S1 — Mỗi service owns một tập DB schema không overlap.**  
Không có schema nào bị sở hữu bởi hai service. "Shared schema" là prohibited pattern.

**S2 — State transition authority là bất khả xâm phạm.**  
Chỉ `orchestrator-service` được mutate `Task/Run/Step.*_status`. Mọi service khác đọc qua API hoặc event — không direct write.

**S3 — Mỗi service tự chịu trách nhiệm reconcile sau crash.**  
Không có "global recovery manager". Từng service có recovery duty của riêng nó, theo đúng startup order trong doc 13.

**S4 — Async-first, sync chỉ khi có lý do.**  
Inter-service communication mặc định là event-driven. Sync call (HTTP/gRPC) chỉ được dùng cho: query đọc cần response ngay, command cần ack tức thì từ user, hoặc health check.

**S5 — Service không được gọi thẳng provider bên ngoài — phải qua gateway tương ứng.**  
Model call phải qua `model-gateway`. Secret access phải qua `secret-broker`. Không service domain nào cầm API key trực tiếp.

---

## 2. Service Inventory

| # | Service Name | Bounded Context | DB Schema | Tier |
|---|---|---|---|---|
| SVC-01 | `orchestrator-service` | Task Orchestration (C3) | `orchestrator_core` | Critical |
| SVC-02 | `agent-runtime-service` | Agent Runtime (C4) | `agent_runtime` | Critical |
| SVC-03 | `artifact-service` | Artifact and File (C7) | `artifact_core` | Critical |
| SVC-04 | `execution-service` | Execution and Sandbox (C6) | `execution_core` | Critical |
| SVC-05 | `api-gateway` | Web Shell / Control (C11) | Không có | Critical |
| SVC-06 | `sse-gateway` | Web Shell / Control (C11) | Không có | Important |
| SVC-07 | `auth-service` | Identity and Access (C1) | `identity_core` | Critical |
| SVC-08 | `workspace-service` | Workspace (C2) | `workspace_core` | Critical |
| SVC-09 | `policy-service` | Identity and Access (C1) | `policy_core` | Critical |
| SVC-10 | `secret-broker` | Execution and Sandbox (C6) | `secret_core` | Critical |
| SVC-11 | `model-gateway` | Model Gateway (C9) | `model_gateway_core` | Critical |
| SVC-12 | `audit-service` | Event and Telemetry (C8) | `audit_core` | Critical |
| SVC-13 | `event-store-service` | Event and Telemetry (C8) | `event_core` | Critical |
| SVC-14 | `notification-service` | Human Control (C10) | `notification_core` | Important |
| SVC-15 | `telemetry-service` | Event and Telemetry (C8) | Không có | Supporting |

---

## 3. Service Detail

---

### SVC-01 `orchestrator-service`

**Mục đích:** State transition authority cho Task/Run/Step. Điều phối toàn bộ execution flow.

**DB Schema:** `orchestrator_core`  
**Tables owned:** `tasks`, `runs`, `steps`, `approval_requests`, `retry_policies`, `outbox_orchestrator`

**Responsibilities:**

- Tạo và mutate Task/Run/Step state — **duy nhất có quyền này**
- Timeout watcher cho ApprovalRequest (không phụ thuộc scheduler đơn thuần — PP8)
- Cascade cancel: Task → Run → Step (theo thứ tự trong-ra-ngoài từ doc 05)
- Tạo Run mới khi human re-submit (không resume Run cũ — DNB1)
- Phát command-like event `sandbox.terminate_requested` khi Step bị cancel
- Reconcile approval timeout defensively khi process bất kỳ event workspace đó

**Command interfaces (sync — nhận từ api-gateway):**

| Command | Trigger | Action |
|---|---|---|
| `SubmitTask` | User | Validate, tạo Task, emit `task.submitted` |
| `CancelTask` | User / Policy | Cascade cancel, emit events |
| `ApproveGate` | User | Resolve approval, resume Run |
| `RejectGate` | User | Reject approval, cancel entity |
| `RerunTask` | User | Tạo Run mới trên Task đã failed |

**Event published (outbox):**

Toàn bộ `task.*`, `run.*`, `step.*`, `approval.*` events đã liệt kê trong doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `agent_invocation.completed` | Advance Step → completed, check Run completion |
| `agent_invocation.failed` | Fail Step, propagate |
| `agent_invocation.interrupted` | Update Step, continue cascade |
| `sandbox.terminated` | Confirm cleanup, unblock if needed |
| `artifact.ready` | Confirm Run artifact finalized |
| `approval.timed_out` | Resolve gate, cancel entity |

**Recovery duty (PP2, PP3 từ gate review):**

1. Flush outbox backlog.
2. Rebuild Task/Run/Step state từ `event_core` log với `correlation_id`.
3. Resume timeout watchers.
4. Chỉ sau đó mới accept command mới.

**Không được làm:**

- Direct write vào schema của bất kỳ service nào khác.
- Tự cấp permission (delegate qua `policy-service`).
- Gọi model provider trực tiếp.
- Resume Run đã failed (DNB1).
- Chuyển `run.timed_out` mà không emit tiếp `run.cancelled` trong cùng outbox transaction.

---

### SVC-02 `agent-runtime-service`

**Mục đích:** Chạy AgentInvocation, duy trì reasoning loop, điều phối tool calls.

**DB Schema:** `agent_runtime`  
**Tables owned:** `agent_invocations`, `tool_calls`, `runtime_states`, `outbox_agent_runtime`

**Responsibilities:**

- Nhận AgentInvocation assignment từ Orchestrator
- Duy trì reasoning loop và multi-turn state
- Dispatch tool calls qua Tool/Execution layer
- Gọi model qua `model-gateway` — **không trực tiếp**
- Emit `agent_invocation.*` events
- Sau crash: reconcile invocation state từ event log **trước** khi nhận work mới (PP3)

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `StartInvocation` | Orchestrator | Khởi tạo AgentInvocation |
| `InterruptInvocation` | Orchestrator | Interrupt in-flight invocation |
| `ResumeWithHumanInput` | Orchestrator (relay từ user) | Resume `waiting_human` invocation |
| `DeliverToolResult` | execution-service | Resume `waiting_tool` invocation |

**Event published (outbox):**

Toàn bộ `agent_invocation.*` events từ doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `sandbox.failed` | Interrupt affected invocation |
| `sandbox.terminated` | Confirm execution environment gone |

**Recovery duty (PP3 — critical):**

1. Query event log: tất cả `agent_invocation.started` không có terminal event.
2. Với mỗi dangling invocation: phát `agent_invocation.interrupted` + trigger `sandbox.terminate_requested`.
3. Chỉ sau reconcile mới nhận StartInvocation mới.

**Không được làm:**

- Tạo hoặc ghi artifact trực tiếp (FD9, DNB6).
- Cầm model provider API key (S5).
- Gọi sandbox/execution layer trực tiếp — phải qua command/event.
- Tự quyết định state transition của Task/Run/Step.
- Ghi vào `orchestrator_core` schema.

---

### SVC-03 `artifact-service`

**Mục đích:** Single write point cho mọi artifact. Quản lý lineage, taint, signed URL.

**DB Schema:** `artifact_core`  
**Tables owned:** `artifacts`, `artifact_lineage_edges`, `artifact_provenance`, `signed_url_records`, `outbox_artifact`

**Object storage:** riêng biệt, chỉ `artifact-service` có write credentials (PP10).

**Responsibilities:**

- Nhận artifact registration từ agent-runtime hoặc execution-service — **không nhận từ agent code trực tiếp**
- Validate provenance tuple đầy đủ trước khi accept (PP9, L5 từ doc 10)
- Validate model_version không phải alias (PP9)
- Detect lineage cycle khi ghi edge
- Propagate taint: write DB flag **trước** khi emit event (PP5, DNB11)
- Issue và revoke signed URLs (doc 10 mục 6.2)
- Archive artifacts theo policy

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `RegisterArtifact` | agent-runtime-service | Tạo artifact `pending` |
| `FinalizeArtifact` | agent-runtime-service | Write data, validate checksum, → `ready` |
| `RecordLineageEdge` | agent-runtime-service | Ghi edge, detect cycle |
| `TaintArtifact` | Security event (internal) / admin API | Set taint = true, emit event |
| `UntaintArtifact` | Admin user (artifact:untaint) | Clear taint, ghi review record |
| `IssueSignedUrl` | User request qua api-gateway | Check state×taint×permission, phát URL |
| `ArchiveArtifact` | Scheduler / user | Chuyển → archived |

**Event published (outbox):**

Toàn bộ `artifact.*` events từ doc 06, bao gồm `artifact.lineage_recorded`, `artifact.tainted`, `artifact.untainted`.

**Event consumed:**

| Event | Action |
|---|---|
| `security.violation` | Taint artifact liên quan nếu đang writing/ready |
| `run.cancelled` | Mark pending artifacts của run → failed |

**Recovery duty:**

- Verify artifact `writing` state không bị orphan sau crash.
- Với artifact `writing` không có checksum: chuyển → `failed`, giữ partial data.

**Không được làm:**

- Nhận artifact content trực tiếp từ sandbox hay agent code.
- Xóa artifact bất kỳ (chỉ archive).
- Mutate `checksum` của artifact đã `ready`.
- Phát signed URL cho artifact `tainted` mà không block (doc 10 mục 6.2).
- Ghi artifact `ready` khi provenance tuple thiếu (FR7, DNB12).

---

### SVC-04 `execution-service`

**Mục đích:** Quản lý sandbox lifecycle, terminal sessions, secret mounting, network policy enforcement.

**DB Schema:** `execution_core`  
**Tables owned:** `sandboxes`, `sandbox_attempts`, `terminal_sessions`, `execution_logs_meta`, `outbox_execution`

**Responsibilities:**

- Provision sandbox theo policy snapshot (bất biến sau provisioning — P7, DNB9 implied)
- Quản lý `sandbox_attempt_index` — hỗ trợ 1-N per AgentInvocation (PP4 từ gate review)
- Mount filesystem, inject secrets qua `secret-broker`, apply network policy
- Enforce egress policy (deny-by-default)
- Unmount `/secrets` **trước** khi emit `sandbox.terminated`
- Terminate sandbox khi nhận `sandbox.terminate_requested`
- Relay tool execution kết quả về agent-runtime-service

**Command interfaces (sync):**

| Command | Trigger | Action |
|---|---|---|
| `ProvisionSandbox` | Orchestrator (qua agent-runtime) | Tạo sandbox mới, apply policy |
| `ExecuteTool` | agent-runtime-service | Chạy tool trong sandbox, trả result |
| `TerminateSandbox` | Orchestrator / internal | Cleanup, emit `sandbox.terminated` |

**Event published (outbox):**

Toàn bộ `sandbox.*` events từ doc 06.

**Event consumed:**

| Event | Action |
|---|---|
| `sandbox.terminate_requested` | Trigger termination flow |
| `run.cancelled` | Terminate tất cả sandbox của run đó |
| `agent_invocation.interrupted` | Terminate sandbox của invocation |

**Recovery duty:**

1. Liệt kê sandbox còn active trong `execution_core`.
2. Đối chiếu với orchestrator state (qua API hoặc event log).
3. Sandbox không có active run → terminate và emit `sandbox.terminated`.
4. Emit các event còn thiếu nếu repair workflow cho phép.

**Không được làm:**

- Gọi model provider trực tiếp (model provider key không được present trong execution layer).
- Giữ secret value sau khi sandbox terminated.
- Cho UI gọi trực tiếp (I1, invariant từ doc 02).
- Tiếp tục execution sau khi nhận terminate signal.
- Sửa `policy_snapshot` sau provisioning (P7).

---

### SVC-05 `api-gateway`

**Mục đích:** Điểm vào duy nhất cho request từ client. Authn/authz entry. Response shaping.

**DB Schema:** Không có.

**Responsibilities:**

- Authn (validate JWT/session qua `auth-service`)
- Authz pre-check (forward permission check tới `policy-service` trước khi forward command)
- Route command đến đúng domain service
- Inject `correlation_id` (= new trace_id nếu request mới) vào header
- Shape response cho client
- Rate limiting per workspace/user

**Sync interfaces:**

Tất cả REST/gRPC endpoints của hệ thống. Không có direct write xuống domain schema.

**Không được làm (PP1 — critical):**

- Direct write vào bất kỳ domain schema nào (orchestrator, artifact, agent_runtime, v.v.).
- Cầm domain secret (chỉ cầm auth material).
- Bypass policy check khi forward command.
- Tạo correlation_id khác trace_id (DNB7).

---

### SVC-06 `sse-gateway`

**Mục đích:** Push realtime event về client qua Server-Sent Events.

**DB Schema:** Không có.

**Responsibilities:**

- Subscribe event stream từ `event-store-service` theo `workspace_id`, `task_id`, `run_id`
- Fan-out event đến connected clients
- Hỗ trợ `Last-Event-ID` để client reconnect không mất event
- Rate-limit reconnect per workspace (tránh thundering herd)

**Không được làm:**

- Thay đổi execution semantics khi down (DNB8 implied — SSE chỉ là observation layer).
- Giữ event state — stateless relay only.
- Expose event của workspace A cho client workspace B.

---

### SVC-07 `auth-service`

**Mục đích:** Identity, authn, session management.

**DB Schema:** `identity_core`  
**Tables owned:** `users`, `sessions`, `auth_providers`, `org_memberships`

**Responsibilities:**

- Authenticate user qua provider (local, OAuth, SSO)
- Issue và validate session tokens / JWTs
- Cung cấp user identity cho các service khác

**Fail-closed rule:**

Khi `auth-service` down, `api-gateway` phải deny tất cả request (doc 12 L7, doc 13).

**Không được làm:**

- Làm bất kỳ domain logic orchestration nào.
- Cầm agent/sandbox credentials.

---

### SVC-08 `workspace-service`

**Mục đích:** Quản lý workspace, member, workspace-level settings và connections.

**DB Schema:** `workspace_core`  
**Tables owned:** `workspaces`, `workspace_members`, `workspace_settings`, `workspace_connections`, `repo_snapshots`

**Responsibilities:**

- CRUD workspace
- Manage member và role assignment
- Manage workspace-level connections (Git, storage, connectors)
- Ingest repo snapshots (trigger, không tự chạy execution)

**Event published:** `workspace.*` events nếu cần.

**Không được làm:**

- Thực thi code hay chạy agent.
- Cấp phát secrets (delegated to `secret-broker`).
- Mutate Task/Run state.

---

### SVC-09 `policy-service`

**Mục đích:** Source of truth cho Policy, permission resolution, policy snapshot generation.

**DB Schema:** `policy_core`  
**Tables owned:** `policies`, `policy_rules`, `secret_bindings_meta`

**Responsibilities:**

- Lưu và version Policy cho workspace/task/agent
- Resolve permission theo 7-tầng resolution order (doc 09 mục 5)
- Generate `policy_snapshot` cho sandbox provisioning
- Cung cấp permission decision cho `api-gateway` và `orchestrator-service`

**Fail-closed rule (critical):**

Khi `policy-service` unreachable → tất cả permission check → DENY (doc 09, doc 12 L7).

**Không được làm:**

- Thực thi policy trực tiếp tại sandbox (snapshot được freeze, enforcement là trách nhiệm của execution-service).
- Cho agent Runtime tự request policy expansion.

---

### SVC-10 `secret-broker`

**Mục đích:** Quản lý SecretBinding, inject secret vào sandbox theo policy.

**DB Schema:** `secret_core`  
**Tables owned:** `secret_bindings`, `secret_refs`

**Lưu ý quan trọng:** `secret_core` chỉ lưu `secret_ref` (con trỏ) — không bao giờ lưu secret value thật. Secret value lưu trong vault/KMS bên ngoài.

**Responsibilities:**

- Validate SecretBinding theo permission (doc 09 FD2, FD5)
- Mount secret vào sandbox theo request của `execution-service`
- Revoke secret mount sau sandbox terminated

**Fail-closed rule:**

Nếu `secret-broker` down khi sandbox cần secret → sandbox không được provisioned (fail tại `preparing`).

**Không được làm:**

- Lưu secret value thật trong DB.
- Cấp secret cho agent trực tiếp (chỉ inject vào sandbox environment).
- Cho UI layer query secret value.

---

### SVC-11 `model-gateway`

**Mục đích:** Duy nhất được gọi LLM provider. Routing, fallback, cost tracking.

**DB Schema:** `model_gateway_core`  
**Tables owned:** `model_usage_records`, `provider_configs`, `budget_policies`

**Responsibilities:**

- Route model call đến provider theo policy
- Failover sang backup provider khi primary down
- Track token usage và cost per workspace/invocation
- Resolve model version alias → version cụ thể **trước** khi pass xuống (PP9, DNB12)
- Enforce budget policy

**Không được làm:**

- Cầm provider key trong request từ agent/sandbox.
- Gọi provider trực tiếp từ sandbox (enforcement tại Boundary C — doc 13).
- Trả về model alias trong usage record — phải là version cụ thể.

---

### SVC-12 `audit-service`

**Mục đích:** Append-only audit trail cho mọi permission decision.

**DB Schema:** `audit_core`  
**Tables owned:** `audit_records`

**Durability requirement:** Higher SLA than regular logs. Separate backup. Append-only enforced at DB level (no UPDATE/DELETE permissions on `audit_records`).

**Responsibilities:**

- Nhận audit write từ mọi service có permission decision
- Enforce append-only (no update, no delete)
- Serve audit query cho compliance/admin surfaces

**Fail-closed behavior:**

- Permission.violation write fail → fail-safe deny + P1 alert (doc 09 mục 9.3)
- permission.allowed write fail → allow action nhưng alert P1

**Không được làm:**

- Update hay delete record đã ghi.
- Share write credentials với bất kỳ service nào ngoài audit write path.

---

### SVC-13 `event-store-service`

**Mục đích:** Durable event log. Append-only. Source of truth cho history.

**DB Schema:** `event_core`  
**Tables owned:** `domain_events`, `outbox_relay_state`

**Responsibilities:**

- Nhận event từ outbox relay của các service
- Store append-only
- Serve event replay theo `correlation_id` hoặc scope (doc 06 retention)
- Cung cấp stream cho `sse-gateway` và recovery consumers

**Không được làm:**

- Update hay delete event sau khi ghi.
- Cho service gọi direct insert bỏ qua outbox relay.

---

### SVC-14 `notification-service`

**Mục đích:** Gửi approval requests, human-in-the-loop notifications.

**DB Schema:** `notification_core`  
**Tables owned:** `approval_notifications`, `notification_delivery_log`

**Responsibilities:**

- Subscribe event: `approval.requested`, `agent_invocation.waiting_human`
- Gửi notification đến đúng approver theo role
- Dedup theo `approval_id` (không gửi hai lần cho cùng approval — PP6 liên quan)
- Log delivery status

**Không được làm:**

- Tự quyết định approve/reject.
- Cầm domain state của approval.

---

### SVC-15 `telemetry-service`

**Mục đích:** Aggregation metrics, traces, alerting.

**DB Schema:** Không có domain schema — dùng time-series store và tracing backend.

**Responsibilities:**

- Collect spans (OpenTelemetry)
- Collect metrics
- Evaluate alert rules (doc 11 mục 5)
- Dashboard data aggregation

**Không được làm:**

- Làm bất kỳ execution hay state mutation.
- Expose secret hay raw user content trong metrics/traces (O1 từ doc 11).

---

## 4. Inter-service Communication Map

### 4.1 Sync calls (HTTP/gRPC) — chỉ cho query và command ack

```
api-gateway
  → auth-service          (authn validation)
  → policy-service        (authz pre-check)
  → orchestrator-service  (SubmitTask, CancelTask, ApproveGate, v.v.)
  → artifact-service      (IssueSignedUrl, query metadata)
  → workspace-service     (workspace/member queries)
  → model-gateway         (từ agent-runtime-service)
  → secret-broker         (từ execution-service, mount secrets)
  → policy-service        (từ execution-service, tại sandbox provisioning)
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

api-gateway: KHÔNG có direct DB write vào bất kỳ domain schema nào
sse-gateway: KHÔNG có DB schema
telemetry-service: KHÔNG có domain schema
```

---

## 5. Pressure Points → Service Mapping

Mọi pressure point từ gate review phải được address bởi service cụ thể:

| Pressure Point | Service chịu trách nhiệm | Mechanism |
|---|---|---|
| PP1 — State transition chỉ qua Orchestrator | `orchestrator-service` | Single domain method; no direct write từ service khác; enforce bằng DB credential isolation |
| PP2 — Orchestrator crash recovery | `orchestrator-service` | Flush outbox → rebuild từ event log → resume watchers → accept commands |
| PP3 — Agent Engine rebuild sau crash | `agent-runtime-service` | Query event log cho dangling invocations → interrupt → only then accept new work |
| PP4 — Sandbox 1-N per AgentInvocation | `execution-service` | `sandbox_attempt_index` field; query filter `is_active = true` |
| PP5 — Taint write trước event emit | `artifact-service` | DB write trong outbox transaction trước relay; taint không phụ thuộc event |
| PP6 — `run.timed_out` → `run.cancelled` trong cùng transaction | `orchestrator-service` | Hai outbox entries trong cùng DB transaction |
| PP7 — Tool idempotency contract enforcement | `execution-service` + tool registry | `idempotent` flag bắt buộc trong tool definition; CI idempotency test |
| PP8 — Approval timeout không phụ thuộc scheduler | `orchestrator-service` | Defensive timeout check khi process bất kỳ event workspace đó |
| PP9 — Model version không được là alias | `model-gateway` | Resolve alias → version trước khi pass; validate tại artifact registration |
| PP10 — Artifact table isolation | `artifact-service` | Separate DB schema, separate DB user, separate object storage credentials |

---

## 6. Service Recovery Sequence (tổng hợp từ doc 13)

```
Phase 1 — Infrastructure
  database + object storage + event infrastructure + audit storage

Phase 2 — Control services
  auth-service, policy-service, secret-broker, model-gateway, audit-service

Phase 3 — Artifact plane
  artifact-service
  (phải ready trước orchestrator vì orchestrator confirm artifact finalization)

Phase 4 — Orchestration plane
  orchestrator-service
  (rebuild từ event log, flush outbox, resume watchers)

Phase 5 — Runtime plane
  agent-runtime-service
  (reconcile dangling invocations từ event log)

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

| DNB | Enforced bởi service(s) |
|---|---|
| DNB1 — Run không resume | `orchestrator-service` (RerunTask tạo Run mới) |
| DNB2 — Fail closed | `api-gateway`, `policy-service`, `auth-service` |
| DNB3 — Security violation không auto-recover | `execution-service`, `orchestrator-service` |
| DNB4 — Degraded mode không auto-escalate | `policy-service` (fail-closed), `api-gateway` |
| DNB5 — Recovery có event + audit | Tất cả service có recovery duty |
| DNB6 — Artifact creation chỉ qua artifact-service | `artifact-service` (credential isolation), `agent-runtime-service` (không direct write) |
| DNB7 — trace_id = correlation_id | `api-gateway` (inject), tất cả service (propagate) |
| DNB8 — Execution trace ≠ provenance trace | `telemetry-service` (separate views), `artifact-service` (provenance API) |
| DNB9 — Agent không tự nâng quyền | `execution-service` (policy_snapshot freeze), `policy-service` |
| DNB10 — State transition authority ở Orchestrator | `orchestrator-service` + DB credential isolation |
| DNB11 — Taint write trước event emit | `artifact-service` (outbox transaction order) |
| DNB12 — Model version không là alias | `model-gateway` (resolve), `artifact-service` (validate tại registration) |

---

## 8. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Internal API schema cụ thể (request/response) | Phụ thuộc doc 07 API Contracts — cần review trước khi implement |
| gRPC vs REST cho inter-service sync | Phụ thuộc deployment mode và team preference |
| Service mesh (Istio, Envoy) vs application-level authN | Phụ thuộc infrastructure choice trong doc 13 per mode |
| Multi-instance Orchestrator (leader election vs single-writer) | Phụ thuộc scale requirement thực tế — cần decision trước cloud deployment |
| Agent Runtime worker pool sizing | Cần baseline từ workload thực tế |
| Tool registry service (tách riêng hay embedded trong execution-service) | Cần review khi Tool and Connector Context phức tạp hơn |

---

## 9. Bước tiếp theo

Tài liệu tiếp theo là **14 — Frontend Application Map**: module tree, routing, state management, SSE integration, và constraint "frontend không được giữ source of truth" bám đúng vào service surface đã khóa ở doc này.
