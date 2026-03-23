# Architecture Gate Review — Docs 00–12

**Loại tài liệu:** Review, không phải spec  
**Phạm vi:** Docs 00–12 (toàn bộ bộ kiến trúc lõi)  
**Mục đích:** Xác nhận tính nhất quán cross-doc trước khi đi vào 13–17  
**Kết quả mỗi điểm:** PASS / CLARIFY / GAP

---

## 1. Cross-doc Consistency

### 1.1 Entity ownership vs. lifecycle vs. event — PASS

Ownership chain trong doc 04 bám đúng với state machine trong doc 05 và event family trong doc 06:

| Entity | Owner (04) | States (05) | Event family (06) |
|---|---|---|---|
| Task | Orchestrator | ✓ khớp | task.* ✓ |
| Run | Orchestrator | ✓ khớp | run.* ✓ |
| Step | Orchestrator | ✓ khớp | step.* ✓ |
| AgentInvocation | Agent Engine | ✓ khớp | agent_invocation.* ✓ |
| Sandbox | Execution layer | ✓ khớp | sandbox.* ✓ |
| Artifact | Artifact service | ✓ khớp | artifact.* ✓ |

Không phát hiện lệch ownership.

---

### 1.2 Sandbox có thể được tạo lại cho cùng một AgentInvocation — CLARIFY

**Vấn đề:** Doc 12 mục 4.3 nói: *"Tạo Sandbox mới cho cùng AgentInvocation là acceptable nếu failure là infra-level và không có side effects."*

Doc 04 định nghĩa `Sandbox.agent_invocation_id` là FK bắt buộc, implying 1-1. Doc 05 không mô tả scenario "Sandbox mới cho AgentInvocation cũ".

**Mâu thuẫn tiềm ẩn:** Nếu Sandbox fail ở `provisioning → failed` trước khi AgentInvocation chuyển sang `running`, thì:
- AgentInvocation vẫn đang `initializing`.
- Execution layer tạo Sandbox mới.
- Sandbox mới có `agent_invocation_id` trỏ về cùng AgentInvocation cũ.
- Nhưng Sandbox cũ đang `failed → terminating → terminated` — hai Sandbox cùng FK tồn tại song song trong thời gian ngắn.

**Cần khóa:** Doc 04 phải nói rõ `Sandbox.agent_invocation_id` là NOT UNIQUE — một AgentInvocation có thể có nhiều Sandbox records (chỉ một active tại một thời điểm). Trường `is_active` hoặc `sandbox_attempt_index` cần bổ sung.

---

### 1.3 AgentInvocation `compensated` → Step state là gì — GAP

**Vấn đề:** Doc 05 mô tả AgentInvocation lifecycle đến `compensated` là terminal. Nhưng không có quy tắc nào nói rõ Step parent của AgentInvocation này chuyển sang state gì khi AgentInvocation `compensated`.

**Ba khả năng, chưa được chọn:**
1. Step → `failed` (compensation = lỗi không recover được ở cấp Step).
2. Step → `completed` với flag `compensation_applied` (compensation thành công = outcome hợp lệ).
3. Step → `cancelled` (compensation là cleanup, không phải kết quả).

**Cần khóa:** Đây là gap thật sự. Khuyến nghị: `compensated` AgentInvocation → Step `failed` với `error_detail.compensation_applied = true`. Lý do: compensation có nghĩa là side effects đã xảy ra và phải undo — đó là failure, không phải success.

---

### 1.4 `run.timed_out` phát sinh hai event — CLARIFY

**Vấn đề:** Doc 05 định nghĩa: `running → timed_out → cancelled (system cleanup)`. Tức là `timed_out` không phải terminal — nó bắt buộc phải đi đến `cancelled`.

Doc 06 có cả `run.timed_out` và `run.cancelled` là hai event riêng. Implementor có thể emit chỉ `run.timed_out` và quên emit `run.cancelled`.

**Cần khóa:** Bổ sung note vào doc 06: *"`run.timed_out` không thể là event cuối cùng của một Run. `run.cancelled` phải được emit ngay sau đó bởi Orchestrator trong cùng transaction/outbox."*

---

### 1.5 Taint flag là state, event chỉ là notification — PASS với note

Doc 10 đã khóa đúng: *"Taint là state, không phải event. Nếu taint propagation event fail, taint vẫn phải được set trên artifact."*

Doc 12 bảng L6 confirm: `taint propagation event fail to emit → retry emit — taint flag vẫn giữ`.

Nhất quán. Tuy nhiên: implementor phải biết write taint flag vào DB **trước** khi emit event — không phải sau. Thứ tự này phải được document trong service implementation guide.

---

### 1.6 Policy snapshot trong Sandbox là bất biến — PASS

Doc 08 (EP3), Doc 09 (P7), Doc 12 (FR8) đều nhất quán: `policy_snapshot` bị lock sau khi Sandbox rời `provisioning`. Không có doc nào mở ngoại lệ.

---

## 2. No Hidden Bypass

### 2.1 API có thể bypass state machine — GAP NGHIÊM TRỌNG

**Vấn đề:** Bộ doc hiện tại khóa state machine đúng, nhưng không có doc nào nói rõ cơ chế enforcement tại DB/API layer.

Ví dụ: Không có gì ngăn một service gọi `UPDATE runs SET run_status = 'running' WHERE id = ?` trực tiếp trên một Run đang `failed` — đây là bypass hoàn toàn state machine.

**Bypass path tiềm năng:**
- Direct DB write từ service internal (bỏ qua Orchestrator).
- Recovery script của ops team viết tắt qua DB.
- Bug trong Orchestrator gọi sai method.

**Cần khóa trong doc 15 (Backend Service Map) và doc 16 (Repo Conventions):** Mọi state transition phải đi qua một single method trong Orchestrator domain service — không có direct DB update nào cho `*_status` fields ở bất kỳ đâu ngoài method đó. Enforce bằng architecture test / linting rule.

---

### 2.2 Artifact creation có thể bypass Artifact service — GAP

**Vấn đề:** Doc 04, 09 (FD9), 10 (L6), 12 (FR7) đều khẳng định `artifact_service` là đường vào duy nhất. Nhưng nếu Agent Engine có quyền write vào cùng DB, không có gì ngăn direct insert.

**Cần khóa trong doc 15:** Artifact table phải được sở hữu riêng bởi Artifact service. Các service khác không có DB credentials để write vào artifact table. Enforce bằng DB-level permission (separate schema hoặc separate DB user).

---

### 2.3 Orchestrator rebuild sau crash — không bypass state machine — PASS với pressure note

Doc 12 mục 4.1 nói: *"Orchestrator phải rebuild state từ event log — không từ in-memory state."*

Đây là đúng và không tạo bypass. Tuy nhiên đây là **implementation pressure point số 1** (xem mục 5).

---

### 2.4 Permission check có thể bị bypass nếu Policy store down — PASS

Doc 09 + Doc 12 (L7) nhất quán: Policy store unreachable → fail closed (deny all). Không có path nào fail open trong bộ doc hiện tại.

---

### 2.5 Approval có thể bị bypass nếu timeout xử lý sai — CLARIFY

**Vấn đề:** Doc 05 nói `timeout_at` hết → approval `timed_out` → entity cha `cancelled`. Nhưng ai watch `timeout_at`? Nếu scheduler miss timeout (scheduler down), approval request treo vô hạn và Run không tiến thêm được.

**Cần khóa trong doc 12 hoặc doc 15:** Orchestrator phải có một timeout watcher process. Nếu watcher miss một cycle, approval phải được resolve ở lần watcher chạy tiếp — không phải chờ đến next event.

---

## 3. Terminal Semantics Alignment

### 3.1 Bảng terminal states cross-doc

| Entity | Terminal states | Ghi chú |
|---|---|---|
| Task | `completed`, `failed`, `cancelled`, `archived` | `archived` là terminal vĩnh viễn |
| Run | `completed`, `failed`, `cancelled`, `timed_out`* | *`timed_out` → `cancelled` bắt buộc (xem 1.4) |
| Step | `completed`, `failed`, `skipped`, `cancelled` | `skipped` là terminal — không thể unship |
| AgentInvocation | `completed`, `failed`, `interrupted`, `compensated` | `compensated` → Step state cần khóa (xem 1.3) |
| Sandbox | `terminated` | `failed` là mid-state → selalu resolve to `terminated` |
| Artifact | `ready`, `failed`, `superseded`, `archived` | `superseded` vẫn readable và downloadable |
| Approval | `approved`, `rejected`, `timed_out` | Tất cả đều terminal |

### 3.2 Sandbox `failed` không phải terminal — CLARIFY

**Vấn đề:** Doc 05 Sandbox lifecycle: `failed → terminating → terminated`. Tức là `failed` là mid-state — Sandbox luôn phải đi qua `terminated`.

Nhưng trong bảng alert doc 11, một số chỗ xử lý `sandbox.failed` như terminal event. Và doc 12 bảng L3 viết *"`sandbox.failed` → interrupt AgentInvocation → fail Step"* — đây là đúng, nhưng Sandbox vẫn phải tiếp tục đến `terminated` sau đó.

**Cần khóa:** Thêm note rõ ràng: *"Sandbox `failed` là intermediate state. Bất kể kết quả, `sandbox.terminated` là state và event cuối cùng bắt buộc của mọi Sandbox. Không có Sandbox nào kết thúc lifecycle ở `failed`."*

---

### 3.3 `archived` là terminal vĩnh viễn — PASS

Doc 04, 05, 10 nhất quán: Artifact/Task không thể rời `archived`. Không có state transition nào từ `archived` quay về.

---

### 3.4 `tainted` không phải state, là property — PASS

Doc 10 đã thiết kế đúng: `tainted` là boolean property trên Artifact, không phải state trong state machine. Artifact `ready + tainted` vẫn có state `ready` — nhưng access rules bị restrict. Nhất quán với doc 09 và doc 11.

---

## 4. Operational Truth Alignment

### 4.1 Source of truth map

| Layer | Entity | Source of truth | Conflict nếu lệch |
|---|---|---|---|
| Identity | User | Auth service | Auth down → deny all (doc 12 L7) |
| Workspace | Workspace, Member, Policy, SecretBinding | Workspace service DB | Policy unreachable → fail closed |
| Orchestration | Task, Run, Step | Orchestrator DB + Event log | Rebuild từ event log sau crash |
| Execution | AgentInvocation | Agent Engine DB + Event log | Potential disagreement với Orchestrator (xem 4.2) |
| Sandbox | Sandbox metadata | Execution layer DB | Sandbox terminated = cleaned up |
| Storage | Artifact content | Storage layer | Checksum = ground truth |
| Artifact metadata | Artifact | Artifact service DB | Lineage + provenance fields |
| History | Tất cả events | Event store | Append-only, không sửa |
| Permission decisions | Audit records | Audit log | Không thể reconstruct nếu mất |

### 4.2 Orchestrator / Agent Engine có thể bất đồng sau dual crash — GAP

**Vấn đề:** Doc 12 mục 4.1: *"Orchestrator rebuild từ event log."* Nhưng nếu cả Orchestrator **và** Agent Engine crash đồng thời:

- Orchestrator rebuild: thấy `run.started`, `step.started`, `agent_invocation.started` — kết luận AgentInvocation đang `running`.
- Agent Engine restart: không có in-memory state — kết luận không có AgentInvocation nào đang chạy.
- Hệ bị split-brain: Orchestrator tin AgentInvocation `running`, Agent Engine không có context.

**Cần khóa trong doc 15:** Agent Engine phải persist AgentInvocation state vào DB **đồng bộ** (không chỉ in-memory) và cũng phải có khả năng rebuild từ event log, giống Orchestrator. Khi restart, Agent Engine phải reconcile state với event log trước khi nhận request mới.

---

### 4.3 `run_config` lock tại transition boundary — CLARIFY

**Vấn đề:** Doc 05: `run_config` bị lock khi Run rời `queued`. Doc 12 mục 4.1: Orchestrator restart có thể re-process `queued → preparing` transition.

Nếu transition đã xảy ra (run_config đã locked) nhưng event `run.preparing` chưa được emit (crash ngay sau DB write), Orchestrator restart sẽ thấy Run vẫn ở `queued` trong event log nhưng DB đã ở `preparing`.

**Cần khóa:** State machine transitions phải dùng **event-sourcing pattern**: state chỉ được đọc từ event log, không từ DB trực tiếp, **hoặc** DB write và event emit phải đi trong cùng outbox transaction. Không thể để hai source lệch nhau.

---

### 4.4 Audit record là non-reconstructible — PASS với pressure note

Doc 09 mục 9.3: Nếu audit write fail với permission.violation → fail-safe deny. Đây là đúng. Nhưng audit record không thể reconstruct sau khi mất (không như event log có thể rebuild state machine).

**Pressure note:** Audit store phải có higher durability SLA hơn event store thông thường. Doc 13 phải reflect điều này trong deployment topology.

---

## 5. Implementation Pressure Points

Đây là 10 điểm mà team code dễ làm sai nhất, cần được khóa trong doc 13–17:

---

**PP1 — State transition enforcement tại DB layer**

Dễ sai: Developer viết `repository.save(run)` sau khi gán `run.status = 'running'` trực tiếp, bỏ qua state machine.

Cần làm: Single domain method per transition. Architecture test: không có file nào ngoài `OrchestratorDomainService` được gọi method write `run_status`.

---

**PP2 — Orchestrator crash recovery — partial event log**

Dễ sai: Orchestrator rebuild state từ event log, nhưng outbox chưa kịp relay một số events trước khi crash. Rebuilt state bị thiếu transition.

Cần làm: Outbox relay phải chạy trước khi Orchestrator accept bất kỳ request mới nào sau restart. "Startup readiness" = outbox fully flushed.

---

**PP3 — Agent Engine / Orchestrator split-brain sau dual crash**

Dễ sai: Agent Engine restart không reconcile với event log — assume không có in-flight AgentInvocation.

Cần làm: Agent Engine startup phải query event log cho tất cả `agent_invocation.started` chưa có terminal event, và interrupt chúng trước khi nhận request mới.

---

**PP4 — Sandbox 1-N với AgentInvocation**

Dễ sai: Code assume `sandbox.agent_invocation_id` là unique — query `WHERE agent_invocation_id = ?` trả về một row, nhưng có thể có nhiều rows (attempt 1 failed, attempt 2 active).

Cần làm: Bổ sung `sandbox_attempt_index` vào Sandbox entity. Query phải filter `WHERE agent_invocation_id = ? AND is_active = true`.

---

**PP5 — Taint write trước event emit**

Dễ sai: Code emit `artifact.tainted` event trước khi write `tainted = true` vào DB. Nếu DB write fail sau event emit, consumer downstream đã act on taint nhưng DB không có record.

Cần làm: Taint write vào DB phải đi trong cùng outbox transaction với event emit. DB write trước, outbox relay sau.

---

**PP6 — `run.timed_out` không emit `run.cancelled`**

Dễ sai: Developer thấy `run.timed_out` là event "đủ" và không emit `run.cancelled` tiếp theo.

Cần làm: `timed_out` state transition phải trigger **hai** outbox entries: `run.timed_out` và `run.cancelled`, trong cùng một transaction.

---

**PP7 — Tool idempotency contract không được enforce**

Dễ sai: Tool được retry (vì khai báo `idempotent: true`) nhưng thực ra không idempotent (VD: tool gửi email, insert DB row).

Cần làm: Tool registration phải có `idempotency_proof` field — không phải self-declared. CI phải chạy idempotency test cho mọi tool trước khi ship.

---

**PP8 — Approval timeout watcher bị miss**

Dễ sai: Scheduler down → approval timeout không được trigger → Run treo vô hạn ở `waiting_approval`.

Cần làm: Orchestrator phải check approval timeouts khi processing bất kỳ event nào liên quan đến workspace đó — không chỉ dựa vào scheduler. Defensive timeout check là bắt buộc.

---

**PP9 — Artifact provenance tuple incomplete tại write time**

Dễ sai: Artifact được tạo với `root_type = generated` nhưng `model_version` chỉ là alias (`latest`) không phải version cụ thể. Artifact pass validation và được promote `ready` với reproducibility tuple không hợp lệ.

Cần làm: Artifact service phải validate `model_version` không phải alias trước khi accept artifact registration. Model Gateway phải resolve alias thành version cụ thể trước khi pass xuống.

---

**PP10 — Direct DB access đến artifact table từ non-artifact service**

Dễ sai: Developer viết migration script hoặc debug tool query trực tiếp artifact table để "fix" data, bỏ qua lineage và event trail.

Cần làm: Artifact table nằm trong DB schema riêng với credentials riêng. Chỉ `artifact_service` service account có WRITE permission. Mọi "fix" phải đi qua Artifact service API.

---

## 6. Do-Not-Break List trước khi đi vào 13–17

Những quyết định sau **không được phép thay đổi** trong quá trình viết doc 13–17 hay khi implement. Nếu topology, service map, hay repo structure mâu thuẫn với những điểm này — topology phải thay đổi, không phải những điểm này:

| # | Quyết định | Xuất xứ |
|---|---|---|
| DNB1 | Run không bao giờ resume — chỉ Rerun tạo Run mới | doc 05, 12 |
| DNB2 | EP fail closed — không bao giờ fail open | doc 09, 12 |
| DNB3 | Security violation không auto-recover | doc 12 F6 |
| DNB4 | Degraded mode không auto-escalate permission | doc 12 mục 7.2 |
| DNB5 | Recovery phải có event + audit | doc 12 F7 |
| DNB6 | `artifact_service` là đường vào duy nhất cho artifact creation | doc 10 L6, 09 FD9 |
| DNB7 | `trace_id = correlation_id` — không tạo hai ID riêng | doc 11 O5 |
| DNB8 | Execution trace và provenance trace là hai hệ quan sát riêng | doc 11 O6 |
| DNB9 | Agent không tự nâng quyền qua prompt hay tool call | doc 09 P2 |
| DNB10 | Mọi state transition phải đi qua Orchestrator domain service | doc 05, gap PP1 |
| DNB11 | Taint write vào DB trước event emit — không sau | gap PP5 |
| DNB12 | Model version không được là alias tại artifact registration | gap PP9 |

---

## 7. Kết luận Gate Review

**Trạng thái tổng thể:** Bộ 00–12 đủ điều kiện làm hiến pháp kiến trúc. Không có mâu thuẫn nào đủ nghiêm trọng để chặn việc đi tiếp.

**Cần xử lý trước khi code:**

| Mức độ | Số lượng | Hành động |
|---|---|---|
| GAP nghiêm trọng | 3 | API bypass state machine (PP1), Artifact table isolation (PP10), Agent Engine rebuild (PP3) — phải khóa trong doc 15 |
| CLARIFY | 5 | Sandbox 1-N (PP4), run.timed_out dual event (1.4), AgentInvocation compensated → Step state (1.3), Approval watcher (PP8), run_config lock boundary (4.3) — bổ sung note vào doc tương ứng |
| Pressure notes | 10 | PP1–PP10 — phải xuất hiện tường minh trong doc 16 (Repo Conventions) và doc 17 (Roadmap) |

**Thứ tự xử lý tiếp:**  
13 → 15 → 14 → 16 → 17 (theo thứ tự đã thống nhất, bắt đầu từ doc 13 Deployment Topology).
