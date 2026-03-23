# 12 — Failure & Recovery Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model, 10 Artifact Lineage Model, 11 Observability Model  
**Mục tiêu:** Khóa failure taxonomy, recovery principles, retry semantics theo từng layer, compensation vs retry vs rerun, duplicate side-effect prevention, degraded modes, và ma trận đầy đủ failure → response.

---

## 1. Failure Taxonomy

### 1.1 Phân biệt Detectability và Recoverability

Đây là tách biệt quan trọng nhất của toàn doc:

| | Định nghĩa | Ví dụ |
|---|---|---|
| **Detectable** | Hệ thống nhận biết được failure đã xảy ra | Sandbox crash, model timeout, artifact write error |
| **Observable** | Failure có đủ context để điều tra nguyên nhân | Failure với full trace, event chain, error detail |
| **Recoverable** | Hệ thống có thể tự động hoặc với human input đưa về trạng thái nhất quán | Transient network error, model rate limit |
| **Auto-recoverable** | Hệ thống được phép tự recover mà không cần human decision | Retry idempotent tool call sau transient error |

**Quy tắc cứng:** Detectable ≠ auto-recoverable. Hệ thống không được auto-recover chỉ vì detect được failure. Mỗi loại failure phải có recovery authorization tường minh trong doc này.

### 1.2 Failure layers

Failure được phân loại theo bounded context của nơi nó xảy ra — không gom theo triệu chứng:

| Layer | Scope | Ví dụ failure |
|---|---|---|
| **L1 — Orchestration** | Task, Run, Step lifecycle | Orchestrator crash giữa Run, Step dependency deadlock |
| **L2 — Runtime / Agent** | AgentInvocation, reasoning loop | Model hallucination vòng lặp, agent không terminate, multi-turn exceed limit |
| **L3 — Sandbox** | Sandbox provisioning, execution, policy | Container crash, OOM, policy violation, egress block |
| **L4 — Model Gateway** | LLM provider calls | Timeout, rate limit, provider outage, malformed response |
| **L5 — Eventing** | Event publish, consume, delivery | Event bus down, consumer lag, duplicate delivery, lost event |
| **L6 — Artifact / Provenance** | Artifact write, lineage, taint | Write partial, provenance incomplete, lineage cycle, taint propagation |
| **L7 — Permission / Security** | Permission check, policy enforcement | EP fail open, audit write fail, violation not caught |
| **L8 — Realtime / SSE** | Client push, connection | SSE stream drop, message lag, client reconnect storm |

---

## 2. Failure Invariants

**F1 — Failure không được silently corrupt state.**  
Khi failure xảy ra, entity phải chuyển sang trạng thái terminal rõ ràng (`failed`, `interrupted`, `cancelled`) theo đúng state machine trong doc 05. Không để entity ở trạng thái ambiguous.

**F2 — Recovery không được bỏ qua event emission.**  
Mọi state transition trong recovery — dù là auto-retry hay human-triggered rerun — đều phải phát event tương ứng theo doc 06. Không có "silent fix".

**F3 — Retry không được replay side effects đã thực hiện.**  
Trước khi retry, hệ thống phải verify side effects của attempt trước đã xảy ra hay chưa. Idempotency check là bắt buộc, không phải optional.

**F4 — Artifact partial data phải được giữ lại và đánh dấu.**  
Khi artifact write fail, partial data không được xóa. Artifact chuyển sang `failed` với `partial_data_available` flag theo doc 10.

**F5 — Sandbox failure không được lan sang AgentInvocation logic.**  
Sandbox crash là infrastructure failure — không phải agent failure. AgentInvocation nhận `interrupted`, không phải `failed`. Hai lifecycle không được nhập nhằng (doc 05).

**F6 — Security failure không được auto-recover.**  
Permission violation, policy breach, taint detection là terminal. Không có auto-retry. Chỉ human với đúng permission mới được quyết định bước tiếp theo.

**F7 — Recovery phải observable và auditable.**  
Mọi recovery action — kể cả auto-retry — phải có event, trace span, và audit record. Recovery không observable = recovery không tin cậy.

**F8 — Degraded mode phải có ranh giới rõ.**  
Khi hệ chạy degraded (một service down), phải biết chính xác capability nào còn, capability nào mất. Không được để user nghĩ hệ đang hoạt động đầy đủ khi thực ra không.

---

## 3. Recovery Principles

### 3.1 Ba hướng recovery

| Hướng | Ý nghĩa | Khi dùng |
|---|---|---|
| **Retry** | Thực thi lại đúng cùng unit (step, tool call, model call) với cùng input | Transient failure, idempotent operation |
| **Compensation** | Thực hiện hành động ngược để undo side effects đã xảy ra | Failure sau khi side effect đã commit |
| **Rerun** | Tạo Run mới hoàn toàn (không resume Run cũ) | Run-level failure, non-idempotent failure |

**Quyết định cứng từ doc 05: Run không bao giờ được resume.** Mọi failure ở cấp Run đều dẫn đến Rerun — không phải retry Run.

### 3.2 Escalation path

```
Failure detected
  → Can it be retried safely? (idempotent, transient, within retry budget)
      YES → Auto-retry với backoff → nếu hết budget → Fail unit
      NO  → Fail unit ngay
  → Has compensation handler?
      YES → Compensate → emit compensation events
      NO  → Fail unit, propagate up
  → Propagate to parent:
      Step fail → Run decides (retry Step? fail Run?)
      Run fail  → Task decides (rerun? fail Task?)
      Task fail → Human decides (re-submit?)
```

---

## 4. Retry Semantics theo Từng Layer

### 4.1 L1 — Orchestration failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Orchestrator crash giữa Run | Auto-recover | Orchestrator restart | Khôi phục Run từ event log — không tạo Run mới | Không re-emit `run.started` nếu đã có |
| Step dependency deadlock (circular wait) | Không | — | Fail Run | Không |
| Orchestrator mất kết nối Event Store | Degrade + alert | Operator | — | Không phát event cho đến khi kết nối phục hồi |
| Approval timeout | Không retry | — | `waiting_approval → cancelled` per state machine | Không |

**Khôi phục Orchestrator sau crash:** Orchestrator phải rebuild state từ event log (`correlation_id` based replay) — không từ in-memory state. Đây là lý do event store là source of truth.

### 4.2 L2 — Runtime / Agent failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Model call transient error (5xx, timeout) | Auto-retry | Agent Engine | AgentInvocation-level (không tạo AgentInvocation mới) | Không re-send nếu request đã được acknowledge |
| Agent vòng lặp không terminate | Không | — | Interrupt AgentInvocation (terminate sandbox) | |
| Agent exceed max turns | Không | — | Fail AgentInvocation | Không tạo thêm model call |
| AgentInvocation interrupted (cascade từ Step cancel) | Không | — | Compensation nếu có handler | Không retry sau interrupt |
| Tool call transient error | Auto-retry (nếu tool khai báo idempotent) | Agent Engine | Tool call level | Verify tool side effect chưa xảy ra trước khi retry |
| Tool call non-idempotent error | Không | — | Fail Step | Không |

**Tool idempotency contract:** Tool phải khai báo `idempotent: true/false` khi đăng ký. Agent Engine chỉ auto-retry tool call với `idempotent: true`.

### 4.3 L3 — Sandbox failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Container provisioning fail (transient) | Auto-retry | Sandbox Manager | Tạo Sandbox mới (không retry cùng Sandbox) | Không |
| OOM / resource exhaustion | Không auto-retry | Operator alert | Fail AgentInvocation, escalate | Cần human review resource limits |
| Policy violation | Không | — | Violation cascade (doc 08): block → fail step → interrupt → terminate | Không |
| Sandbox crash mid-execution | Không auto-retry | — | `sandbox.failed` → interrupt AgentInvocation → fail Step | Không taint artifact nếu chưa có write |
| Egress block (expected, policy) | Không retry | — | Block tool call, emit `security.violation` | |
| Egress block (transient network) | Retry tool call (nếu idempotent) | Agent Engine | Tool call level | Sandbox không trực tiếp retry |

**Tạo Sandbox mới ≠ retry Run.** Sandbox mới cho cùng AgentInvocation là acceptable nếu failure là infra-level và không có side effects.

### 4.4 L4 — Model Gateway / Provider failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Provider HTTP 429 (rate limit) | Auto-retry với backoff | Model Gateway | Request level — transparent với Agent | Không gọi provider lần 2 cho cùng request nếu đang chờ response |
| Provider HTTP 5xx (transient) | Auto-retry (max 3) | Model Gateway | Request level | Idempotency key phải gửi kèm request |
| Provider timeout | Auto-retry (max 2) | Model Gateway | Request level | Cancel request cũ trước khi retry |
| Provider outage (tất cả endpoint down) | Failover sang backup provider | Model Gateway | Transparent với Agent nếu backup available | Ghi `model_gateway.fallback_activated` metric |
| Malformed response từ provider | Không retry | — | Fail AgentInvocation | |
| Provider trả về content vi phạm policy | Không retry | — | Flag và fail AgentInvocation | Taint artifact nếu output đã được partial write |

**Idempotency key với provider:** Model Gateway phải gửi `request_id` (= `agent_invocation_id:attempt_number`) cùng mọi provider request. Nếu provider hỗ trợ, dùng để detect duplicate.

### 4.5 L5 — Eventing failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Event bus down (publisher không thể ghi) | Queue locally (outbox) | Publisher (via outbox relay) | Message level — transparent nếu dùng outbox | Không drop event — outbox đảm bảo durability |
| Consumer lag (processing chậm) | Không retry — là throughput issue | Operator | Scale consumer | Không |
| Duplicate delivery (at-least-once) | Idempotency check trước process | Consumer | Message level | Không process nếu `event_id` đã có trong idempotency store |
| Lost event (không có trong store sau crash) | Không thể retry event đã mất | — | Orchestrator rebuild từ entity state | Alert ops team |
| Consumer crash giữa processing | Requeue message | Message broker | Message level | Consumer phải checkpoint trước khi ack |

**Lost event là failure nghiêm trọng nhất của L5.** Lý do bắt buộc outbox pattern cho critical publishers (doc 06 mục 6.2) là để tránh scenario này.

### 4.6 L6 — Artifact / Provenance failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Artifact write partial (network/storage blip) | Auto-retry write | Artifact service | Write operation level | Giữ partial data — không xóa trước khi retry |
| Artifact write fail (storage full) | Không | — | Fail artifact, alert ops | Không |
| Provenance tuple incomplete | Không | — | Fail artifact với `failure_reason: incomplete_provenance` | Không chuyển sang `ready` |
| Lineage cycle detected | Không | — | Reject edge, emit `lineage_cycle_rejected` alert | Không ghi edge |
| Taint propagation event fail to emit | Retry emit | Artifact service | Event emit level | Giữ taint flag trên artifact — taint không phụ thuộc event |
| Checksum mismatch sau write | Không | — | Fail artifact, alert | Không promote sang `ready` |

**Taint là state, không phải event.** Nếu taint propagation event fail, taint vẫn phải được set trên artifact. Event chỉ là notification — không phải mechanism.

### 4.7 L7 — Permission / Security enforcement failure

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| EP fail open (enforcement point không check được) | Không auto-recover | — | Fail-safe: deny action, alert P0 | Không cho action tiếp tục khi EP fail |
| Audit write failure | Không retry action | — | Alert P1, allow/deny vẫn xảy ra (per doc 09) | Không |
| Policy store unreachable | Deny all | — | Tất cả permission check → denied cho đến khi recover | Không |
| Permission.violation event fail to emit | Retry emit | Permission service | Event emit level | Violation đã xảy ra — không undo |

**EP fail-safe = fail closed.** Khi enforcement point không xác định được policy, mặc định là DENY. Không bao giờ fail open.

### 4.8 L8 — Realtime / SSE degradation

| Failure | Retry? | Ai retry | Cấp retry | Side effects cần chặn |
|---|---|---|---|---|
| Client SSE connection drop | Auto-reconnect | Client | Connection level | Client phải gửi `Last-Event-ID` để nhận lại event bị miss |
| SSE server overload | Không, backpressure | — | Operator scale | Không drop event — buffer với TTL |
| SSE message lag > SLO | Alert P1 | Operator | — | Không |
| Client reconnect storm (thundering herd) | Jitter backoff | Client | Connection level | Server phải rate-limit reconnect per workspace |

---

## 5. Compensation vs Retry vs Rerun

### 5.1 Khi nào dùng Compensation

Compensation được dùng khi failure xảy ra **sau khi side effect đã commit** và side effect đó cần được undo:

- AgentInvocation đã ghi partial output vào external system (qua tool call) → cần gọi compensate endpoint của tool.
- Artifact đã được một phần promote lên `superseded` nhưng process fail → cần rollback `superseded` state.

**Compensation không phải retry.** Compensation là thực hiện hành động ngược — không phải thực hiện lại hành động gốc.

**Compensation phải có handler được khai báo trước.** Không được phép "improvise" compensation tại thời điểm failure.

### 5.2 Khi nào dùng Retry

Retry được dùng khi:
- Failure là transient (network blip, rate limit, timeout).
- Operation là idempotent (gọi lại không tạo thêm side effect).
- Retry budget chưa cạn.

**Retry budget:** Mỗi loại operation có retry budget riêng (max attempts + total time window). Hết budget → fail unit, không tiếp tục retry.

### 5.3 Khi nào dùng Rerun

Rerun được dùng khi:
- Run đã fail và cần thực thi lại từ đầu.
- Human đã review và quyết định thử lại.
- Failure không phải security/permission violation.

**Rerun tạo Run mới hoàn toàn.** Run cũ giữ nguyên `failed` state — không bị xóa, không bị sửa. Lineage của artifact từ Run cũ vẫn còn.

### 5.4 Ma trận quyết định

```
Failure xảy ra
  │
  ├─ Security / permission violation?
  │   YES → Terminal. Human decision only. Không retry, không compensate auto.
  │
  ├─ Side effects đã commit?
  │   YES + có compensation handler → Compensate, rồi fail unit
  │   YES + không có handler       → Fail unit, ghi rõ "uncompensated side effect"
  │   NO                           → Có thể retry nếu idempotent + transient
  │
  ├─ Failure transient + operation idempotent + budget còn?
  │   YES → Auto-retry với backoff
  │   NO  → Fail unit
  │
  └─ Unit level?
      Tool call / model call → Fail Step nếu hết retry
      Step                  → Fail Run
      Run                   → Fail Task (human decides rerun)
      Task                  → Human re-submit
```

---

## 6. Duplicate Side-Effect Prevention

### 6.1 Idempotency check trước mọi side effect

Trước khi thực hiện bất kỳ side effect nào trong retry:

1. Kiểm tra side effect đã xảy ra chưa (qua idempotency store hoặc entity state).
2. Nếu đã xảy ra: bỏ qua, không thực hiện lại.
3. Nếu chưa: thực hiện, ghi vào idempotency store.

### 6.2 Các side effects nguy hiểm nhất nếu duplicate

| Side effect | Consequence nếu duplicate | Prevention mechanism |
|---|---|---|
| `run.started` phát ra 2 lần | Orchestrator tạo 2 Step sequence độc lập | Outbox + event_id idempotency check |
| Artifact finalization chạy 2 lần | Checksum overwrite, lineage corrupt | Artifact service check state trước khi write |
| Approval notification gửi 2 lần | User nhận 2 approval request | Approval dedup theo `approval_id` |
| Sandbox provisioned 2 lần | 2 Sandbox cùng chạy 1 AgentInvocation | Sandbox Manager lock per `agent_invocation_id` |
| Taint propagation chạy 2 lần | Taint record duplicate | Idempotent taint write — check trước khi set |
| `task.cancelled` cascade chạy 2 lần | Run/Step cancel 2 lần | State check trước khi cascade — chỉ cascade nếu entity chưa terminal |

### 6.3 Idempotency store requirements

- Store `event_id` và `operation_id` với TTL = retention window (doc 06).
- Phải durable — không in-memory only.
- Lookup phải < 10ms p99.

---

## 7. Degraded Modes

Khi một service down, hệ phải có ranh giới rõ về capability còn và mất.

### 7.1 Degraded mode matrix

| Service down | Capability còn | Capability mất | User-visible |
|---|---|---|---|
| **Orchestrator** | Đọc existing task/artifact | Tạo task, chạy run, approval | Banner: "Task execution unavailable" |
| **Agent Engine** | Task/run view, artifact download | Chạy agent, bất kỳ Run nào | Banner: "Agent execution unavailable" |
| **Sandbox Manager** | Task/run view | Bất kỳ Run cần sandbox | Banner: "Execution unavailable" |
| **Model Gateway** | Task/run view, artifact view | Bất kỳ Run gọi LLM | Banner: "AI model unavailable" |
| **Artifact Service** | Task/run view (metadata) | Artifact download, artifact finalization | Warning trên artifact list |
| **Event Store** | Tất cả real-time features off | Timeline view, SSE, realtime status | Banner: "Real-time updates unavailable" |
| **Auth service** | Không có | Toàn bộ | Hard block tại gateway |
| **Observability stack** | Tất cả features vẫn chạy | Monitoring, alerting | Alert tới ops, không user-facing |
| **SSE server** | Polling fallback (nếu implement) | Real-time push | UI poll thay SSE |

### 7.2 Degraded mode không được auto-escalate permission

Khi Policy store unreachable: tất cả permission check phải default DENY. Không mở rộng quyền để "giữ hệ chạy". (F invariant F6 + doc 09 mục 7.)

### 7.3 Degraded mode phải user-visible

User không được nghĩ hệ đang hoạt động đầy đủ khi thực ra degraded. Mọi degraded mode phải:
- Hiển thị banner rõ ràng trong UI.
- Emit `system.degraded` event với scope bị ảnh hưởng.
- Alert ops team theo severity tier (doc 11).

---

## 8. Operator-visible Recovery Surfaces

Những surfaces này bổ sung vào Investigation Surfaces của doc 11, dành riêng cho recovery workflow:

### 8.1 Failed Run Queue

Danh sách Run `failed` chưa được human review — với context đủ để operator/user quyết định có rerun không:
- Error summary + error layer (L1–L8).
- Retry history: đã retry mấy lần, tại step nào.
- Artifact partial data status.
- Compensation status (nếu có).
- Quick action: "Rerun" (tạo Run mới), "Archive" (đóng lại không rerun).

### 8.2 Compensation Audit Log

Danh sách mọi compensation action đã được thực hiện:
- AgentInvocation ID, tool call ID được compensate.
- Compensation result: success/fail.
- Uncompensated side effects (nếu có handler không tồn tại).

### 8.3 Degraded Mode Dashboard

Real-time view của service health và capability availability — phân biệt rõ "service up" với "capability available":
- Mỗi service: `liveness`, `readiness`, `dependency` status.
- Mỗi capability: available / degraded / unavailable.
- Active degraded mode alerts.

---

## 9. Mapping Failure → Event / Alert / Audit

| Failure | Event phát ra | Alert | Audit record |
|---|---|---|---|
| Run failed | `run.failed` | P2 (routine) / P1 (nếu burst) | Không bắt buộc |
| Sandbox policy violation | `security.violation`, `sandbox.failed` | P1 | Bắt buộc |
| EP fail open | `permission.violation` | P0 | Bắt buộc |
| Artifact provenance incomplete | `artifact.failed` | P2 | Không bắt buộc |
| Artifact taint propagated | `artifact.tainted` | P1 | Bắt buộc |
| Lineage cycle rejected | `artifact.lineage_cycle_rejected` | P2 | Không bắt buộc |
| Event lost (outbox relay fail) | `system.event_loss_detected` | P0 | Bắt buộc |
| Model provider all down | `model_gateway.all_providers_down` | P0 | Không bắt buộc |
| Agent escalation attempt | `security.violation` | P1 | Bắt buộc |
| Audit write failure | `system.audit_write_failed` | P1 | N/A (là chính failure này) |
| Orchestrator rebuild từ event log | `system.orchestrator_recovered` | P2 | Bắt buộc |
| Compensation success | `agent_invocation.compensated` | Không | Bắt buộc |
| Compensation fail | `agent_invocation.compensation_failed` | P1 | Bắt buộc |

---

## 10. Forbidden Recovery Actions

Những hành động sau không bao giờ được phép dù dưới bất kỳ hoàn cảnh failure nào:

| # | Forbidden | Lý do |
|---|---|---|
| FR1 | Resume Run đã `failed` — chỉ tạo Run mới | Giữ lineage sạch, state machine không bị bypass |
| FR2 | Auto-recover sau security/permission violation | F6 invariant — security terminal là terminal |
| FR3 | Retry tool call không idempotent sau failure | Tránh duplicate side effects ngoài hệ thống |
| FR4 | Xóa artifact partial data khi write fail | L4 invariant từ doc 10 — partial data phải giữ |
| FR5 | Sửa event đã ghi trong event store để "fix" failure | Event là fact — không sửa, chỉ ghi correction |
| FR6 | Fail open khi Policy store unreachable | Luôn fail closed |
| FR7 | Ghi artifact `ready` khi provenance tuple chưa đủ | L5 invariant từ doc 10 |
| FR8 | Tắt taint flag mà không có `artifact:untaint` actor | Security invariant từ doc 09 + doc 10 |
| FR9 | Bỏ qua audit record trong recovery action | F7 invariant — recovery phải auditable |
| FR10 | Propagate compensation tự động mà không có declared handler | Improvised compensation nguy hiểm hơn là để lỗi |

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Retry budget cụ thể (số lần, time window) theo operation type | Cần baseline từ vận hành thực tế |
| Compensation handler registry — schema và registration flow | Phụ thuộc vào tool contract layer (doc 07) |
| Circuit breaker thresholds per provider/service | Cần tuning theo deployment và SLO thực tế |
| Chaos engineering policy (deliberate failure injection) | Không thuộc architecture layer — thuộc QA/ops process |
| Partial run replay (replay từ step N thay vì từ đầu) | Complex, cần đánh giá reproducibility tuple trước khi quyết định |

---

## 12. Bước tiếp theo

Bộ doc lõi (00–12) giờ đã đủ để mô tả toàn bộ "ý chí hệ thống". Phần còn lại là đóng vỏ kiến trúc:

- **13 — Deployment Topology:** local / cloud / hybrid, service placement, network boundary.
- **14 — Frontend Application Map:** module tree, routing, state management, SSE integration.
- **15 — Backend Service Map:** service list, ownership, inter-service contracts.
- **16 — Repo Structure Conventions:** monorepo vs polyrepo, naming, module boundaries.
- **17 — Implementation Roadmap:** Phase A/B/C theo kiến trúc đã khóa, vertical slices, milestone criteria.
