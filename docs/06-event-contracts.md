# 06 — Event Contracts

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 04 Core Domain Model, 05 State Machines  
**Mục tiêu:** Khóa toàn bộ event model — envelope chuẩn, ordering guarantees, idempotency, retry semantics, retention/replay policy, và mapping đầy đủ từ state transition sang event bắt buộc.

---

## 1. Nguyên tắc chung của event model

### 1.1 Event là sự kiện đã xảy ra — không phải lời nhắc nội bộ

Mọi event trong hệ thống này là **fact** — phản ánh điều đã xảy ra trong quá khứ, không phải ý định hay yêu cầu. Điều này có nghĩa:

- Event không thể bị "hủy" sau khi phát ra.
- Consumer không được từ chối một fact event vì "không muốn xử lý" — nó chỉ được idempotently ignore nếu đã xử lý rồi.
- Tên event luôn ở **past tense**: `task.completed`, `sandbox.terminated`, không phải `task.complete` hay `sandbox.terminate`.

### 1.2 Tách biệt fact event và command-like event

Hệ thống sử dụng hai loại event với ngữ nghĩa khác nhau. Không được trộn lẫn:

| Loại | Ngữ nghĩa | Ví dụ | Ai phát |
|---|---|---|---|
| **Fact event** | Điều đã xảy ra, không thể đảo ngược | `sandbox.terminated`, `artifact.ready` | Service chủ sở hữu entity |
| **Command-like event** | Yêu cầu một service thực hiện hành động | `sandbox.terminate_requested` | Orchestrator |

Command-like event chỉ tồn tại trong **cascade shutdown flow** (Task cancel → Run cancel → ... → Sandbox terminate). Tất cả các trường hợp còn lại chỉ dùng fact event.

Command-like event phải được đặt tên với suffix `_requested` để phân biệt tuyệt đối. Không có ngoại lệ.

### 1.3 Event là nguồn chân lý về lịch sử

Event store là append-only. Không có entity nào được thay đổi nội dung event sau khi ghi. Nếu một event được ghi sai, cách xử lý là ghi thêm một **correction event** — không sửa event cũ.

### 1.4 Không có global ordering — chỉ có scoped ordering

Hệ thống **không cam kết** total ordering across toàn bộ event stream. Ordering chỉ được đảm bảo trong từng scope có ý nghĩa nghiệp vụ (xem mục 4).

---

## 2. Event Envelope chuẩn

Mọi event — không phân biệt aggregate, loại, hay context — đều phải tuân theo envelope sau. Không service nào được tự thêm field vào envelope. Field bổ sung chỉ được đặt trong `payload`.

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

### 2.1 Quy tắc điền các ID context

- Điền tất cả ID context có liên quan đến event. Ví dụ: `sandbox.terminated` phải điền `workspace_id`, `task_id`, `run_id`, `step_id`, `agent_invocation_id`, `sandbox_id`.
- ID nào không liên quan thì để `null` — không bỏ field.
- `workspace_id` **luôn bắt buộc** — không event nào được thiếu.

### 2.2 `event_type` naming convention

Format: `<aggregate>.<past_tense_verb>`

Aggregate hợp lệ: `task`, `run`, `step`, `agent_invocation`, `sandbox`, `artifact`, `approval`

Ví dụ hợp lệ: `task.completed`, `sandbox.terminated`, `artifact.ready`  
Ví dụ không hợp lệ: `taskCompleted`, `sandbox_terminate`, `artifact-ready`

### 2.3 `schema_version`

Mỗi `event_type` có `schema_version` riêng. Khi payload schema thay đổi không backward-compatible, phải tăng version và duy trì consumer support cho version cũ trong ít nhất **2 release cycle**.

---

## 3. Correlation / Causation Chain

### 3.1 `correlation_id`

Gắn kết tất cả event thuộc cùng một **execution context**. Trong hệ này, mỗi `run_id` sinh ra một `correlation_id` duy nhất khi Run được tạo. Toàn bộ event trong một Run — bao gồm Step, AgentInvocation, Sandbox, Artifact — đều mang cùng `correlation_id`.

**Quy tắc:**
- `correlation_id` của một Run = UUID được tạo khi `run.queued` event được phát.
- Mọi event phát sinh trong Run đó đều phải copy `correlation_id` này.
- Khi Task spawn nhiều Run, mỗi Run có `correlation_id` riêng.

### 3.2 `causation_id`

Chỉ ra event nào trực tiếp gây ra event hiện tại. Dùng để trace chuỗi nhân quả.

**Ví dụ chuỗi cancel cascade:**

```
task.cancelled          (causation_id: null — người dùng trigger)
  └── run.cancelled     (causation_id: task.cancelled.event_id)
        └── step.cancelled  (causation_id: run.cancelled.event_id)
              └── agent_invocation.interrupted  (causation_id: step.cancelled.event_id)
                    └── sandbox.terminate_requested  (causation_id: agent_invocation.interrupted.event_id)
                          └── sandbox.terminating    (causation_id: sandbox.terminate_requested.event_id)
                                └── sandbox.terminated  (causation_id: sandbox.terminating.event_id)
```

**Quy tắc:**
- Nếu event được phát do một event khác, `causation_id` = `event_id` của event nguyên nhân.
- Nếu event được phát do hành động trực tiếp của actor (user, scheduler), `causation_id` = `null`.
- `causation_id` không bao giờ trỏ đến event thuộc một `correlation_id` khác — không có cross-run causation.

---

## 4. Ordering Guarantees và Non-guarantees

### 4.1 Ordering được đảm bảo (within-scope)

| Scope | Ordering đảm bảo | Cơ chế |
|---|---|---|
| Trong một `run_id` | Các event của Run được ordered theo `occurred_at` | Partition key = `run_id` |
| Trong một `task_id` | Các event của Task được ordered | Partition key = `task_id` |
| Trong một `sandbox_id` | `provisioned → executing → idle → terminated` ordered | Partition key = `sandbox_id` |
| Trong một `artifact_id` | `registered → writing → ready/failed → archived` ordered | Partition key = `artifact_id` |

### 4.2 Ordering KHÔNG được đảm bảo (cross-scope)

- Giữa hai Run khác nhau trong cùng Task.
- Giữa Step A và Step B song song trong cùng Run.
- Giữa event của AgentInvocation và event của Sandbox nếu chúng xảy ra đồng thời.
- Giữa `artifact.ready` của hai Artifact khác nhau.

### 4.3 Cách xử lý cross-scope ordering khi cần

Dùng `causation_id` để suy luận thứ tự nhân quả. Dùng `occurred_at` chỉ để ước lượng, không để enforce ordering logic. Consumer không được assume tổng tự tuyệt đối giữa các scope khác nhau.

---

## 5. Idempotency Rules

### 5.1 Nguyên tắc

Mọi consumer của event **phải** xử lý idempotent theo `event_id`. Nếu cùng một `event_id` xuất hiện hai lần, consumer phải:
- Nhận biết duplicate qua `event_id`.
- Bỏ qua lần thứ hai hoàn toàn — không xử lý lại, không báo lỗi.
- Không emit thêm downstream event do duplicate.

### 5.2 Idempotency store

Consumer phải duy trì idempotency store riêng. Lưu `event_id` đã xử lý trong ít nhất **retention window** (xem mục 7). Không dựa vào event bus để dedup.

### 5.3 Các event đặc biệt cần idempotency nghiêm ngặt

| Event | Lý do |
|---|---|
| `run.completed` | Không được trigger artifact finalization hai lần |
| `artifact.ready` | Không được trigger downstream pipeline hai lần |
| `sandbox.terminated` | Không được trigger cleanup hai lần |
| `approval.approved` | Không được resume Run hai lần |
| `task.cancelled` | Không được cascade cancel hai lần |

---

## 6. Retry Semantics

### 6.1 Delivery guarantee

Toàn bộ hệ thống sử dụng **at-least-once delivery**. Consumer phải idempotent. Exactly-once không được cam kết ở transport layer.

### 6.2 Outbox pattern — bắt buộc cho các publisher sau

Publisher phải dùng **transactional outbox** (ghi event vào DB cùng transaction với state mutation, sau đó relay sang event bus) để đảm bảo event không bị mất nếu service crash giữa chừng:

| Publisher | Lý do bắt buộc outbox |
|---|---|
| Orchestrator phát `run.started` | State mutation và event phải atomic |
| Orchestrator phát `task.completed` | Artifact confirmation và event phải atomic |
| Artifact service phát `artifact.ready` | Checksum write và event phải atomic |
| Orchestrator phát `task.cancelled` | Cascade trigger và event phải atomic |

### 6.3 Retry policy theo event type

| Loại event | Retry | Backoff | Max attempts | On exhaustion |
|---|---|---|---|---|
| Fact events (state transition) | ✓ | Exponential + jitter | 5 | Dead letter queue |
| Command-like events (`*_requested`) | ✓ | Exponential | 3 | Alert + DLQ |
| Approval events | ✓ | Linear | 3 | Alert ops team |
| Artifact events | ✓ | Exponential + jitter | 5 | DLQ + alert |

### 6.4 Events không được replay side effects

Các event terminal sau đây **không được phép gây side effect lặp** dù bị deliver nhiều lần:

- `sandbox.terminated` → không được terminate sandbox đã terminated.
- `artifact.ready` → không được ghi đè artifact đã `ready`.
- `run.completed` → không được chuyển Run đã `completed` sang state khác.
- `approval.approved` / `approval.rejected` → không được xử lý quyết định hai lần.

Consumer phải check trạng thái hiện tại của entity trước khi xử lý event terminal.

---

## 7. Retention và Replay Policy

### 7.1 Hot retention (queryable, low latency)

| Scope | Thời gian giữ | Lý do |
|---|---|---|
| Tất cả event | 30 ngày | Debug, audit, replay ngắn hạn |

### 7.2 Cold retention (archived, higher latency)

| Scope | Thời gian giữ |
|---|---|
| Tất cả event | 1 năm |
| Event của workspace enterprise | Theo contract (tối thiểu 3 năm) |

### 7.3 Replay semantics

- **Cho phép replay:** Trong debug mode, consumer được phép replay event từ một `correlation_id` cụ thể.
- **Không cho phép replay production side effects:** Replay không được trigger thật sandbox, không được ghi artifact thật, không được gửi approval notification thật.
- Replay phải chạy trong **dry-run mode** với flag `is_replay: true` trong envelope context.
- Consumer phải check `is_replay` và skip mọi side effect có thật nếu flag này được bật.

---

## 8. Event Families theo Aggregate

### 8.1 task.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `task.submitted` | User submit task | `task_type`, `input_config_hash` | Fact |
| `task.started` | Orchestrator tạo Run đầu tiên | `first_run_id` | Fact |
| `task.approval_requested` | Orchestrator gặp approval gate | `approval_id`, `approver_role`, `prompt` | Fact |
| `task.approved` | User approve | `approval_id`, `decided_by_id` | Fact |
| `task.rejected` | User reject | `approval_id`, `decided_by_id`, `reason` | Fact |
| `task.completed` | Tất cả Run cần thiết done | `artifact_ids`, `duration_ms` | Fact |
| `task.failed` | Orchestrator xác định không recover | `error_code`, `error_summary`, `failed_run_id` | Fact |
| `task.cancelled` | User hoặc Policy hủy | `cancelled_by_type`, `cancelled_by_id`, `reason` | Fact |
| `task.archived` | Scheduled archival | `archived_at` | Fact |

### 8.2 run.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `run.queued` | Orchestrator tạo Run | `trigger_type`, `run_config_hash` | Fact |
| `run.preparing` | Orchestrator bắt đầu prepare | | Fact |
| `run.started` | Sandbox ready, Step đầu được tạo | `first_step_id` | Fact |
| `run.approval_requested` | Approval gate trong Run | `approval_id`, `approver_role` | Fact |
| `run.approved` | User approve | `approval_id`, `decided_by_id` | Fact |
| `run.completing` | Tất cả Step xong | `artifact_ids_pending_finalization` | Fact |
| `run.completed` | Artifact finalized | `artifact_ids`, `duration_ms`, `total_cost_usd` | Fact |
| `run.failed` | Lỗi không recover | `error_code`, `error_summary`, `failed_step_id` | Fact |
| `run.cancelled` | Cascade từ Task hoặc User | `cancelled_by_type`, `cancelled_by_id` | Fact |
| `run.timed_out` | Vượt timeout | `timeout_limit_ms` | Fact |

### 8.3 step.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `step.started` | Orchestrator bắt đầu Step | `step_type`, `sequence`, `input_snapshot_hash` | Fact |
| `step.approval_requested` | Orchestrator gặp approval gate | `approval_id`, `approver_role`, `prompt` | Fact |
| `step.approved` | User approve | `approval_id`, `decided_by_id` | Fact |
| `step.blocked` | Dependency chưa thỏa mãn | `blocking_reason`, `blocking_step_id` | Fact |
| `step.unblocked` | Dependency được resolve | `resolved_by` | Fact |
| `step.completed` | Step hoàn thành | `output_snapshot_hash`, `duration_ms` | Fact |
| `step.failed` | Lỗi không recover | `error_code`, `error_detail_hash` | Fact |
| `step.skipped` | Condition false | `skip_reason` | Fact |
| `step.cancelled` | Cascade từ Run | | Fact |

### 8.4 agent_invocation.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `agent_invocation.started` | Agent Engine bắt đầu | `agent_id`, `model_id` | Fact |
| `agent_invocation.waiting_human` | Agent hỏi người dùng | `question_summary`, `timeout_at` | Fact |
| `agent_invocation.human_responded` | User cung cấp input | `responded_by_id` | Fact |
| `agent_invocation.waiting_tool` | Tool call được dispatch | `tool_name`, `tool_call_id` | Fact |
| `agent_invocation.tool_result_received` | Tool trả kết quả | `tool_call_id`, `success` | Fact |
| `agent_invocation.completed` | Agent kết thúc thành công | `prompt_tokens`, `completion_tokens`, `total_cost_usd` | Fact |
| `agent_invocation.failed` | Lỗi logic/model | `error_code`, `error_detail` | Fact |
| `agent_invocation.interrupted` | Orchestrator interrupt | `interrupted_by`, `reason` | Fact |
| `agent_invocation.compensating` | Agent Engine bắt đầu rollback | `compensation_reason` | Fact |
| `agent_invocation.compensated` | Rollback hoàn thành | | Fact |

### 8.5 sandbox.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `sandbox.terminate_requested` | Orchestrator yêu cầu terminate | `requested_by`, `reason` | **Command-like** |
| `sandbox.provisioned` | Execution layer tạo sandbox xong | `sandbox_type`, `resource_limits_hash` | Fact |
| `sandbox.executing` | Bắt đầu thực thi lệnh | `tool_call_id` | Fact |
| `sandbox.idle` | Lệnh hoàn thành, chờ lệnh tiếp | `last_tool_call_id` | Fact |
| `sandbox.failed` | Crash, OOM, policy violation | `failure_type`, `policy_violation_detail` | Fact |
| `sandbox.terminating` | Bắt đầu shutdown | `termination_reason` | Fact |
| `sandbox.terminated` | Shutdown hoàn toàn | `terminated_at`, `termination_reason` | Fact |

**Lưu ý:** `sandbox.terminate_requested` là command-like event duy nhất trong toàn bộ sandbox family. Tất cả event còn lại là fact.

### 8.6 artifact.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `artifact.registered` | Artifact service tạo record | `artifact_type`, `run_id`, `step_id` | Fact |
| `artifact.writing` | Bắt đầu ghi vào storage | `storage_ref` | Fact |
| `artifact.ready` | Ghi xong, checksum xác nhận | `checksum`, `size_bytes`, `storage_ref` | Fact |
| `artifact.failed` | Ghi thất bại | `failure_reason`, `partial_data_available` | Fact |
| `artifact.superseded` | Artifact mới trong lineage được tạo | `superseded_by_artifact_id` | Fact |
| `artifact.archived` | Chuyển sang cold storage | `archived_storage_ref` | Fact |

### 8.7 approval.*

| Event type | Trigger | Key payload fields | Fact hay Command-like |
|---|---|---|---|
| `approval.requested` | Orchestrator tạo ApprovalRequest | `approval_id`, `target_type`, `target_id`, `approver_role`, `prompt`, `timeout_at` | Fact |
| `approval.approved` | User approve | `approval_id`, `decided_by_id`, `decided_at` | Fact |
| `approval.rejected` | User reject | `approval_id`, `decided_by_id`, `reason` | Fact |
| `approval.timed_out` | Timeout không có quyết định | `approval_id`, `timed_out_at` | Fact |

---

## 9. Bất hợp lệ — Điều bị cấm tuyệt đối

### 9.1 Về event integrity

- Sửa nội dung event sau khi đã ghi vào event store.
- Xóa event từ event store (kể cả event sai — chỉ được ghi correction event).
- Event không có `workspace_id`.
- Event không có `event_id` duy nhất toàn cục.
- Event `occurred_at` là timestamp tương lai.

### 9.2 Về naming và semantics

- Dùng tên event không phải past tense (trừ suffix `_requested` cho command-like).
- Đặt logic nghiệp vụ vào `event_type` thay vì `payload`.
- Một event mang ngữ nghĩa của cả fact lẫn command.
- Cross-run `causation_id` — `causation_id` không được trỏ sang event của `correlation_id` khác.

### 9.3 Về ordering và delivery

- Consumer assume global ordering giữa các aggregate khác nhau.
- Consumer xử lý event mà không check idempotency store trước.
- Terminal event (`run.completed`, `artifact.ready`, `sandbox.terminated`) gây side effect khi bị deliver lần hai.
- Replay event với `is_replay: true` trigger real sandbox, real artifact write, hoặc real approval notification.

### 9.4 Về publisher

- Service không phải owner của aggregate phát event của aggregate đó. Ví dụ: Agent Engine không được phát `artifact.*` event — đó là việc của Artifact service.
- Publisher không dùng outbox cho các event bắt buộc (xem mục 6.2) mà gọi event bus trực tiếp sau DB write.

---

## 10. Mapping từ State Transition (doc 05) sang Event bắt buộc

### 10.1 Task

| State transition | Event bắt buộc |
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

| State transition | Event bắt buộc |
|---|---|
| Run được tạo | `run.queued` |
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

| State transition | Event bắt buộc |
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

| State transition | Event bắt buộc |
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

| State transition | Event bắt buộc |
|---|---|
| `provisioning → ready` | `sandbox.provisioned` |
| `ready/idle → executing` | `sandbox.executing` |
| `executing → idle` | `sandbox.idle` |
| `* → failed` | `sandbox.failed` |
| Nhận `sandbox.terminate_requested` | `sandbox.terminating` |
| `terminating → terminated` | `sandbox.terminated` |

### 10.6 Artifact

| State transition | Event bắt buộc |
|---|---|
| `pending` được tạo | `artifact.registered` |
| `pending → writing` | `artifact.writing` |
| `writing → ready` | `artifact.ready` |
| `* → failed` | `artifact.failed` |
| `ready → superseded` | `artifact.superseded` |
| `* → archived` | `artifact.archived` |

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Schema chi tiết của từng `payload` | Phụ thuộc vào API Contracts (doc 07) — payload phải nhất quán với API response shape |
| Dead letter queue handling và alert routing | Phụ thuộc vào Observability model (doc 11) |
| Event bus technology cụ thể (Kafka, NATS, Postgres LISTEN/NOTIFY) | Phụ thuộc vào deployment topology (doc 13) |
| `is_replay` propagation mechanism | Phụ thuộc vào implementation của replay infrastructure |
| Correction event convention chi tiết | Đủ để khóa sau khi có vài trường hợp thực tế cần correct |

---

## 12. Bước tiếp theo

Tài liệu tiếp theo là **07 — API Contracts**: khóa surface area của từng service — endpoint, request/response shape, auth, versioning, và mapping từ event model sang API semantics. Payload schema của event (mục 11) sẽ được khóa song song với doc 07.
