# 07 — API Contracts

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts  
**Mục tiêu:** Khóa public control surface của toàn hệ thống — API là lớp con người và client tương tác với state machine và event model, không phải lớp tạo ra chúng.

---

## 1. API Principles

### 1.1 API là control/query surface — không phải source of truth

State machine (doc 05) là source of truth cho lifecycle. Event store (doc 06) là source of truth cho lịch sử. API chỉ làm 3 việc:

1. **Tạo ý định** — submit task, cancel task, approve, attach repo.
2. **Truy vấn trạng thái** — get task, list runs, get artifact.
3. **Human intervention** — approve, reject, respond to agent waiting for human.

API không được làm bất kỳ điều gì ngoài 3 việc đó.

### 1.2 Command API trả acknowledgement — không trả kết quả cuối cùng

Khi một command được accept, API trả `202 Accepted` kèm resource reference. Kết quả cuối cùng đến qua event stream hoặc polling query. API không được block chờ Orchestrator hoàn thành trước khi trả response.

### 1.3 Mọi mutation phải map về state transition + event

Không tồn tại endpoint thay đổi trạng thái mà không có state transition hợp lệ tương ứng trong doc 05 và event bắt buộc tương ứng trong doc 06. Nếu một mutation không có state transition, nó không được phép tồn tại như endpoint.

### 1.4 UI convenience không được sinh ra API sai kiến trúc

Nếu UI cần một thứ mà API đúng kiến trúc không cung cấp, giải pháp là xây BFF (Backend for Frontend) layer — không phải hack endpoint core.

---

## 2. Versioning và Compatibility Policy

### 2.1 URL versioning

Tất cả endpoint bắt đầu bằng `/v1/`. Không có endpoint không có version prefix.

### 2.2 Backward compatibility

Trong cùng major version (`v1`):
- Thêm field vào response: **allowed** (clients phải tolerant với unknown field).
- Thêm optional field vào request: **allowed**.
- Đổi tên field: **không allowed** — tạo field mới, deprecate field cũ.
- Xóa field: **không allowed** trong v1 — chỉ được xóa khi bump lên v2.
- Thay đổi kiểu dữ liệu của field: **không allowed**.

### 2.3 Deprecation policy

- Field/endpoint bị deprecated phải gắn header `Deprecation: true` và `Sunset: <date>`.
- Thời gian từ deprecated → removed: tối thiểu **60 ngày**.
- Trong thời gian deprecated, field vẫn hoạt động bình thường.

### 2.4 Breaking changes

Breaking change chỉ được phép khi bump major version (`v2`). `/v1` và `/v2` phải chạy song song tối thiểu **90 ngày** sau khi v2 ra.

---

## 3. Common Request/Response Envelope

### 3.1 Response envelope chuẩn

Mọi response đều bọc trong envelope sau:

```json
{
  "data": { },
  "meta": {
    "request_id": "<UUID>",
    "workspace_id": "<UUID>",
    "api_version": "v1",
    "timestamp": "<ISO 8601>"
  },
  "error": null
}
```

- Khi thành công: `data` chứa payload, `error` là `null`.
- Khi lỗi: `data` là `null`, `error` chứa error object (xem mục 4).
- `meta` luôn có mặt trong mọi response.

### 3.2 Pagination

List endpoint dùng cursor-based pagination:

```json
{
  "data": {
    "items": [ ],
    "pagination": {
      "next_cursor": "<opaque string | null>",
      "has_more": true,
      "limit": 20
    }
  }
}
```

Không dùng offset-based pagination. Cursor là opaque — client không được parse.

### 3.3 Command response (202 Accepted)

```json
{
  "data": {
    "accepted": true,
    "resource_type": "task",
    "resource_id": "<UUID>",
    "current_status": "pending",
    "correlation_id": "<UUID>"
  },
  "meta": { }
}
```

`correlation_id` ở đây là correlation_id của event sẽ được phát — client dùng để subscribe event stream.

---

## 4. Error Model

Mọi error response dùng cấu trúc sau:

```json
{
  "data": null,
  "meta": { },
  "error": {
    "error_code": "<string>",
    "message": "<human-readable string>",
    "details": [ ],
    "retryable": false,
    "conflict_with_state": "<current_state | null>",
    "correlation_id": "<UUID | null>"
  }
}
```

### 4.1 HTTP status codes chuẩn

| HTTP Status | Khi nào dùng |
|---|---|
| `200 OK` | Query thành công |
| `201 Created` | Resource được tạo synchronously (hiếm) |
| `202 Accepted` | Command được accept, xử lý async |
| `400 Bad Request` | Request malformed, validation fail |
| `401 Unauthorized` | Chưa auth |
| `403 Forbidden` | Đã auth nhưng không có permission |
| `404 Not Found` | Resource không tồn tại hoặc không visible trong workspace |
| `409 Conflict` | Mutation vi phạm state machine hiện tại |
| `422 Unprocessable` | Request hợp lệ về cú pháp nhưng không thể thực hiện do business logic |
| `429 Too Many Requests` | Rate limit |
| `500 Internal Server Error` | Lỗi server không mong đợi |
| `503 Service Unavailable` | Service tạm thời không sẵn sàng |

### 4.2 Error codes chuẩn

| `error_code` | HTTP | Mô tả |
|---|---|---|
| `INVALID_REQUEST` | 400 | Validation fail |
| `UNAUTHORIZED` | 401 | Thiếu hoặc token không hợp lệ |
| `FORBIDDEN` | 403 | Không có permission |
| `NOT_FOUND` | 404 | Resource không tồn tại |
| `STATE_CONFLICT` | 409 | Vi phạm state machine — `conflict_with_state` chứa state hiện tại |
| `ALREADY_EXISTS` | 409 | Resource đã tồn tại (idempotency case) |
| `UNPROCESSABLE` | 422 | Business logic từ chối |
| `RATE_LIMITED` | 429 | Rate limit |
| `INTERNAL_ERROR` | 500 | Lỗi server |
| `SERVICE_UNAVAILABLE` | 503 | Tạm thời không sẵn sàng, `retryable: true` |

---

## 5. Idempotency Model

### 5.1 Command endpoint bắt buộc dùng `Idempotency-Key`

Các command sau **bắt buộc** client gửi header `Idempotency-Key: <UUID>`:

- `POST /v1/tasks` (submit task)
- `POST /v1/tasks/:id/cancel`
- `POST /v1/runs/:id/cancel`
- `POST /v1/approvals/:id/approve`
- `POST /v1/approvals/:id/reject`
- `POST /v1/repos/snapshots` (trigger snapshot)

### 5.2 Scope của Idempotency-Key

- Scope: `(workspace_id, actor_id, idempotency_key)`.
- TTL: 24 giờ. Sau 24 giờ, cùng key có thể tạo resource mới.
- Nếu request với cùng key đã được xử lý thành công: trả lại response gốc với `200 OK` (không phải `202`), kèm header `Idempotency-Replayed: true`.
- Nếu request với cùng key đang được xử lý: trả `409 Conflict` với `error_code: ALREADY_EXISTS`.
- Nếu request với cùng key đã fail: cho phép retry với cùng key.

---

## 6. Auth và Permission Checkpoints

Mỗi endpoint gắn với một permission point cụ thể. Permission được resolve bởi Permission service dựa trên `Member.role` và `Policy` của Workspace (sẽ chi tiết trong doc 09).

| Action | Minimum role | Policy override |
|---|---|---|
| Submit task | `editor` | Policy có thể restrict theo `task_type` |
| Cancel task | `editor` (owner) hoặc `admin` | |
| Cancel task của người khác | `admin` | |
| Approve/reject | `editor` với approver role được chỉ định | Approval request chỉ định `approver_role` |
| Attach repo | `editor` | |
| Read task/run/artifact | `viewer` | |
| Read artifact với sensitive flag | `editor` | Policy có thể restrict |
| Attach terminal/session | `editor` | Policy có thể disable hoàn toàn |
| Admin workspace settings | `admin` | |
| Tạo/sửa Policy | `owner` | |
| Manage secrets | `owner` hoặc `admin` | |

**Invariant từ doc 02:** Permission không được resolve tại UI layer. API layer forward request kèm identity tới Permission service. Permission service đưa ra quyết định.

---

## 7. Workspace APIs

### 7.1 Resources

```
GET    /v1/workspaces/:workspace_id
PATCH  /v1/workspaces/:workspace_id          # update settings (admin only)

GET    /v1/workspaces/:workspace_id/members
POST   /v1/workspaces/:workspace_id/members  # invite member (admin)
PATCH  /v1/workspaces/:workspace_id/members/:user_id  # update role (admin)
DELETE /v1/workspaces/:workspace_id/members/:user_id  # remove member (admin)

GET    /v1/workspaces/:workspace_id/policies
POST   /v1/workspaces/:workspace_id/policies        # create policy (owner)
GET    /v1/workspaces/:workspace_id/policies/:id
PATCH  /v1/workspaces/:workspace_id/policies/:id    # update policy (owner)

GET    /v1/workspaces/:workspace_id/secrets          # list secret names only, không có value
POST   /v1/workspaces/:workspace_id/secrets          # create binding (owner/admin)
DELETE /v1/workspaces/:workspace_id/secrets/:id      # delete binding (owner/admin)
```

### 7.2 Response shape: Workspace

```json
{
  "id": "<UUID>",
  "slug": "<string>",
  "display_name": "<string>",
  "plan": "team",
  "deployment_mode": "cloud",
  "owner_id": "<UUID>",
  "created_at": "<ISO 8601>",
  "settings": { }
}
```

**Forbidden:** Không có endpoint `GET /v1/workspaces/:id/secrets/:id/value` — giá trị secret không bao giờ được expose qua API.

---

## 8. Repo và Snapshot APIs

```
GET    /v1/workspaces/:workspace_id/repos
POST   /v1/workspaces/:workspace_id/repos/snapshots   # trigger snapshot (async, 202)
GET    /v1/workspaces/:workspace_id/repos/snapshots
GET    /v1/workspaces/:workspace_id/repos/snapshots/:snapshot_id
```

### 8.1 POST /v1/workspaces/:workspace_id/repos/snapshots

Request:
```json
{
  "source_url": "https://github.com/org/repo",
  "commit_sha": "<string>",
  "branch": "<string | null>"
}
```

Response `202 Accepted`:
```json
{
  "data": {
    "accepted": true,
    "resource_type": "repo_snapshot",
    "resource_id": "<UUID>",
    "current_status": "pending"
  }
}
```

### 8.2 Response shape: RepoSnapshot

```json
{
  "id": "<UUID>",
  "workspace_id": "<UUID>",
  "source_url": "<string>",
  "commit_sha": "<string>",
  "branch": "<string | null>",
  "size_bytes": 0,
  "created_at": "<ISO 8601>",
  "created_by_id": "<UUID>"
}
```

---

## 9. Task APIs

### 9.1 Endpoints

```
GET    /v1/workspaces/:workspace_id/tasks
POST   /v1/workspaces/:workspace_id/tasks              # submit task (async, 202)
GET    /v1/workspaces/:workspace_id/tasks/:task_id
POST   /v1/workspaces/:workspace_id/tasks/:task_id/cancel  # cancel task (async, 202)
```

**Forbidden endpoints:**
- `PUT /v1/tasks/:id` — không có "update task" generic.
- `POST /v1/tasks/:id/resume` — Run failed không resume (doc 05).
- `DELETE /v1/tasks/:id` — Task không được xóa, chỉ archive.
- `POST /v1/tasks/:id/status` — Không có endpoint set status trực tiếp.

### 9.2 POST /v1/workspaces/:workspace_id/tasks

Request:
```json
{
  "title": "<string>",
  "description": "<string | null>",
  "task_type": "coding",
  "input_config": {
    "repo_snapshot_id": "<UUID | null>",
    "prompt": "<string>",
    "params": { }
  },
  "policy_id": "<UUID | null>",
  "parent_task_id": "<UUID | null>"
}
```

Response `202 Accepted` — Task chuyển sang `pending`, event `task.submitted` được phát.

**State machine check:** Nếu `parent_task_id` tồn tại nhưng parent task đang `cancelled` hoặc `failed`, trả `409 STATE_CONFLICT`.

### 9.3 POST /v1/workspaces/:workspace_id/tasks/:task_id/cancel

Request body: `{ "reason": "<string | null>" }`

Response `202 Accepted` — Task chuyển sang `cancelled`, cascade bắt đầu.

**State machine check:** Nếu task đang `completed` hoặc `archived`, trả `409 STATE_CONFLICT` với `conflict_with_state`.

### 9.4 Response shape: Task

```json
{
  "id": "<UUID>",
  "workspace_id": "<UUID>",
  "title": "<string>",
  "description": "<string | null>",
  "task_type": "coding",
  "task_status": "running",
  "input_config": { },
  "repo_snapshot_id": "<UUID | null>",
  "policy_id": "<UUID | null>",
  "parent_task_id": "<UUID | null>",
  "created_by_id": "<UUID>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>"
}
```

---

## 10. Run APIs

### 10.1 Endpoints

```
GET  /v1/workspaces/:workspace_id/tasks/:task_id/runs
GET  /v1/workspaces/:workspace_id/tasks/:task_id/runs/:run_id
POST /v1/workspaces/:workspace_id/tasks/:task_id/runs/:run_id/cancel
POST /v1/workspaces/:workspace_id/tasks/:task_id/retry   # tạo Run mới (async, 202)
```

**Forbidden endpoints:**
- `POST /v1/runs/:id/resume` — Run failed không resume.
- `PATCH /v1/runs/:id` — run_config là immutable sau khi queued.

### 10.2 POST /v1/tasks/:task_id/retry

Tạo Run mới trên Task đang `failed`. Task phải được chuyển lại `pending` trước khi Run mới được tạo.

**State machine check:** Chỉ cho phép khi Task đang `failed`. Mọi trạng thái khác trả `409 STATE_CONFLICT`.

### 10.3 Response shape: Run

```json
{
  "id": "<UUID>",
  "task_id": "<UUID>",
  "workspace_id": "<UUID>",
  "run_status": "running",
  "trigger_type": "manual",
  "triggered_by_id": "<UUID | null>",
  "started_at": "<ISO 8601 | null>",
  "completed_at": "<ISO 8601 | null>",
  "duration_ms": null,
  "run_config": { },
  "error_summary": null,
  "created_at": "<ISO 8601>"
}
```

---

## 11. Step và AgentInvocation Query APIs

Đây là **query-only** surface — không có command endpoint ở đây ngoài human response.

```
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id/agent-invocations
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id/agent-invocations/:invocation_id

POST /v1/workspaces/:workspace_id/agent-invocations/:invocation_id/respond
     # human respond khi agent đang waiting_human (202)
```

### 11.1 POST /agent-invocations/:id/respond

Chỉ hợp lệ khi AgentInvocation đang `waiting_human`.

Request:
```json
{
  "content": "<string>",
  "attachments": [ ]
}
```

**State machine check:** Nếu invocation không ở trạng thái `waiting_human`, trả `409 STATE_CONFLICT`.

### 11.2 Response shape: Step

```json
{
  "id": "<UUID>",
  "run_id": "<UUID>",
  "step_type": "agent_invocation",
  "step_status": "completed",
  "sequence": 1,
  "parent_step_id": null,
  "input_snapshot": { },
  "output_snapshot": { },
  "started_at": "<ISO 8601>",
  "completed_at": "<ISO 8601>",
  "error_detail": null
}
```

---

## 12. Sandbox và Terminal APIs

### 12.1 Sandbox query

```
GET /v1/workspaces/:workspace_id/sandboxes/:sandbox_id
GET /v1/workspaces/:workspace_id/agent-invocations/:invocation_id/sandbox
```

**Forbidden:** Không có command endpoint trực tiếp vào Sandbox từ API public. Orchestrator là actor duy nhất gửi terminate signal (qua internal channel, không qua public API).

### 12.2 Terminal/session attach

Terminal là interactive session — chỉ dành cho trường hợp người dùng cần observe hoặc interact trực tiếp với execution environment trong giới hạn policy.

```
POST /v1/workspaces/:workspace_id/runs/:run_id/terminal    # request terminal session (202)
GET  /v1/workspaces/:workspace_id/terminal-sessions/:session_id
DELETE /v1/workspaces/:workspace_id/terminal-sessions/:session_id  # detach
```

Terminal session là **read + limited-input only** theo mặc định. Policy có thể disable terminal hoàn toàn cho workspace.

**Permission checkpoint:** `attach terminal` yêu cầu ít nhất `editor` role và policy cho phép.

### 12.3 Response shape: Sandbox

```json
{
  "id": "<UUID>",
  "agent_invocation_id": "<UUID>",
  "workspace_id": "<UUID>",
  "sandbox_type": "container",
  "sandbox_status": "executing",
  "resource_limits": { },
  "started_at": "<ISO 8601>",
  "terminated_at": null,
  "termination_reason": null
}
```

---

## 13. Artifact APIs

```
GET    /v1/workspaces/:workspace_id/artifacts
GET    /v1/workspaces/:workspace_id/artifacts/:artifact_id
GET    /v1/workspaces/:workspace_id/runs/:run_id/artifacts
GET    /v1/workspaces/:workspace_id/artifacts/:artifact_id/download   # redirect to signed URL
POST   /v1/workspaces/:workspace_id/artifacts/:artifact_id/archive    # manual archive (admin)
```

**Forbidden endpoints:**
- `DELETE /v1/artifacts/:id` — Artifact không được xóa.
- `PUT /v1/artifacts/:id` — Artifact `ready` là immutable.
- `PATCH /v1/artifacts/:id/status` — Không set status trực tiếp.

### 13.1 GET /artifacts/:id/download

Trả `302 Redirect` đến signed URL có TTL ngắn (15 phút). Không stream artifact qua API server.

**Permission checkpoint:** Artifact với `metadata.sensitive: true` yêu cầu `editor` role tối thiểu và policy không block.

### 13.2 Response shape: Artifact

```json
{
  "id": "<UUID>",
  "workspace_id": "<UUID>",
  "run_id": "<UUID>",
  "step_id": "<UUID | null>",
  "artifact_type": "file",
  "artifact_status": "ready",
  "name": "<string>",
  "size_bytes": 0,
  "checksum": "<SHA-256>",
  "lineage": [ ],
  "metadata": { },
  "created_at": "<ISO 8601>"
}
```

**Không expose `storage_ref` trong response** — đó là internal reference, không phải URL cho client.

---

## 14. Approval APIs

```
GET  /v1/workspaces/:workspace_id/approvals
GET  /v1/workspaces/:workspace_id/approvals/:approval_id
POST /v1/workspaces/:workspace_id/approvals/:approval_id/approve
POST /v1/workspaces/:workspace_id/approvals/:approval_id/reject
```

### 14.1 POST /approvals/:id/approve

Request: `{ "comment": "<string | null>" }`

**State machine checks:**
- Nếu approval không ở trạng thái `pending`: `409 STATE_CONFLICT`.
- Nếu actor không có `approver_role` được chỉ định: `403 FORBIDDEN`.
- Nếu approval đã `timed_out`: `409 STATE_CONFLICT`.

Response `202 Accepted` — event `approval.approved` được phát, entity cha tiếp tục lifecycle.

### 14.2 Response shape: Approval

```json
{
  "id": "<UUID>",
  "target_type": "step",
  "target_id": "<UUID>",
  "requested_by": "orchestrator",
  "requested_at": "<ISO 8601>",
  "approver_role": "editor",
  "prompt": "<string>",
  "timeout_at": "<ISO 8601>",
  "decision": "pending",
  "decided_by_id": null,
  "decided_at": null
}
```

---

## 15. Event/Timeline Subscription APIs

### 15.1 Pull API — history và polling

```
GET /v1/workspaces/:workspace_id/events
    ?aggregate_type=run&aggregate_id=<UUID>
    &after=<cursor>
    &limit=50

GET /v1/workspaces/:workspace_id/tasks/:task_id/timeline
GET /v1/workspaces/:workspace_id/runs/:run_id/timeline
```

Timeline endpoint trả toàn bộ event của một Run/Task theo thứ tự `occurred_at`, đã được flatten và enriched với context. Đây là endpoint chính cho UI timeline view.

### 15.2 Realtime — Server-Sent Events (SSE)

```
GET /v1/workspaces/:workspace_id/events/stream
    ?task_id=<UUID>        # subscribe theo task
    ?run_id=<UUID>         # subscribe theo run
    ?workspace_id=<UUID>   # subscribe toàn workspace (admin only)
```

SSE được chọn thay WebSocket vì:
- Unidirectional (server → client): phù hợp với event fact model.
- Native HTTP/2 multiplexing.
- Dễ reconnect với `Last-Event-ID`.

**Subscription scopes:**
- `run_id`: nhận tất cả event trong một Run (bao gồm Step, AgentInvocation, Sandbox, Artifact).
- `task_id`: nhận tất cả event trong một Task (tất cả Run của Task đó).
- `workspace_id`: nhận tất cả event trong workspace — chỉ `admin` mới được.

**SSE event format:**

```
id: <event_id>
event: <event_type>
data: <JSON event envelope>

```

Client dùng `Last-Event-ID` header khi reconnect để tiếp tục từ vị trí cuối.

---

## 16. Mapping từ Command sang State Transition và Event

| API Command | State Transition | Event bắt buộc |
|---|---|---|
| `POST /tasks` | Task: `→ pending` | `task.submitted` |
| `POST /tasks/:id/cancel` | Task: `→ cancelled` (cascade) | `task.cancelled` + cascade |
| `POST /tasks/:id/retry` | Task: `failed → pending`, Run: `→ queued` | `run.queued` |
| `POST /runs/:id/cancel` | Run: `→ cancelled` (cascade) | `run.cancelled` + cascade |
| `POST /approvals/:id/approve` | Approval: `pending → approved`, entity cha resume | `approval.approved` + entity resume event |
| `POST /approvals/:id/reject` | Approval: `pending → rejected`, entity cha cancelled | `approval.rejected` + entity cancel event |
| `POST /agent-invocations/:id/respond` | AgentInvocation: `waiting_human → running` | `agent_invocation.human_responded` |
| `POST /repos/snapshots` | RepoSnapshot: `→ pending` | (internal snapshot event) |
| `POST /artifacts/:id/archive` | Artifact: `ready → archived` | `artifact.archived` |

---

## 17. Forbidden APIs

Danh sách endpoint **không được tồn tại** — nếu xuất hiện trong implementation, đó là dấu hiệu kiến trúc đang bị lệch:

| Forbidden endpoint | Lý do |
|---|---|
| `POST /runs/:id/resume` | Run failed không resume — doc 05 |
| `DELETE /artifacts/:id` | Artifact không được xóa — doc 04 |
| `PUT /artifacts/:id` | Artifact ready là immutable — doc 04 |
| `PATCH /tasks/:id/status` | Không set status trực tiếp — state machine là owner |
| `PATCH /runs/:id/status` | Tương tự |
| `PATCH /runs/:id/run_config` | run_config immutable sau khi queued — doc 05 |
| `POST /tasks/:id/do-everything` | UI convenience endpoint — BFF layer giải quyết |
| `GET /secrets/:id/value` | Secret value không bao giờ exposed — doc 04 |
| `POST /sandboxes/:id/terminate` | Public API không direct-terminate sandbox — doc 02 |
| `POST /sandboxes/:id/command` | UI không gọi sandbox trực tiếp — doc 02 |
| `PUT /events/:id` | Event là immutable — doc 06 |
| `DELETE /events/:id` | Event là immutable — doc 06 |

---

## 18. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| `input_config` schema theo từng `task_type` | Phụ thuộc vào từng agent definition |
| Rate limiting rules cụ thể (per workspace, per user) | Phụ thuộc vào plan/deployment topology (doc 13) |
| Signed URL TTL và storage provider | Phụ thuộc vào Storage layer và deployment mode |
| SSE reconnect và backpressure semantics | Phụ thuộc vào infrastructure (doc 13) |
| Payload schema chi tiết của từng event type | Cần khóa song song với implementation |
| BFF layer design | Không thuộc về API contracts lõi |

---

## 19. Bước tiếp theo

Sau doc 07, có hai con đường song song có thể tiếp tục:

- **08 — Sandbox Security Model**: khóa isolation, policy enforcement, network egress, secret injection.
- **09 — Permission Model**: khóa role/policy resolution logic chi tiết, bổ sung cho permission checkpoints đã liệt kê trong doc này.

Thứ tự đề xuất: **08 trước** vì Sandbox là điểm rủi ro cao nhất và nhiều invariant trong 02, 04, 05 đã tham chiếu đến nó mà chưa khóa chi tiết.
