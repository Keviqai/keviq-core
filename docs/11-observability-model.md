# 11 — Observability Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model, 10 Artifact Lineage Model  
**Mục tiêu:** Khóa cách hệ thống được quan sát — ai nhìn thấy gì, để quyết định gì — bao gồm signal taxonomy, trace model, health model, alert model, và investigation surfaces.

---

## 1. Observability Goals

Observability không phải "log nhiều vào". Nó là khả năng trả lời câu hỏi cụ thể mà không cần đọc source code hay SSH vào server.

### 1.1 Ba câu hỏi observability phải trả lời được

| Câu hỏi | Loại | Audience |
|---|---|---|
| "Hệ đang làm gì ngay lúc này?" | Real-time operational | Operator, user |
| "Việc X đã xảy ra thế nào?" | Post-hoc execution trace | Developer, operator |
| "Artifact này đến từ đâu và có đáng tin không?" | Provenance investigation | Security, admin, auditor |

### 1.2 Phân biệt Execution Trace và Provenance Trace

Hai khái niệm này liên quan nhưng không được nhập một:

| | Execution Trace | Provenance Trace |
|---|---|---|
| **Trả lời** | Hệ đã làm gì, theo thứ tự nào, mất bao lâu | Artifact này đến từ đâu, qua những bước nào |
| **Trục thời gian** | Chronological — từ trái sang phải | Causal — từ dưới lên trên (root đến leaf) |
| **Đơn vị** | Step, AgentInvocation, Sandbox session | Artifact, lineage edge, input snapshot |
| **Dùng để** | Debug latency, reproduce lỗi, hiểu flow | Verify trust, audit security, reproduce artifact |
| **Source** | Spans/traces, event stream | Lineage graph, provenance tuple, artifact events |

### 1.3 Observability phục vụ ai

| Actor | Cần thấy gì | Không cần thấy gì |
|---|---|---|
| **User (task owner)** | Task/Run timeline, artifact status, approval queue | Sandbox internals, infra metrics |
| **Developer** | Full execution trace, error detail, tool call sequence, agent reasoning steps | Infra-level hardware metrics |
| **Operator** | Service health, resource utilization, error rates, alert queue | Agent reasoning content |
| **Security/Admin** | Taint events, violation events, audit trail, lineage investigation | User task content (unless needed) |
| **Auditor** | Audit records, approval history, permission decisions | Internal implementation detail |

---

## 2. Signals

Hệ thống sử dụng 6 loại signal, mỗi loại có đặc tính khác nhau về cardinality, latency, và retention.

### 2.1 Logs

Unstructured đến semi-structured text. Dùng cho debug chi tiết và error investigation.

**Quy tắc bắt buộc:**
- Mọi log entry phải có: `timestamp`, `service`, `level`, `correlation_id`, `workspace_id` (nếu có ngữ cảnh).
- Log không được chứa secret value, provider key, hay nội dung raw của user message.
- Log level chuẩn: `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`.
- `DEBUG` log bị tắt mặc định ở production — chỉ bật per-correlation-id khi debug.

**Retention:** 7 ngày hot, 30 ngày cold.

### 2.2 Metrics

Numeric time-series. Dùng cho monitoring, alerting, và capacity planning.

**Taxonomy:**

| Prefix | Ý nghĩa | Ví dụ |
|---|---|---|
| `task.*` | Metrics ở cấp Task | `task.created_total`, `task.completed_duration_ms` |
| `run.*` | Metrics ở cấp Run | `run.active_count`, `run.failed_total` |
| `agent.*` | Metrics ở cấp AgentInvocation | `agent.tokens_used_total`, `agent.cost_usd_total` |
| `sandbox.*` | Metrics ở cấp Sandbox | `sandbox.provisioning_duration_ms`, `sandbox.violation_total` |
| `artifact.*` | Metrics ở cấp Artifact | `artifact.tainted_total`, `artifact.write_duration_ms` |
| `model_gateway.*` | Metrics Model Gateway | `model_gateway.latency_ms`, `model_gateway.error_rate` |
| `permission.*` | Metrics permission decisions | `permission.denied_total`, `permission.violation_total` |
| `service.*` | Infra-level service health | `service.up`, `service.request_rate`, `service.p99_latency` |

**Cardinality rule:** Label không được dùng `artifact_id`, `run_id`, hay bất kỳ UUID nào làm label value — làm vỡ metrics cardinality. Dùng `workspace_id`, `task_type`, `sandbox_class`, `model_id` làm label.

**Retention:** 15 ngày hot (high-resolution), 1 năm downsampled.

### 2.3 Traces (Distributed Tracing)

Structured spans theo chuẩn OpenTelemetry. Dùng để trace execution flow qua nhiều service.

**Trace hierarchy bắt buộc:**

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

**Bắt buộc trên mọi span:**
- `workspace_id`, `task_id`, `run_id` (propagated từ parent)
- `span.kind`: `SERVER`, `CLIENT`, `INTERNAL`
- Span không được chứa secret hay raw user content trong attributes.

**Sampling strategy:**
- 100% sampling cho span có `error = true` hoặc `duration > SLO_threshold`.
- 10% sampling cho span bình thường trong production.
- 100% sampling trong staging và debug mode.

**Retention:** 3 ngày hot (queryable), 14 ngày cold (aggregated).

### 2.4 Events (từ Event Store — doc 06)

Event store là nguồn chân lý lịch sử. Observability layer consume event stream để build materialized views, alert, và investigation surfaces.

**Observability consume events để:**
- Build task/run timeline view.
- Trigger alerts khi certain event patterns xảy ra.
- Feed artifact lineage investigation view.
- Power approval audit view.

Events không phải log — không được treat như log hay duplicate log content vào event store.

**Retention:** Theo doc 06 — 30 ngày hot, 1 năm cold.

### 2.5 Lineage Context

Signal đặc biệt chỉ có trong hệ này. Khi một artifact `failed`, `tainted`, hoặc bị block download, observability layer phải kéo và surface **lineage context** gồm:

- Artifact root type và provenance tuple.
- Toàn bộ parent chain đến root.
- Run/Step/AgentInvocation/Tool/Model tạo ra artifact.
- Taint propagation path (nếu tainted).
- Reproducibility tuple completeness check.

Lineage context phải truy được trong **< 2 giây** từ artifact_id. Đây là SLO cho investigation surface.

### 2.6 Audit Records

Từ doc 09 — mọi permission decision (allow/deny/violation) có audit record. Observability layer aggregate audit records để:
- Power taint investigation view.
- Feed security dashboard.
- Support compliance audit export.

---

## 3. Trace Model

### 3.1 Trace ID = Correlation ID

`correlation_id` từ event envelope (doc 06) = `trace_id` trong OpenTelemetry. Không tạo hai ID riêng. Mọi span trong một Run mang cùng `trace_id`.

### 3.2 Propagation path

```
User request
  → API Gateway (inject trace_id = correlation_id)
    → Orchestrator (propagate)
      → Agent Engine (propagate)
        → Model Gateway (propagate — ghi vào provider request header nếu provider hỗ trợ)
        → Tool Execution (propagate)
          → Sandbox Sidecar (propagate)
      → Artifact Service (propagate)
      → Event Store (ghi correlation_id vào event)
```

### 3.3 Cross-service context propagation

Dùng W3C `traceparent` header. Mọi HTTP/gRPC call giữa service phải propagate header này.

Với async/event-driven path: `correlation_id` và `causation_id` trong event envelope là mechanism propagation — không dùng header.

### 3.4 Span attributes bắt buộc theo loại span

**Span: AgentInvocation**

| Attribute | Ghi chú |
|---|---|
| `agent.id` | agent definition ID |
| `agent.model_id` | model được dùng |
| `agent.prompt_tokens` | sau khi invocation hoàn thành |
| `agent.completion_tokens` | sau khi invocation hoàn thành |
| `agent.cost_usd` | sau khi invocation hoàn thành |
| `agent.tool_call_count` | số lượng tool call |
| `agent.status` | kết quả cuối |

**Span: Sandbox session**

| Attribute | Ghi chú |
|---|---|
| `sandbox.id` | |
| `sandbox.class` | |
| `sandbox.termination_reason` | sau khi terminated |
| `sandbox.policy_violation` | `true` nếu có violation |

**Span: Artifact write**

| Attribute | Ghi chú |
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
| **Critical** | Orchestrator, Auth, Event Store, Model Gateway | 99.9% | 10 giây |
| **Important** | Agent Engine, Artifact Service, Sandbox Manager | 99.5% | 15 giây |
| **Supporting** | Observability stack, Audit Log, Notification | 99.0% | 30 giây |

### 4.2 Health check dimensions

Mỗi service phải báo cáo 4 dimensions:

| Dimension | Ý nghĩa | Endpoint |
|---|---|---|
| `liveness` | Service còn sống không | `GET /healthz/live` |
| `readiness` | Service sẵn sàng nhận traffic không | `GET /healthz/ready` |
| `dependency` | Các dependency của service có OK không | `GET /healthz/deps` |
| `saturation` | Queue depth, connection pool, memory pressure | Metrics |

### 4.3 SSE stream health

SSE stream (real-time push sang UI) có health check riêng vì nó là long-lived connection:

- `sse.active_connections`: số connection đang active.
- `sse.reconnect_rate`: tần suất client reconnect (indicator của instability).
- `sse.message_lag_ms`: độ trễ từ event phát đến client nhận.

SLO: `sse.message_lag_ms` < 500ms cho 95th percentile.

### 4.4 Model Gateway health

Model Gateway không chỉ health check nội bộ mà còn phải monitor external provider:

- `model_gateway.provider_latency_ms` per provider.
- `model_gateway.provider_error_rate` per provider.
- `model_gateway.provider_rate_limit_remaining` per provider.
- `model_gateway.fallback_activated_total`: số lần failover sang provider backup.

---

## 5. Alert Model

### 5.1 Alert severity levels

| Severity | Ý nghĩa | Response SLA | Thông báo |
|---|---|---|---|
| `P0 — Critical` | Hệ thống không hoạt động, dữ liệu có nguy cơ mất | 5 phút | PagerDuty + Slack |
| `P1 — High` | Chức năng quan trọng bị ảnh hưởng, đang degraded | 30 phút | Slack + Email |
| `P2 — Medium` | Vấn đề ảnh hưởng tới một phần user, có workaround | 4 giờ | Slack |
| `P3 — Low` | Anomaly, warning, cần theo dõi | 24 giờ | Dashboard only |

### 5.2 Alert groups

**Group 1: Operational alerts (cho Operator)**

| Alert | Severity | Trigger condition |
|---|---|---|
| `orchestrator_down` | P0 | Orchestrator không pass readiness check > 30 giây |
| `event_store_write_failure` | P0 | Event store write error rate > 1% trong 1 phút |
| `model_gateway_all_providers_down` | P0 | Tất cả provider có error rate > 50% |
| `sandbox_manager_capacity_exhausted` | P1 | Sandbox queue depth > threshold |
| `artifact_service_write_lag` | P1 | Artifact write duration p99 > 30 giây |
| `sse_message_lag_high` | P1 | `sse.message_lag_ms` p95 > 500ms |
| `audit_write_failure` | P1 | Audit log write failure (per doc 09 — fail-safe alert) |
| `model_gateway_provider_degraded` | P2 | Một provider có error rate > 10% |
| `run_queue_depth_growing` | P2 | Run queue depth tăng liên tục > 5 phút |

**Group 2: Security & lineage alerts (cho Security/Admin)**

| Alert | Severity | Trigger condition |
|---|---|---|
| `sandbox_policy_violation` | P1 | Bất kỳ `security.violation` event nào |
| `taint_propagation_cascade` | P1 | Artifact taint propagation ảnh hưởng > 5 artifact trong 1 phút |
| `download_blocked_tainted_artifact` | P2 | `artifact:download` bị deny vì taint — theo dõi pattern |
| `incomplete_provenance_artifact` | P2 | Artifact chuyển `failed` với `failure_reason: incomplete_provenance` |
| `lineage_cycle_rejected` | P2 | Artifact service reject lineage edge vì cycle |
| `agent_escalation_attempt` | P1 | Agent cố nâng quyền qua prompt/tool call |
| `permission_violation_burst` | P1 | > 10 `permission.violation` events trong 5 phút từ cùng `workspace_id` |
| `artifact_ready_without_events` | P2 | Artifact `ready` mà không có `artifact.writing` event trước đó |

**Group 3: Artifact lineage alerts (từ doc 10) — group riêng**

| Alert | Severity | Trigger |
|---|---|---|
| `artifact_tainted_propagation` | P1 | Taint lan sang artifact trong lineage chain |
| `artifact_incomplete_provenance` | P2 | Provenance tuple thiếu field bắt buộc |
| `artifact_lineage_cycle` | P2 | Cycle bị phát hiện khi ghi edge |
| `artifact_download_blocked_taint` | P2 | Download attempt bị block vì taint |
| `artifact_ready_without_expected_events` | P2 | Artifact `ready` không có đủ event chain |

### 5.3 Silence policy

- Alert bị silence phải có: owner, reason, và expiry time.
- Alert P0 không được silence quá 1 giờ mà không có incident record.
- Silence không được tự gia hạn — mỗi lần phải manual confirm.

### 5.4 Alert không được fire trong dry-run / replay mode

Khi `is_replay: true` (từ doc 06), alert engine phải suppress mọi alert phát sinh từ event đó — trừ alert security.

---

## 6. Investigation Surfaces

### 6.1 Task Timeline

**Trả lời:** "Task này đã diễn ra như thế nào?"

**Phải hiển thị:**
- Trục thời gian chronological từ `task.submitted` đến terminal state.
- Mọi Run trong Task với trạng thái, thời lượng.
- Mọi approval gate: ai yêu cầu, ai quyết định, bao lâu.
- Mọi error và cancellation với reason.
- Link trực tiếp sang Run timeline.

**Audience:** User (task owner), Developer, Operator.

### 6.2 Run Timeline

**Trả lời:** "Run này đã thực thi thế nào, từng bước một?"

**Phải hiển thị:**
- Waterfall view của các Step (có thể song song).
- Với mỗi Step: trạng thái, thời lượng, input/output snapshot hash.
- AgentInvocation detail: model, tokens, cost, tool calls sequence.
- Sandbox session: class, duration, violations (nếu có).
- Artifact được tạo ra trong Run này với trạng thái và taint status.
- Error detail nếu Step/AgentInvocation fail.
- Distributed trace span (link ra tracing backend).

**Audience:** Developer, Operator.

### 6.3 Sandbox Session View

**Trả lời:** "Sandbox đã làm gì trong session này?"

**Phải hiển thị:**
- Thời gian sống của Sandbox.
- Sequence of commands/tool calls thực thi.
- Policy violations (nếu có): loại violation, thời điểm, action bị block.
- Network egress attempts: domain, allow/deny, timestamp.
- `termination_reason`.
- Link sang AgentInvocation tương ứng.

**Audience:** Developer, Security/Admin.

**Ghi chú:** View này không hiển thị nội dung raw của reasoning hay message — chỉ metadata và actions.

### 6.4 Artifact Lineage View

**Trả lời:** "Artifact này đến từ đâu và có đáng tin không?"

**Phải hiển thị:**
- DAG visualization của lineage từ root đến artifact hiện tại.
- Với mỗi artifact trong DAG: state, taint status, root type, created_at.
- Provenance tuple completeness check (đủ 5 thành phần không).
- Taint propagation path nếu artifact đang tainted: artifact cha nào gây ra.
- Run/Step/AgentInvocation/Tool/Model liên quan đến từng node trong DAG.
- Download history (ai đã download, khi nào).

**SLO:** Toàn bộ lineage view phải load trong < 2 giây từ `artifact_id`.

**Audience:** Security/Admin, Developer, Auditor.

### 6.5 Taint Investigation View

**Trả lời:** "Artifact này bị taint vì sao, và ảnh hưởng đến artifact nào khác?"

**Phải hiển thị:**
- Taint origin: nguồn gốc taint (security violation / manual / propagation / model anomaly).
- Propagation path: artifact nào đã nhận taint từ artifact này.
- Downstream impact: tất cả artifact con/cháu bị ảnh hưởng.
- Blocked actions: download attempts bị chặn do taint này.
- Untaint history nếu đã từng được untaint và re-tainted.
- Link sang security violation event (nếu nguồn là violation).

**Audience:** Security/Admin.

### 6.6 Approval Audit View

**Trả lời:** "Ai đã approve/reject cái gì, khi nào, và theo ngữ cảnh nào?"

**Phải hiển thị:**
- Toàn bộ approval request trong workspace với filter theo Task/Run/Step/approver.
- Với mỗi approval: target, requester, approver role required, prompt hiển thị cho approver.
- Decision: người quyết định, thời gian quyết định, reason (nếu reject).
- Timeout events.
- Link sang Task/Run/Step context.
- Export sang CSV/JSON cho compliance audit.

**Audience:** Admin, Auditor.

---

## 7. Observability Invariants

Các nguyên tắc sau không được vi phạm bởi bất kỳ implementation hay optimization nào:

**O1 — Observability không được expose secret hay raw user content.**  
Spans, logs, metrics, và investigation surfaces không được chứa secret value, provider key, hay nội dung raw message của user/agent.

**O2 — Artifact lineage phải queryable từ artifact_id trong < 2 giây.**  
Đây là SLO cứng. Nếu lineage graph quá lớn, Artifact service phải maintain materialized ancestors/descendants.

**O3 — Audit records không được bị omit kể cả khi observability stack degraded.**  
Audit write failure → fail-safe behavior theo doc 09 (mục 9.3). Observability stack degraded không được tắt audit trail.

**O4 — Alert không được fire trong replay mode.**  
`is_replay: true` events phải được filtered trước khi vào alert engine. Ngoại lệ duy nhất: security alerts vẫn fire nếu replay phát hiện violation mới.

**O5 — Trace ID = Correlation ID — không được tạo hai ID riêng.**  
Nếu tạo hai ID, trace sẽ không correlate được với event history.

**O6 — Execution trace và provenance trace không được nhập một.**  
Hai view này serve mục đích khác nhau và phải có UI surface riêng.

---

## 8. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Technology cụ thể (Prometheus, Grafana, Jaeger, Loki, v.v.) | Phụ thuộc deployment mode — local vs cloud vs hybrid |
| Sampling rate cụ thể và adaptive sampling logic | Cần tuning thực tế, phụ thuộc workload |
| PII/content redaction pipeline trong logs | Phức tạp theo jurisdiction và deployment, cần riêng |
| Multi-tenant metrics isolation (workspace A không thấy metrics của workspace B) | Phụ thuộc deployment topology và tenant model |
| SLO error budget và burn rate alerting | Cần baseline data từ vận hành thực tế |
| Dashboard layout cụ thể | Không thuộc architecture layer — thuộc UX layer |

---

## 9. Bước tiếp theo

Tài liệu tiếp theo là **12 — Failure & Recovery Model**: khóa cách hệ thống xử lý failure tại từng layer — sandbox fail, model timeout, event duplicate, artifact write partial, subtask fail cascade, và retry semantics không gây side effect lặp. Observability model (doc 11) là nền để failure recovery có thể được observe và verify từ ngoài vào.
