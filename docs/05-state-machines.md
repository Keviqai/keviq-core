# 05 — State Machines

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 04 Core Domain Model  
**Mục tiêu:** Khóa lifecycle vận hành của toàn bộ entity động trong hệ thống — làm nền cho Event Contracts (06), API Contracts (07), và observability/recovery logic.

Mỗi state machine được viết theo khung cố định:
1. Mục đích của lifecycle
2. Danh sách trạng thái hợp lệ
3. Chuyển trạng thái hợp lệ
4. Tác nhân được phép chuyển trạng thái
5. Side effects bắt buộc
6. Events phải phát ra
7. Điều gì là bất hợp lệ và phải bị từ chối

---

## 1. Task Lifecycle

### 1.1 Mục đích

Task là khai báo ý định nghiệp vụ của người dùng. Lifecycle của Task phản ánh vòng đời của ý định đó — từ khi được tạo đến khi có kết quả hoặc bị hủy bỏ. Task không tự thực thi — nó spawn Run để thực thi.

### 1.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `draft` | Task đang được soạn thảo, chưa sẵn sàng thực thi |
| `pending` | Task đã được submit, chờ orchestrator xếp lịch |
| `running` | Có ít nhất một Run đang active |
| `waiting_approval` | Task bị tạm dừng chờ human approval ở cấp Task |
| `completed` | Tất cả Run cần thiết đã hoàn thành và có artifact |
| `failed` | Task kết thúc do lỗi không thể recover |
| `cancelled` | Task bị hủy bởi user hoặc policy |
| `archived` | Task đã completed/cancelled và được đưa vào lưu trữ |

### 1.3 Chuyển trạng thái hợp lệ

```
draft ──────────────────────────► pending
pending ────────────────────────► running
pending ────────────────────────► cancelled
running ────────────────────────► waiting_approval
running ────────────────────────► completed
running ────────────────────────► failed
running ────────────────────────► cancelled
waiting_approval ───────────────► running          (approved)
waiting_approval ───────────────► cancelled         (rejected hoặc timeout)
completed ──────────────────────► archived
failed ─────────────────────────► pending           (human re-submit)
failed ─────────────────────────► archived
cancelled ──────────────────────► archived
```

**Không có chuyển trạng thái ngược từ `completed` → `running`.** Nếu cần chạy lại, tạo Task mới hoặc tạo Run mới trên Task cũ.

### 1.4 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân được phép |
|---|---|
| `draft → pending` | User (submit) |
| `pending → running` | Orchestrator |
| `pending → cancelled` | User, Policy enforcement |
| `running → waiting_approval` | Orchestrator (khi gặp approval gate) |
| `running → completed/failed` | Orchestrator |
| `running → cancelled` | User, Policy enforcement |
| `waiting_approval → running` | User (approver), Policy (auto-approve) |
| `waiting_approval → cancelled` | User (reject), Policy (timeout) |
| `failed → pending` | User (re-submit) |
| `*/→ archived` | System (scheduled archival) |

### 1.5 Side effects bắt buộc

- `pending → running`: Orchestrator tạo Run đầu tiên.
- `running → cancelled`: **Tất cả Run con đang active phải bị terminate.** Không để Run tiếp tục sau khi Task bị cancel.
- `running → failed`: Orchestrator ghi error summary vào Task. Các Run con đang active bị terminate.
- `completed`: Orchestrator xác nhận ít nhất một Artifact `ready` tồn tại cho Task này.
- `failed → pending`: Orchestrator tạo Run mới — không resume Run cũ.

### 1.6 Events phải phát ra

| Sự kiện | Khi nào |
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

### 1.7 Bất hợp lệ — phải bị từ chối

- Chuyển `completed → running` hoặc `completed → pending` — không được phép.
- Chuyển `cancelled → running` — không được phép. Phải tạo Task mới.
- Bất kỳ layer nào khác ngoài Orchestrator chuyển trạng thái Task (trừ User cancel và User re-submit).
- Task bị `completed` khi chưa có Artifact `ready` nào.
- Task `waiting_approval` tự chuyển sang `running` không qua actor.

---

## 2. Run Lifecycle

### 2.1 Mục đích

Run là một lần thực thi cụ thể của Task. Nó ghi lại toàn bộ quá trình từ lúc bắt đầu đến khi có kết quả. Nhiều Run có thể tồn tại trên cùng một Task (retry, re-run thủ công, experimental). Run không được resume — nếu fail, tạo Run mới.

### 2.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `queued` | Run đã được tạo, chờ tài nguyên |
| `preparing` | Orchestrator đang chuẩn bị sandbox, load config, bind secrets |
| `running` | Đang thực thi các Step |
| `waiting_approval` | Bị tạm dừng chờ approval ở cấp Run/Step |
| `completing` | Tất cả Step xong, đang finalize artifact |
| `completed` | Run kết thúc thành công với artifact |
| `failed` | Run kết thúc do lỗi |
| `cancelled` | Run bị hủy |
| `timed_out` | Run vượt quá thời gian giới hạn |

### 2.3 Chuyển trạng thái hợp lệ

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

**Run không có `resume`.** Khi fail hoặc cancel, Run kết thúc vĩnh viễn. Orchestrator tạo Run mới nếu cần retry.

### 2.4 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân |
|---|---|
| `queued → preparing` | Orchestrator |
| `queued/preparing/running → cancelled` | User, Policy, Task cancellation cascade |
| `preparing → running` | Orchestrator |
| `running → waiting_approval` | Orchestrator (approval gate trong Step) |
| `running → completing/failed/timed_out` | Orchestrator |
| `waiting_approval → running` | User (approver), Policy (auto-approve) |
| `waiting_approval → cancelled` | User (reject), Policy (timeout) |
| `completing → completed/failed` | Orchestrator (sau artifact finalization) |

### 2.5 Side effects bắt buộc

- `queued → preparing`: Lock `run_config` — không được phép thay đổi sau bước này.
- `preparing → running`: Orchestrator khởi tạo Step đầu tiên.
- `running → cancelled` (do Task cancel cascade): Tất cả Step và AgentInvocation đang active phải terminate.
- `running → timed_out`: Tương đương cancel — terminate toàn bộ Step, AgentInvocation, Sandbox con.
- `completing → completed`: Artifact service xác nhận tất cả Artifact có `checksum` hợp lệ.
- `completing → failed`: Partial artifacts (nếu có) được giữ lại với status `failed`, không xóa.

### 2.6 Events phải phát ra

| Sự kiện | Khi nào |
|---|---|
| `run.queued` | Run được tạo |
| `run.preparing` | `queued → preparing` |
| `run.started` | `preparing → running` |
| `run.approval_requested` | `running → waiting_approval` |
| `run.approved` | `waiting_approval → running` |
| `run.completing` | `running → completing` |
| `run.completed` | `completing → completed` |
| `run.failed` | `* → failed` |
| `run.cancelled` | `* → cancelled` |
| `run.timed_out` | `running → timed_out` |

### 2.7 Bất hợp lệ — phải bị từ chối

- Resume Run đã `failed`, `cancelled`, `timed_out` — không được phép.
- Thay đổi `run_config` sau khi Run rời `queued`.
- `completed` khi còn Step chưa kết thúc.
- `completed` khi Artifact chưa được finalize.
- Bất kỳ Step nào tiếp tục chạy sau khi Run chuyển sang `cancelled`.

---

## 3. Step Lifecycle

### 3.1 Mục đích

Step là đơn vị trace nhỏ nhất trong Run. Mọi timeline, observability, và recovery đều bám vào Step. Step không tự quyết định logic — nó là đơn vị ghi nhận "đã làm gì, input là gì, output là gì, trạng thái là gì".

### 3.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `pending` | Step đã được tạo, chờ Step trước hoàn thành |
| `running` | Step đang thực thi |
| `waiting_approval` | Step bị dừng chờ human approval trước khi tiếp tục |
| `blocked` | Step không thể tiếp tục do dependency chưa thỏa mãn (không phải approval) |
| `completed` | Step hoàn thành thành công |
| `failed` | Step kết thúc với lỗi |
| `skipped` | Step bị bỏ qua do điều kiện logic |
| `cancelled` | Step bị hủy do Run bị hủy |

**Phân biệt `waiting_approval` và `blocked`:**
- `waiting_approval`: Step có thể tiếp tục ngay khi có human approval. Hệ thống đang chờ người.
- `blocked`: Step không thể tiếp tục vì một điều kiện kỹ thuật chưa thỏa mãn (VD: Step phụ thuộc chưa xong, tài nguyên chưa sẵn sàng). Hệ thống đang chờ hệ thống.

### 3.3 Chuyển trạng thái hợp lệ

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

### 3.4 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân |
|---|---|
| `pending → running/skipped` | Orchestrator |
| `running → waiting_approval` | Orchestrator (khi gặp approval gate) |
| `running → blocked` | Orchestrator (dependency check) |
| `running → completed/failed` | Orchestrator |
| `waiting_approval → running` | User (approver) |
| `waiting_approval → cancelled` | User (reject) |
| `blocked → running` | Orchestrator (dependency watcher) |
| `blocked → failed` | Orchestrator (dependency resolution timeout) |
| `* → cancelled` | Run cancellation cascade |

### 3.5 Side effects bắt buộc

- `pending → running`: Ghi `started_at`, ghi `input_snapshot`.
- `running → completed`: Ghi `completed_at`, ghi `output_snapshot`.
- `running → failed`: Ghi `error_detail`.
- `running → waiting_approval`: Orchestrator phát approval request, ghi thông tin approver cần.
- `blocked → failed`: Orchestrator ghi lý do dependency fail vào `error_detail`.
- `* → cancelled` (cascade từ Run): Step không được emit thêm bất kỳ side effect nào sau khi cancelled.

### 3.6 Events phải phát ra

| Sự kiện | Khi nào |
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

### 3.7 Bất hợp lệ — phải bị từ chối

- Step chuyển trạng thái mà không có Run đang `running` hoặc `waiting_approval`.
- `completed` khi `output_snapshot` chưa được ghi.
- `waiting_approval` và `blocked` cùng tồn tại trên một Step.
- Step tiếp tục sau khi Run cha đã `cancelled`.

---

## 4. AgentInvocation Lifecycle

### 4.1 Mục đích

AgentInvocation là một lần gọi vào agent runtime — bao gồm toàn bộ reasoning loop, tool calls, và multi-turn. Lifecycle của nó phải mô tả được: invocation thành công, thất bại, bị gián đoạn, đang chờ human, và đã được compensate khi fail.

### 4.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `initializing` | Agent runtime đang được khởi tạo, context đang được load |
| `running` | Agent đang trong vòng reasoning/tool-use loop |
| `waiting_human` | Agent đã phát câu hỏi/yêu cầu input từ người dùng |
| `waiting_tool` | Agent đang chờ kết quả tool call hoàn thành |
| `completed` | Agent kết thúc thành công, có output |
| `failed` | Agent kết thúc với lỗi không recover được |
| `interrupted` | Invocation bị dừng từ bên ngoài (Run cancel, timeout, policy violation) |
| `compensating` | Đang thực hiện rollback/cleanup sau fail (nếu có compensation logic) |
| `compensated` | Compensation hoàn thành |

### 4.3 Chuyển trạng thái hợp lệ

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
failed ─────────────────────────► compensating     (nếu có compensation handler)
failed ─────────────────────────► (terminal)       (nếu không có compensation)
interrupted ────────────────────► compensating     (nếu cần cleanup)
interrupted ────────────────────► (terminal)
compensating ───────────────────► compensated
compensating ───────────────────► failed           (compensation cũng fail)
```

### 4.4 Quan hệ với Sandbox

- Khi AgentInvocation → `interrupted`: Sandbox phải được terminate. Sandbox không tự chuyển sang `terminated` — nó nhận tín hiệu terminate từ Execution layer khi AgentInvocation bị interrupted.
- Khi Sandbox bị terminate bất thường từ bên ngoài: AgentInvocation phải chuyển sang `interrupted`, không phải `failed`. `failed` chỉ dành cho lỗi logic/model.
- Hai lifecycle này **không được nhập nhằng**: Sandbox có thể terminated trong khi AgentInvocation đang `compensating`.

### 4.5 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân |
|---|---|
| `initializing → running` | Agent Engine |
| `running → waiting_human` | Agent Engine (agent tự quyết định hỏi người dùng) |
| `running → waiting_tool` | Agent Engine (tool call được dispatch) |
| `running → completed/failed` | Agent Engine |
| `waiting_human → running` | User (qua UI/API), với input được ghi vào Step |
| `waiting_tool → running/failed` | Tool/Execution layer (trả kết quả) |
| `* → interrupted` | Orchestrator (cascade từ Run/Step cancel hoặc policy) |
| `failed/interrupted → compensating` | Agent Engine (nếu có compensation handler) |
| `compensating → compensated/failed` | Agent Engine |

### 4.6 Side effects bắt buộc

- `initializing → running`: Ghi `started_at`, snapshot `input_messages`.
- `running → waiting_human`: Orchestrator thông báo UI có câu hỏi chờ người dùng.
- `completed`: Ghi `output_messages`, `tool_calls`, `prompt_tokens`, `completion_tokens`, `total_cost_usd`.
- `* → interrupted`: Gửi terminate signal tới Sandbox tương ứng.
- `compensating → compensated`: Ghi cleanup result vào Step `output_snapshot`.

### 4.7 Events phải phát ra

| Sự kiện | Khi nào |
|---|---|
| `agent_invocation.started` | `initializing → running` |
| `agent_invocation.waiting_human` | `running → waiting_human` |
| `agent_invocation.waiting_tool` | `running → waiting_tool` |
| `agent_invocation.completed` | `* → completed` |
| `agent_invocation.failed` | `* → failed` |
| `agent_invocation.interrupted` | `* → interrupted` |
| `agent_invocation.compensating` | `* → compensating` |
| `agent_invocation.compensated` | `compensating → compensated` |

### 4.8 Bất hợp lệ — phải bị từ chối

- `completed` khi `output_messages` hoặc `total_cost_usd` chưa được ghi.
- Agent tự chuyển trạng thái sang `interrupted` — chỉ Orchestrator được interrupt.
- AgentInvocation tiếp tục `running` sau khi Step cha đã `cancelled`.
- Tạo Artifact trực tiếp từ Agent Engine — phải qua Artifact service.

---

## 5. Sandbox Lifecycle

### 5.1 Mục đích

Sandbox là môi trường thực thi ephemeral. Lifecycle của Sandbox hoàn toàn độc lập với reasoning của Agent — nó chỉ phản ánh trạng thái của môi trường chạy, không phải logic của công việc.

### 5.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `provisioning` | Sandbox đang được tạo ra (container/VM spin up) |
| `ready` | Sandbox đã sẵn sàng nhận lệnh thực thi |
| `executing` | Sandbox đang thực thi lệnh |
| `idle` | Sandbox đang chờ lệnh tiếp theo (giữa các tool calls) |
| `terminating` | Sandbox đang được shut down |
| `terminated` | Sandbox đã dừng hoàn toàn |
| `failed` | Sandbox gặp lỗi không thể recover (crash, OOM, policy violation) |

### 5.3 Chuyển trạng thái hợp lệ

```
provisioning ───────────────────► ready
provisioning ───────────────────► failed
ready ──────────────────────────► executing
ready ──────────────────────────► terminating    (signal từ Orchestrator)
executing ──────────────────────► idle
executing ──────────────────────► failed         (execution error, policy violation)
executing ──────────────────────► terminating    (signal từ Orchestrator)
idle ───────────────────────────► executing
idle ───────────────────────────► terminating
failed ─────────────────────────► terminating    (cleanup)
terminating ────────────────────► terminated
```

### 5.4 Quan hệ với AgentInvocation

- Khi AgentInvocation → `interrupted`: Execution layer gửi terminate signal → Sandbox `terminating → terminated`.
- Khi Sandbox → `failed` bất ngờ: Execution layer thông báo Orchestrator → Orchestrator interrupt AgentInvocation.
- Sandbox không được tự quyết định interrupt AgentInvocation — nó chỉ báo cáo trạng thái.

### 5.5 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân |
|---|---|
| `provisioning → ready/failed` | Execution layer |
| `ready/idle → executing` | Execution layer (nhận tool call từ Agent Engine) |
| `executing → idle` | Execution layer (tool call hoàn thành) |
| `executing/idle/ready → terminating` | Execution layer (nhận terminate signal từ Orchestrator) |
| `failed → terminating` | Execution layer (auto cleanup) |
| `terminating → terminated` | Execution layer |

**UI layer không được gọi Sandbox trực tiếp — đây là invariant bất biến.**

### 5.6 Side effects bắt buộc

- `provisioning → ready`: Ghi `started_at`, apply `policy_snapshot` và `resource_limits`.
- `executing → failed` (policy violation): Ghi vi phạm vào audit log trước khi chuyển `terminating`.
- `terminating → terminated`: Ghi `terminated_at`, `termination_reason`. Toàn bộ data trong sandbox bị xóa — không có persistence sau `terminated`.

### 5.7 Events phải phát ra

| Sự kiện | Khi nào |
|---|---|
| `sandbox.provisioned` | `provisioning → ready` |
| `sandbox.executing` | `ready/idle → executing` |
| `sandbox.idle` | `executing → idle` |
| `sandbox.failed` | `* → failed` |
| `sandbox.terminating` | `* → terminating` |
| `sandbox.terminated` | `terminating → terminated` |

### 5.8 Bất hợp lệ — phải bị từ chối

- Sandbox persist state nội tại sau khi `terminated`.
- Sandbox nhận lệnh trực tiếp từ UI layer.
- Sandbox tiếp tục `executing` sau khi nhận terminate signal.
- `policy_snapshot` bị thay đổi sau khi Sandbox rời `provisioning`.

---

## 6. Artifact Lifecycle

### 6.1 Mục đích

Artifact là output tồn tại lâu dài. Lifecycle của Artifact phải bất biến theo hướng chỉ tiến — không cho phép mutate ngầm sau khi `ready`. Partial data khi fail phải được giữ lại và đánh dấu rõ.

### 6.2 Trạng thái hợp lệ

| Trạng thái | Ý nghĩa |
|---|---|
| `pending` | Artifact đã được đăng ký, chưa có data |
| `writing` | Data đang được ghi vào storage |
| `ready` | Artifact hoàn chỉnh, có checksum, có thể đọc |
| `failed` | Quá trình ghi thất bại — partial data (nếu có) được giữ lại |
| `superseded` | Artifact đã bị thay thế bởi artifact mới hơn trong cùng lineage |
| `archived` | Artifact được chuyển sang cold storage, vẫn có thể đọc |

### 6.3 Chuyển trạng thái hợp lệ

```
pending ─────────────────────────► writing
pending ─────────────────────────► failed         (không thể init storage)
writing ─────────────────────────► ready
writing ─────────────────────────► failed          (write error)
ready ───────────────────────────► superseded      (khi artifact mới trong lineage được tạo)
ready ───────────────────────────► archived
superseded ──────────────────────► archived
failed ──────────────────────────► archived        (giữ partial data, đánh dấu rõ)
```

**Không có chuyển trạng thái ngược.** `ready → writing` là bất hợp lệ tuyệt đối.  
**Không có `deleted`.** Artifact chỉ được `archived`.

### 6.4 Xử lý Artifact failed

- Partial data (nếu có) **phải được giữ lại** — không xóa.
- `checksum` để trống hoặc ghi `null`.
- `artifact_status = failed` với `metadata.failure_reason` ghi rõ nguyên nhân.
- Artifact `failed` vẫn có thể đọc partial data cho mục đích debug.
- Artifact `failed` **không được dùng làm input** cho Step/Run tiếp theo.

### 6.5 Tác nhân được phép chuyển trạng thái

| Chuyển trạng thái | Tác nhân |
|---|---|
| `pending → writing` | Artifact service (sau khi AgentInvocation hoàn thành) |
| `writing → ready` | Artifact service (sau khi checksum xác nhận) |
| `writing/pending → failed` | Artifact service |
| `ready → superseded` | Artifact service (khi artifact mới được tạo trong lineage) |
| `ready/superseded/failed → archived` | System (scheduled archival) |

**AgentInvocation và Agent Engine không được trực tiếp tạo hay ghi Artifact.**

### 6.6 Side effects bắt buộc

- `writing → ready`: Ghi `checksum` (SHA-256), ghi `size_bytes`. Checksum này **bất biến vĩnh viễn**.
- `ready → superseded`: Ghi `superseded_by_artifact_id` vào metadata.
- `* → archived`: Chuyển file sang cold storage tier, cập nhật `storage_ref`.

### 6.7 Events phải phát ra

| Sự kiện | Khi nào |
|---|---|
| `artifact.registered` | `pending` được tạo |
| `artifact.writing` | `pending → writing` |
| `artifact.ready` | `writing → ready` |
| `artifact.failed` | `* → failed` |
| `artifact.superseded` | `ready → superseded` |
| `artifact.archived` | `* → archived` |

### 6.8 Bất hợp lệ — phải bị từ chối

- Mutate nội dung của Artifact `ready` — tuyệt đối không được phép.
- Xóa Artifact `failed` — phải archive, không xóa.
- Dùng Artifact `failed` làm input cho Run/Step.
- `checksum` bị thay đổi sau khi Artifact `ready`.
- Artifact được tạo trực tiếp từ Agent Engine, bỏ qua Artifact service.

---

## 7. Approval Flow

### 7.1 Mục đích

Approval flow là cơ chế tạm dừng vận hành chờ quyết định của con người. Nó có thể đứng ở cấp Task, Run, hoặc Step — và phải không làm lệch lifecycle của entity chứa nó.

### 7.2 Approval đứng ở cấp nào

| Cấp | Khi nào dùng | Tác động |
|---|---|---|
| **Task** | Cần approve toàn bộ chiến lược trước khi bắt đầu bất kỳ Run nào | Task vào `waiting_approval`, không Run nào được tạo |
| **Run** | Cần approve cụ thể một lần thực thi trước khi tiếp tục | Run vào `waiting_approval`, Step đang running bị pause |
| **Step** | Cần approve một hành động cụ thể trước khi Step tiếp tục | Step vào `waiting_approval`, Run vẫn `running` |

**Approval ở cấp Step là phổ biến nhất** — ví dụ: approve trước khi agent thực thi một lệnh destructive.

### 7.3 ApprovalRequest entity (embedded, không phải aggregate)

ApprovalRequest không là entity độc lập — nó được ghi nhận qua Event và Step/Run/Task metadata.

| Field | Type | Mô tả |
|---|---|---|
| `approval_id` | UUID | |
| `target_type` | enum | `task`, `run`, `step` |
| `target_id` | UUID | |
| `requested_by` | enum | `orchestrator`, `policy` |
| `requested_at` | timestamp | |
| `approver_role` | string | Role được phép approve |
| `prompt` | text | Thông tin hiển thị cho approver |
| `timeout_at` | timestamp | Sau mốc này tự động rejected |
| `decision` | enum | `pending`, `approved`, `rejected`, `timed_out` |
| `decided_by_id` | UUID → User | |
| `decided_at` | timestamp | |

### 7.4 Timeout behavior

- Khi `timeout_at` đạt đến mà chưa có quyết định: Approval tự động chuyển sang `timed_out`.
- `timed_out` tương đương `rejected` về mặt lifecycle — entity cha chuyển sang `cancelled`.
- Policy có thể cấu hình `timed_out → auto_approved` thay vì `cancelled` (opt-in).

### 7.5 Events phải phát ra

| Sự kiện | Khi nào |
|---|---|
| `approval.requested` | ApprovalRequest được tạo |
| `approval.approved` | Người dùng approve |
| `approval.rejected` | Người dùng reject |
| `approval.timed_out` | Timeout không có quyết định |

### 7.6 Bất hợp lệ

- Approval tự động được approve mà không có actor (trừ khi Policy cho phép auto-approve rõ ràng).
- Cùng một target có hai ApprovalRequest active đồng thời.
- ApprovalRequest tồn tại sau khi entity cha đã `cancelled` hoặc `completed`.

---

## 8. Tổng hợp: Cascade khi Cancel

Đây là điểm dễ gây không nhất quán nhất — cần khóa rõ:

```
Task cancelled
  └── tất cả Run đang [queued, preparing, running, waiting_approval] → cancelled
        └── tất cả Step đang [pending, running, waiting_approval, blocked] → cancelled
              └── tất cả AgentInvocation đang [initializing, running, waiting_human, waiting_tool] → interrupted
                    └── tất cả Sandbox đang [provisioning, ready, executing, idle] → terminating → terminated
```

**Thứ tự terminate: từ trong ra ngoài** — Sandbox trước, AgentInvocation sau, Step sau, Run sau, Task sau.  
**Không có side effect nào được phép phát ra sau khi entity đã `cancelled`.**

---

## 9. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Retry policy cụ thể (số lần retry, backoff strategy) | Phụ thuộc vào Policy model (doc 09) |
| Compensation logic chi tiết cho AgentInvocation | Phụ thuộc vào từng agent type và tool type |
| Auto-approve condition trong Policy | Phụ thuộc vào Permission model (doc 09) |
| Approval routing (ai nhận notification) | Phụ thuộc vào Member/role model |
| Archival schedule và cold storage policy | Phụ thuộc vào deployment topology (doc 13) |

---

## 10. Bước tiếp theo

Tài liệu tiếp theo là **06 — Event Contracts**: khóa schema chuẩn cho toàn bộ event đã liệt kê trong doc này, bao gồm payload structure, idempotency key, ordering assumptions, retry semantics, và correlation/causation chain.
