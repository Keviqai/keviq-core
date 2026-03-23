# 17 — Implementation Roadmap

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** Toàn bộ docs 00–16  
**Mục tiêu:** Execution contract cho team — không phải roadmap marketing. Khóa philosophy, phase model, entry/exit conditions, vertical slice order, PP preconditions, architecture gates, và definition of done.

---

## 1. Implementation Philosophy

**Architecture-first, implementation-increments.**  
Bộ docs 00–16 là constitution của hệ. Không có code nào được viết để "chứng minh concept" rồi sau đó refactor cho phù hợp với kiến trúc. Nếu muốn thay đổi kiến trúc, thay đổi doc trước — rồi mới code.

**Vertical slices only.**  
Không build "toàn bộ orchestrator layer" rồi mới build "toàn bộ agent layer". Mỗi slice cắt thẳng qua mọi layer (DB → domain → API → event → frontend) cho một capability cụ thể, end-to-end, có thể verify được. Slice chưa xong thì không được bắt sang slice tiếp theo.

**Risk-first ordering.**  
Thứ tự slice bám vào rủi ro kiến trúc, không bám vào tính năng user muốn thấy trước. Những gì có thể phá kiến trúc về sau (state machine authority, outbox, artifact isolation, security boundary) phải được khóa sớm nhất.

**Pressure points là preconditions, không phải nice-to-have.**  
PP1–PP10 từ gate review không phải technical debt để giải quyết sau. Mỗi slice liệt kê PP nào bắt buộc pass. Merge bị block nếu PP precondition chưa đạt.

**Done là done — không có "mostly done".**  
Definition of Done (mục 7) áp dụng cho mọi slice, mọi phase. Không có "chạy được nhưng chưa có tests", "deployed nhưng chưa có audit trail".

---

## 2. Phase Model

```
Phase A — Foundation & Skeleton         (tuần 1–4)
  Mọi service skeleton, DB schema, event infrastructure, import boundaries,
  architecture tests. Hệ chưa làm được việc gì có ý nghĩa — nhưng không
  thể vi phạm kiến trúc.

Phase B — First Vertical Slice          (tuần 5–12)
  End-to-end: user submit task → orchestrator → run → step →
  agent invocation → artifact → SSE → timeline view.
  Bằng chứng rằng toàn bộ xương sống hoạt động đúng.

Phase C — Hardening & Security Tightening  (tuần 13–20)
  Sandbox enforcement, policy enforcement, taint/lineage, approval flows,
  failure recovery, multi-step workflows, investigation surfaces.
  Hệ trở thành "production-ready" cho single-tenant.

Phase D — Topology Expansion            (tuần 21–28)
  Hybrid topology, multi-tenant isolation, scale hardening,
  model gateway fallback, compliance surfaces, performance SLOs.
```

Mỗi phase có **entry conditions** (cần thỏa mãn trước khi bắt đầu) và **exit criteria** (cần thỏa mãn trước khi coi phase đó xong).

---

## 3. Entry Conditions & Exit Criteria

### Phase A — Foundation & Skeleton

**Entry conditions:**
- Docs 00–17 đã được review và không có GAP nghiêm trọng còn mở.
- Team đã đọc và acknowledge gate review + DNB1–DNB12.
- Monorepo đã init với pnpm + Turborepo.
- Docker Compose local-first topology đã setup.

**Exit criteria:**
- Tất cả 15 service có skeleton: Dockerfile, `main.py`/`main.ts`, health endpoint `/healthz/live` + `/healthz/ready`.
- Tất cả DB schemas đã tạo với đúng ownership (mỗi schema có DB user riêng).
- Outbox table đã tạo cho mọi service cần emit event.
- `dependency-cruiser` và `import-linter` đã chạy clean (0 violations).
- Architecture test PP1 đã pass: `test_no_status_write_outside_orchestrator`.
- Architecture test PP10 đã pass: `test_artifact_schema_credentials`.
- CI pipeline đã chạy đủ stages: lint → arch-test → build.
- `event-store` service có thể nhận và replay event theo `correlation_id`.
- `sse-gateway` có thể mở connection và gửi heartbeat.

**Không cần có trong Phase A:**
- Business logic bất kỳ.
- UI bất kỳ.
- Model call bất kỳ.

---

### Phase B — First Vertical Slice

**Entry conditions:**
- Phase A exit criteria đã đạt.
- `api-gateway` đã có authn qua `auth-service`.
- `policy-service` có thể trả permission decision cho ít nhất một resource type.

**Exit criteria:**
- User có thể submit Task → Task chuyển `draft → pending → running` đúng state machine.
- Orchestrator tạo Run, tạo Step, assign AgentInvocation.
- AgentInvocation gọi model qua `model-gateway` (không gọi trực tiếp).
- Model response được wrap thành Artifact thông qua `artifact-service` (không direct write).
- Artifact có đủ provenance tuple 5 thành phần — không được là alias cho model version.
- `artifact.ready` event được emit.
- `sse-gateway` push timeline events về client.
- Frontend Task timeline hiển thị đúng thứ tự `task.submitted → run.started → step.started → ... → artifact.ready`.
- Khi Orchestrator crash và restart: Run state được rebuild đúng từ event log (PP2).
- Agent Runtime crash và restart: dangling AgentInvocation bị interrupt đúng (PP3).
- Tất cả PP preconditions cho Slices 1–5 đã pass (xem mục 4).

---

### Phase C — Hardening & Security Tightening

**Entry conditions:**
- Phase B exit criteria đã đạt.
- Gate 1 và Gate 2 đã pass (xem mục 5).

**Exit criteria:**
- Sandbox provisioning + policy enforcement hoạt động: egress deny-by-default, `/secrets` unmount trước `sandbox.terminated`.
- Policy violation cascade hoạt động: violation → taint artifact → block download.
- Approval flow đầy đủ: `waiting_approval`, timeout watcher, approve/reject, cascade cancel.
- Failure recovery: Run failed → human triggers Rerun → new Run created (không resume cũ).
- Taint propagation: taint artifact cha → taint artifact con tự động, taint write trước event emit (PP5).
- Investigation surfaces: Artifact Lineage View, Taint Investigation View, Sandbox Session View đều load trong < 2 giây.
- Audit trail: mọi permission decision có audit record, `permission.violation` trigger alert.
- Degraded mode: khi `policy-service` down, tất cả request bị deny (không fail open).
- Tất cả PP preconditions cho Slices 6–9 đã pass.
- Gate 3 và Gate 4 đã pass.

---

### Phase D — Topology Expansion

**Entry conditions:**
- Phase C exit criteria đã đạt.
- Gate 1–4 đã pass.

**Exit criteria:**
- Hybrid topology: control plane trên cloud, execution plane local, event/artifact relay nhất quán.
- Multi-tenant isolation: workspace A không đọc/ghi được resource của workspace B.
- Model Gateway fallback: primary provider down → fallback sang backup transparent với agent.
- Performance SLOs đạt: API command ack p95 < 500ms, SSE propagation p95 < 2s, lineage view < 2s.
- Compliance surfaces: Approval Audit View có export CSV/JSON.
- `sandbox_attempt_index` hoạt động đúng trong multi-attempt scenario (PP4).
- Load test: 50 concurrent runs không làm vỡ state machine.

---

## 4. Vertical Slice Order & PP Preconditions

### Slice 1 — Workspace + Auth + Policy Bootstrap

**Capability:** User có thể đăng nhập, tạo workspace, mời member, assign role.

**Services involved:** `auth-service`, `workspace-service`, `policy-service`, `api-gateway`

**Deliverables:**
- User registration + login (JWT).
- Workspace CRUD.
- Member invite + role assignment.
- Permission resolution cho workspace:read, workspace:write.
- `_capabilities` flags được trả về trong workspace API response.

**PP preconditions phải pass:**
- PP1 ✓ (schema isolation đã có từ Phase A — orchestrator không thể write identity schema)
- PP10 ✓ (artifact schema isolation đã có từ Phase A)

**Architecture test:**
- `test_policy_fail_closed`: khi `policy-service` unreachable → tất cả request → 403.
- `test_capabilities_in_response`: workspace response phải có `_capabilities` object.

---

### Slice 2 — Task Submit → Orchestrator → Event/Outbox

**Capability:** User submit Task → Orchestrator xử lý → events được emit và persist.

**Services involved:** `api-gateway`, `orchestrator-service`, `event-store`

**Deliverables:**
- `SubmitTask` command end-to-end.
- Task state transition: `draft → pending` với event `task.submitted` + `task.pending`.
- Outbox relay: event persist vào `event-store`, queryable bằng `correlation_id`.
- Correlation ID injection tại `api-gateway` → propagate qua toàn bộ chain.

**PP preconditions phải pass:**
- PP1: `orchestrator-service` là nơi duy nhất mutate `task_status` — arch test pass.
- PP6: `run.timed_out` + `run.cancelled` trong cùng transaction — unit test pass (có thể chưa trigger nhưng code path phải đúng).

**Architecture test:**
- `test_no_status_write_outside_orchestrator` pass.
- `test_correlation_id_propagated`: mọi event từ slice này có `correlation_id` khớp với trace header.

---

### Slice 3 — Run/Step Lifecycle

**Capability:** Orchestrator tạo Run, Step, và quản lý lifecycle đầy đủ.

**Services involved:** `orchestrator-service`, `agent-runtime-service`, `event-store`

**Deliverables:**
- Task `pending → running`, tạo Run `queued → preparing → running`.
- Run tạo Step sequence đơn giản (1 step).
- Step `pending → running`.
- AgentInvocation `initializing → running`.
- Cancel cascade: Task cancel → Run cancel → Step cancel → AgentInvocation interrupt.
- Crash recovery: Orchestrator restart rebuild state từ event log (PP2).
- Agent Runtime restart reconcile dangling invocation (PP3).

**PP preconditions phải pass:**
- PP2: `test_orchestrator_startup_order` — outbox flush trước accept.
- PP3: `test_agent_runtime_no_accept_before_reconcile`.
- PP6: `test_timed_out_emits_cancelled`.

**Architecture test:**
- `test_cancel_cascade_inside_out`: cancel order đúng (Step trước, Run sau, Task sau).
- `test_run_no_resume`: không có code path nào cho `run.status = 'running'` trên Run đã `failed`.

---

### Slice 4 — Model Gateway + Agent Invocation

**Capability:** AgentInvocation gọi được LLM qua model gateway, nhận response.

**Services involved:** `agent-runtime-service`, `model-gateway`

**Deliverables:**
- `model-gateway` route call đến provider, return response.
- Model version alias được resolve thành version cụ thể trước khi return (PP9).
- Token tracking: `agent.prompt_tokens`, `agent.completion_tokens` được ghi.
- Retry với backoff khi provider 429 hoặc 5xx (max 3 attempts).
- AgentInvocation `running → completed` khi model trả response.

**PP preconditions phải pass:**
- PP9: `test_model_version_not_alias` — `model-gateway` không trả alias.

**Architecture test:**
- `test_agent_no_direct_provider_key`: sandbox và agent-runtime không có provider API key trong env.
- `test_model_gateway_sole_exit`: không có HTTP call từ non-gateway service đến known provider domains.

---

### Slice 5 — Artifact Creation + Lineage

**Capability:** AgentInvocation tạo Artifact qua `artifact-service`, lineage được ghi.

**Services involved:** `agent-runtime-service`, `artifact-service`, `model-gateway` (cho provenance)

**Deliverables:**
- `RegisterArtifact` → `FinalizeArtifact` flow.
- Provenance tuple validation: reject artifact nếu thiếu bất kỳ 1 trong 5 thành phần.
- Model version trong provenance: phải là version cụ thể (PP9, DNB12).
- `artifact.ready` event emit sau khi finalize.
- Lineage edge ghi: `generated_from` root type.
- Checksum validation trước khi `ready`.

**PP preconditions phải pass:**
- PP5: `test_taint_db_before_outbox` (infrastructure phải đúng dù chưa có taint trigger).
- PP10: `test_artifact_schema_credentials` — artifact-service là duy nhất có write.
- DNB12: model version không phải alias — validated tại `RegisterArtifact`.

**Architecture test:**
- `test_artifact_provenance_complete`: `FinalizeArtifact` với missing field → 400.
- `test_artifact_no_direct_write`: không có INSERT vào `artifact_core` từ ngoài artifact-service.

---

### Slice 6 — SSE + Task/Run Timeline Frontend

**Capability:** User xem Task Timeline và Run Timeline real-time qua SSE.

**Services involved:** `sse-gateway`, `event-store`, `api-gateway`, frontend `task-monitor`

**Deliverables:**
- SSE subscription scope theo `workspace_id` và `task_id`.
- `Last-Event-ID` reconnect không mất event.
- Frontend: Task Timeline render đúng chronological với event chain.
- Frontend: SSE event trigger `invalidateQueries()` — không set cache trực tiếp (FP5).
- Frontend: `_capabilities` flags render correct buttons per task state.
- SSE down: banner "Real-time updates paused" hiển thị rõ.

**PP preconditions phải pass:**
- DNB7: `trace_id = correlation_id` — không có separate traceId generation (dependency-cruiser rule).
- FP1–FP10 checklist pass trong code review.

**Architecture test:**
- `test_sse_scope_isolation`: client workspace A không nhận event workspace B.
- `test_capabilities_not_role_derived`: không có `user.role` check trong frontend component files.

---

### Slice 7 — Sandbox Provisioning + Terminal

**Capability:** AgentInvocation chạy được tool trong Sandbox, terminal relay hoạt động.

**Services involved:** `execution-service`, `secret-broker`, `policy-service`

**Deliverables:**
- Sandbox provisioning với `policy_snapshot` freeze.
- `sandbox_attempt_index` — second attempt có index 2 (PP4).
- Secret injection qua `secret-broker` — không cầm secret value ở execution layer.
- `/secrets` unmount trước `sandbox.terminated`.
- Egress deny-by-default: tool call đến unlisted domain bị block + `security.violation` emit.
- Terminal relay: frontend terminal app → api-gateway → execution-service (không direct WebSocket).

**PP preconditions phải pass:**
- PP4: `test_sandbox_attempt_index_required`.
- PP7: `test_tool_idempotent_flag_required` — mọi tool có `idempotent` flag.

**Architecture test:**
- `test_sandbox_policy_snapshot_frozen`: policy_snapshot không thay đổi sau provisioning.
- `test_secrets_unmounted_before_terminated`: `sandbox.terminated` event chỉ emit sau `/secrets` unmount.
- `test_terminal_no_direct_socket` (frontend arch test): không có `new WebSocket(sandboxUrl)` trong terminal module.

---

### Slice 8 — Approval + Human-in-the-loop

**Capability:** AgentInvocation có thể pause để chờ human approval, timeout đúng.

**Services involved:** `orchestrator-service`, `notification-service`, frontend `approval-center`

**Deliverables:**
- Step chuyển `running → waiting_approval` khi agent emit approval request.
- `notification-service` gửi notification đến approver.
- Dedup: cùng `approval_id` không gửi hai lần.
- Human approve → Step resume.
- Human reject → Step cancel cascade.
- Timeout: approval không có decision sau `timeout_at` → `cancelled` — **watcher không phụ thuộc scheduler** (PP8).
- `run.timed_out` → `run.cancelled` trong cùng outbox transaction (PP6).

**PP preconditions phải pass:**
- PP6: `test_timed_out_emits_cancelled`.
- PP8: `test_approval_timeout_defensive_check`.

**Architecture test:**
- `test_approval_dedup`: hai notification attempt cho cùng `approval_id` → chỉ một delivered.
- `test_timeout_without_scheduler`: giả scheduler down, event trigger vẫn resolve timeout.

---

### Slice 9 — Failure Recovery + Taint + Investigation Surfaces

**Capability:** System xử lý đúng failure, taint propagate, investigation surfaces hoạt động.

**Services involved:** Tất cả service liên quan, frontend `investigation/`

**Deliverables:**
- Taint: `artifact_service` write taint flag **trước** outbox emit (PP5, DNB11).
- Taint propagation qua lineage edges.
- Tainted artifact: download blocked, investigation surface hiển thị taint origin.
- Policy violation cascade: violation → interrupt invocation → terminate sandbox → taint artifact.
- Rerun: Run failed → human triggers Rerun → new Run, run cũ vẫn `failed` (DNB1).
- Artifact Lineage View: load < 2 giây.
- Taint Investigation View: hiển thị propagation path + blocked downloads.
- Approval Audit View: queryable, exportable.
- Degraded mode: `policy-service` down → 403 all requests, banner hiển thị.

**PP preconditions phải pass:**
- PP5: `test_taint_db_before_outbox`.
- DNB1: `test_run_no_resume`.
- DNB11: taint write order enforced.

**Architecture test:**
- `test_taint_propagation_downstream_only`: taint không lan ngược lên parent.
- `test_policy_down_fail_closed`: mock policy-service down → tất cả request → 403.
- `test_degraded_mode_banner`: SSE down → frontend hiển thị degraded indicator.

---

## 5. Architecture Gates

Gates là checkpoints đo được. Không gate nào có thể bị skip hay deferred.

### Gate 1 — No Hidden Bypass

**Thời điểm:** Sau Slice 3 (cuối Phase B đầu).

**Pass conditions:**
- `test_no_status_write_outside_orchestrator` pass.
- `test_artifact_no_direct_write` pass.
- `test_agent_no_direct_provider_key` pass.
- `dependency-cruiser` 0 violations.
- `import-linter` 0 violations.
- Không có cross-schema FK trong bất kỳ migration nào.

**Ý nghĩa:** Không có service nào có thể bypass state machine, artifact isolation, hay model gateway — bằng cách nào đó.

---

### Gate 2 — Reproducible Artifact Path

**Thời điểm:** Sau Slice 5.

**Pass conditions:**
- `test_artifact_provenance_complete` pass — thiếu field → reject.
- `test_model_version_not_alias` pass.
- Mỗi artifact `ready` có đủ 5 thành phần trong provenance tuple.
- Lineage DAG không có cycle (`test_lineage_cycle_rejected`).
- `artifact.tainted` event luôn có `artifact.tainted = true` trong DB **trước** event được emit.

**Ý nghĩa:** Bất kỳ artifact nào hệ sinh ra đều có thể bị truy vết đầy đủ và tái tạo.

---

### Gate 3 — Recovery-Safe Orchestration

**Thời điểm:** Cuối Phase B / đầu Phase C.

**Pass conditions:**
- `test_orchestrator_startup_order` pass — outbox flush trước accept.
- `test_agent_runtime_no_accept_before_reconcile` pass.
- `test_run_no_resume` pass — không có code path resume Run cũ.
- `test_cancel_cascade_inside_out` pass.
- `test_timed_out_emits_cancelled` pass.
- Manual test: giả crash Orchestrator và Agent Runtime đồng thời → restart → state nhất quán.

**Ý nghĩa:** Hệ không mất trạng thái, không tạo zombie invocations, không có split-brain sau crash.

---

### Gate 4 — Security Boundary Intact

**Thời điểm:** Cuối Phase C.

**Pass conditions:**
- `test_sandbox_policy_snapshot_frozen` pass.
- `test_secrets_unmounted_before_terminated` pass.
- `test_terminal_no_direct_socket` pass.
- `test_policy_down_fail_closed` pass.
- `test_taint_propagation_downstream_only` pass.
- `test_capabilities_not_role_derived` pass.
- Security violation trigger đúng cascade và taint artifact liên quan.
- Audit trail: mọi violation có audit record với đủ fields.

**Ý nghĩa:** Security invariants từ doc 08, 09, 10 được enforce bằng code, không chỉ bằng quy ước.

---

## 6. Definition of Done

Áp dụng cho mọi slice, mọi PR merge vào main:

### 6.1 Code

- [ ] Feature end-to-end hoạt động theo happy path.
- [ ] Error paths được handle — không có silent failure.
- [ ] Không có `TODO: fix later` trong production code path.

### 6.2 Tests

- [ ] Unit tests cho domain logic mới.
- [ ] Integration test cho cross-service interaction (nếu có).
- [ ] Architecture tests liên quan đến slice này pass.
- [ ] Infra tests liên quan pass.

### 6.3 Architecture Compliance

- [ ] PR checklist từ doc 16 đã được check — không có item unchecked.
- [ ] `dependency-cruiser` 0 violations sau thay đổi.
- [ ] `import-linter` 0 violations sau thay đổi.
- [ ] PP preconditions cho slice này pass.

### 6.4 Events & Audit

- [ ] Mọi domain mutation cần event: outbox entry tồn tại.
- [ ] Event type đúng naming convention.
- [ ] Correlation ID được propagate đúng.
- [ ] Audit record được tạo cho mọi permission decision trong slice này.

### 6.5 Docs

- [ ] Nếu slice làm lộ inconsistency với docs 00–16: inconsistency được ghi nhận và doc được update hoặc CLARIFY note được tạo.
- [ ] Không có architectural decision mới nào được embedded trong code mà không có doc tương ứng.

### 6.6 Forbidden patterns

- [ ] Không có pattern nào trong FP1–FP10 (doc 14) được introduce.
- [ ] Không có pattern nào trong Forbidden Recovery Actions FR1–FR10 (doc 12) được introduce.
- [ ] Không có DNB1–DNB12 bị vi phạm.

### 6.7 Observability

- [ ] Span attributes đúng theo doc 11 mục 3.4 cho loại span được thêm.
- [ ] Error path emit đúng event.
- [ ] Alert rules liên quan được kiểm tra (nếu slice thêm failure mode mới).

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

Những sai lầm phổ biến trong execution mà roadmap này chủ động cấm:

| Anti-pattern | Consequence | Rule |
|---|---|---|
| Build toàn bộ một layer trước khi build layer tiếp | Không có end-to-end verify sớm; bugs found late | Vertical slices only |
| Defer PP compliance đến "hardening sprint" | PP là debt không trả được sau khi codebase đã lớn | PP preconditions block merge |
| Merge code "mostly working" vào main | DoD bị erode dần | DoD check bắt buộc |
| "Refactor architecture sau khi có MVP" | Architecture sau MVP không refactor được cleanly | Architecture-first, không MVP-first |
| Skip gate review vì "deadline" | Gate violations tích lũy; không detect được trước khi Phase D | Gates không thể skip hay defer |
| Frontend team build UI trước khi service API stable | Frontend kéo ngược backend | Slice order bắt buộc: backend trước |
| Một developer own nhiều bounded context | Knowledge silo; service boundary erode | Mỗi service có clear owner |

---

## 9. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Thời gian cụ thể mỗi slice | Phụ thuộc team size, không thể khóa mà không biết headcount |
| Sprint/iteration structure | Phụ thuộc team's working style |
| External dependency schedule (cloud infra, provider contracts) | Nằm ngoài tầm kiểm soát của kiến trúc |
| Feature prioritization trong Phase D | Phase D là expansion — thứ tự phụ thuộc vào deployment target thực tế |
| Load testing thresholds cụ thể | Cần baseline từ Phase C workload thực |

---

## 10. Kết luận Bộ Architecture Docs 00–17

Bộ tài liệu 00–17 đã khóa:

| Nhóm | Docs | Nội dung |
|---|---|---|
| Vision & Principles | 00, 01, 02, 03 | Tuyên ngôn, goals, invariants, bounded contexts |
| Domain & Lifecycle | 04, 05, 06, 07 | Entity model, state machines, event contracts, API contracts |
| Security & Trust | 08, 09 | Sandbox security, permission model |
| Data & Observability | 10, 11 | Artifact lineage, observability model |
| Resilience | 12 | Failure & recovery model |
| Deployment | 13 | Topology (local/cloud/hybrid) |
| Application | 14, 15 | Frontend map, backend service map |
| Execution | 16, 17 | Repo conventions, implementation roadmap |
| Gate Review | GR | Cross-doc consistency, pressure points, DNB list |

Team có thể bắt đầu Phase A ngay khi doc này được chốt.
