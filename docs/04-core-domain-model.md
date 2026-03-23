# 04 — Core Domain Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 00 Product Vision, 01 Goals & Non-goals, 02 Invariants, 03 Bounded Contexts  
**Mục tiêu tài liệu này:** Khóa toàn bộ object nghiệp vụ lõi, quan hệ giữa chúng, aggregate boundary, và source of truth — làm nền cho DB schema, API schema, event schema, và state machine.

---

## 1. Nguyên tắc đặt tên

| Quy tắc | Lý do |
|---|---|
| PascalCase cho entity | Phân biệt với field/attribute |
| snake_case cho field | Nhất quán với DB và JSON |
| Không viết tắt trong tên entity | `AgentInvocation` không phải `AgentInvoc` |
| Tên field dùng `_at` cho timestamp | `created_at`, `started_at`, `completed_at` |
| Tên field dùng `_id` cho foreign key | `workspace_id`, `task_id` |
| Tên field dùng `_status` cho state | `run_status`, `artifact_status` |

---

## 2. Entity Map tổng quan

```
Workspace
  └── Member (User × Workspace)
  └── Policy
  └── SecretBinding
  └── RepoSnapshot
  └── Task
        └── Run
              └── Step
              └── AgentInvocation
                    └── Sandbox
              └── Artifact
  └── Event (append-only log)
```

---

## 3. Entity chi tiết

---

### 3.1 User

Danh tính người dùng trong hệ thống. Không gắn chặt với workspace nào.

**Source of truth:** Auth layer / identity store

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | Primary key |
| `email` | string | ✓ | Duy nhất toàn hệ thống |
| `display_name` | string | ✓ | Tên hiển thị |
| `auth_provider` | enum | ✓ | `local`, `google`, `github`, `sso` |
| `auth_provider_id` | string | | ID từ provider ngoài |
| `created_at` | timestamp | ✓ | |
| `last_active_at` | timestamp | | |

**Quan hệ:** User tham gia Workspace qua entity `Member`.

---

### 3.2 Workspace

Đơn vị tổ chức cao nhất. Mọi tài nguyên thuộc về một Workspace cụ thể.

**Source of truth:** Workspace service

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | Primary key |
| `slug` | string | ✓ | URL-safe, duy nhất toàn hệ thống |
| `display_name` | string | ✓ | |
| `plan` | enum | ✓ | `personal`, `team`, `enterprise` |
| `deployment_mode` | enum | ✓ | `local`, `cloud`, `hybrid` |
| `owner_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |
| `settings` | JSONB | | Cấu hình workspace-level |

**Aggregate root:** Workspace là aggregate root cho Member, Policy, SecretBinding.

---

### 3.3 Member

Liên kết User với Workspace, mang role và permission.

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `user_id` | UUID → User | ✓ | |
| `role` | enum | ✓ | `owner`, `admin`, `editor`, `viewer` |
| `joined_at` | timestamp | ✓ | |
| `invited_by_id` | UUID → User | | |

**Ràng buộc:** `(workspace_id, user_id)` là unique.

---

### 3.4 Policy

Quy tắc kiểm soát hành vi trong Workspace: permission, sandbox limits, model access, egress rules.

**Source of truth:** Permission/Policy service

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `name` | string | ✓ | |
| `scope` | enum | ✓ | `workspace`, `task_type`, `agent`, `tool` |
| `rules` | JSONB | ✓ | Danh sách rule theo schema chuẩn |
| `is_default` | boolean | ✓ | |
| `created_at` | timestamp | ✓ | |

**Ghi chú:** Policy không được resolve tại UI hay Tool layer. Chỉ Orchestrator và Sandbox mới được đọc và enforce Policy.

---

### 3.5 SecretBinding

Cơ chế inject secret vào Sandbox mà không expose giá trị raw ra bất kỳ layer nào khác.

**Source of truth:** Secret store (Vault / KMS tùy deployment mode)

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `name` | string | ✓ | Tên alias dùng trong run config, VD: `OPENAI_KEY` |
| `secret_ref` | string | ✓ | Con trỏ tới secret store, không phải giá trị thật |
| `scope` | enum | ✓ | `workspace`, `task`, `agent` |
| `created_by_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |

**Invariant:** Giá trị secret không được lưu trong domain model. Chỉ lưu `secret_ref`.

---

### 3.6 RepoSnapshot

Ảnh chụp tại thời điểm một Git repository — là input cố định cho Task/Run, đảm bảo reproducibility.

**Source of truth:** Storage layer

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `source_url` | string | ✓ | URL repo gốc |
| `commit_sha` | string | ✓ | SHA của commit được snapshot |
| `branch` | string | | |
| `snapshot_storage_ref` | string | ✓ | Con trỏ tới file snapshot trong storage |
| `size_bytes` | int | | |
| `created_at` | timestamp | ✓ | |
| `created_by_id` | UUID → User | ✓ | |

---

### 3.7 Task

Đơn vị công việc do người dùng tạo ra. Task là khai báo "mình muốn làm gì", không phải khai báo "thực thi thế nào".

**Source of truth:** Orchestrator

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `title` | string | ✓ | |
| `description` | text | | |
| `task_type` | enum | ✓ | `coding`, `research`, `analysis`, `operation`, `custom` |
| `task_status` | enum | ✓ | Xem State Machine |
| `input_config` | JSONB | ✓ | Tham số đầu vào: repo, prompt, params |
| `repo_snapshot_id` | UUID → RepoSnapshot | | Nếu task liên quan đến code |
| `policy_id` | UUID → Policy | | Policy áp dụng cho task này |
| `created_by_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |
| `updated_at` | timestamp | ✓ | |
| `parent_task_id` | UUID → Task | | Nếu là subtask |

**Aggregate root:** Task là aggregate root cho Run.

---

### 3.8 Run

Một lần thực thi của Task. Một Task có thể có nhiều Run (retry, re-run, experimental run).

**Source of truth:** Orchestrator

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `task_id` | UUID → Task | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized để query nhanh |
| `run_status` | enum | ✓ | Xem State Machine |
| `trigger_type` | enum | ✓ | `manual`, `scheduled`, `event`, `approval` |
| `triggered_by_id` | UUID → User | | Null nếu triggered by event/schedule |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `duration_ms` | int | | |
| `run_config` | JSONB | ✓ | Snapshot config tại thời điểm chạy (immutable sau khi started) |
| `error_summary` | text | | |
| `created_at` | timestamp | ✓ | |

**Invariant:** `run_config` không được thay đổi sau khi Run chuyển sang `running`.  
**Invariant:** Mọi Run phải reproducible từ `run_config` + `repo_snapshot_id` + artifact lineage.

---

### 3.9 Step

Đơn vị thực thi nhỏ nhất có thể trace được trong một Run. Bao gồm cả agent invocation, tool call, approval gate, hoặc bước logic.

**Source of truth:** Orchestrator

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `run_id` | UUID → Run | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `step_type` | enum | ✓ | `agent_invocation`, `tool_call`, `approval_gate`, `condition`, `transform` |
| `step_status` | enum | ✓ | Xem State Machine |
| `sequence` | int | ✓ | Thứ tự trong Run |
| `parent_step_id` | UUID → Step | | Nếu là sub-step |
| `input_snapshot` | JSONB | | Input tại thời điểm chạy |
| `output_snapshot` | JSONB | | Output thu được |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `error_detail` | JSONB | | |

---

### 3.10 AgentInvocation

Một lần gọi vào agent runtime. Tách khỏi Step vì một Step có thể spawn nhiều AgentInvocation (multi-turn, retry, fan-out).

**Source of truth:** Agent Engine

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `step_id` | UUID → Step | ✓ | |
| `run_id` | UUID → Run | ✓ | Denormalized |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `agent_id` | string | ✓ | ID định danh agent definition |
| `model_id` | string | ✓ | Model được dùng (VD: `claude-3-7-sonnet`) |
| `invocation_status` | enum | ✓ | Xem State Machine |
| `prompt_tokens` | int | | |
| `completion_tokens` | int | | |
| `total_cost_usd` | decimal | | |
| `input_messages` | JSONB | | Snapshot toàn bộ input message |
| `output_messages` | JSONB | | Snapshot toàn bộ output |
| `tool_calls` | JSONB | | Danh sách tool call phát sinh |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `error_detail` | JSONB | | |

**Invariant:** Agent Engine không sở hữu artifact. Artifact chỉ được tạo bởi Artifact service sau khi AgentInvocation hoàn thành.

---

### 3.11 Sandbox

Môi trường thực thi cô lập cho một AgentInvocation hoặc nhóm tool calls.

**Source of truth:** Execution/Sandbox layer

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `agent_invocation_id` | UUID → AgentInvocation | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `sandbox_type` | enum | ✓ | `container`, `vm`, `wasm`, `subprocess` |
| `sandbox_status` | enum | ✓ | Xem State Machine |
| `policy_snapshot` | JSONB | ✓ | Policy áp dụng tại thời điểm tạo sandbox (immutable) |
| `resource_limits` | JSONB | ✓ | CPU, memory, network, timeout |
| `network_egress_policy` | JSONB | ✓ | Whitelist/blacklist network |
| `started_at` | timestamp | | |
| `terminated_at` | timestamp | | |
| `termination_reason` | enum | | `completed`, `timeout`, `policy_violation`, `error`, `manual` |

**Invariant:** Sandbox là ephemeral — không được persist state nội tại qua các invocation.  
**Invariant:** UI layer không được gọi Sandbox trực tiếp.

---

### 3.12 Artifact

Output có giá trị được tạo ra bởi một Run/Step/AgentInvocation. Là kết quả tồn tại lâu dài.

**Source of truth:** Artifact service / Storage layer

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `run_id` | UUID → Run | ✓ | |
| `step_id` | UUID → Step | | Null nếu artifact của cả Run |
| `artifact_type` | enum | ✓ | `file`, `code_patch`, `report`, `dataset`, `log`, `structured_data` |
| `artifact_status` | enum | ✓ | `pending`, `writing`, `ready`, `failed`, `archived` |
| `name` | string | ✓ | |
| `storage_ref` | string | ✓ | Con trỏ tới storage (không phải URL trực tiếp) |
| `size_bytes` | int | | |
| `checksum` | string | ✓ | SHA-256 của nội dung |
| `lineage` | JSONB | | Danh sách `artifact_id` cha (nếu là derived artifact) |
| `metadata` | JSONB | | Thông tin bổ sung theo artifact_type |
| `created_at` | timestamp | ✓ | |
| `created_by_invocation_id` | UUID → AgentInvocation | | |

**Invariant:** Artifact không được xóa — chỉ được archive.  
**Invariant:** Một Artifact `ready` có `checksum` không được phép thay đổi.

---

### 3.13 Event

Append-only log của mọi thay đổi trạng thái quan trọng trong hệ thống.

**Source of truth:** Event store (append-only)

| Field | Type | Bắt buộc | Mô tả |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `event_type` | string | ✓ | VD: `task.created`, `run.started`, `artifact.ready` |
| `aggregate_type` | enum | ✓ | `workspace`, `task`, `run`, `step`, `agent_invocation`, `artifact` |
| `aggregate_id` | UUID | ✓ | ID của entity phát sinh event |
| `payload` | JSONB | ✓ | Dữ liệu của event |
| `correlation_id` | UUID | ✓ | Liên kết các event trong cùng một Run |
| `causation_id` | UUID | | ID của event là nguyên nhân |
| `actor_type` | enum | ✓ | `user`, `agent`, `system`, `scheduler` |
| `actor_id` | string | ✓ | ID của actor |
| `occurred_at` | timestamp | ✓ | |
| `schema_version` | string | ✓ | VD: `1.0` |

**Invariant:** Event không được update hay delete sau khi ghi.  
**Invariant:** Mọi thay đổi trạng thái dài hạn phải có Event tương ứng.

---

## 4. Aggregate Boundaries

| Aggregate Root | Owned Entities | Không được own |
|---|---|---|
| Workspace | Member, Policy, SecretBinding | Task (riêng), User (global) |
| Task | Run | Step (thuộc Run), Artifact (thuộc Run) |
| Run | Step, Artifact | AgentInvocation (thuộc Step) |
| Step | AgentInvocation | Sandbox (thuộc AgentInvocation) |
| AgentInvocation | Sandbox | Artifact (Artifact service riêng) |

---

## 5. Quan hệ tổng hợp

```
User ──< Member >── Workspace
                      │
               ┌──────┼──────┐
            Policy  Secret  RepoSnapshot
                      │
                    Task
                      │
                     Run ──── Artifact
                      │
                    Step ──── Artifact
                      │
              AgentInvocation
                      │
                   Sandbox
                      
Event ← (phát sinh bởi bất kỳ entity nào)
```

---

## 6. Source of Truth theo layer

| Entity | Layer chịu trách nhiệm |
|---|---|
| User | Auth / Identity service |
| Workspace, Member, Policy, SecretBinding | Workspace service |
| RepoSnapshot | Storage layer (ingested by Workspace service) |
| Task | Orchestrator |
| Run, Step | Orchestrator |
| AgentInvocation | Agent Engine |
| Sandbox | Execution layer |
| Artifact | Artifact service |
| Event | Event store |

---

## 7. Những quyết định chưa khóa (để ngỏ có chủ đích)

| Điểm | Lý do chưa khóa |
|---|---|
| Schema cụ thể của `policy.rules` | Cần sau khi khóa Permission Model (doc 09) |
| Schema cụ thể của `input_config` theo từng `task_type` | Cần sau khi khóa API Contracts (doc 07) |
| Cơ chế lưu `input_messages` / `output_messages` của AgentInvocation | Phụ thuộc vào storage strategy và privacy model |
| `artifact.lineage` schema chi tiết | Cần sau khi khóa Artifact Lineage Model (doc 10) |
| `sandbox.network_egress_policy` schema | Cần sau khi khóa Sandbox Security Model (doc 08) |

---

## 8. Bước tiếp theo

Tài liệu tiếp theo cần viết ngay là **05 — State Machines**, bao gồm:

- Task lifecycle
- Run lifecycle
- Step lifecycle
- AgentInvocation lifecycle
- Sandbox lifecycle
- Artifact lifecycle
- Approval flow

Tất cả đều bám trực tiếp vào các entity đã định nghĩa trong tài liệu này.
