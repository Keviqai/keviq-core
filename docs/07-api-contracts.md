# 07 — API Contracts

**Status:** Draft v1.0
**Dependencies:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts
**Objective:** Lock down the public control surface of the entire system — the API is the layer through which humans and clients interact with the state machine and event model, not the layer that creates them.

---

## 1. API Principles

### 1.1 API Is a Control/Query Surface — Not the Source of Truth

The state machine (doc 05) is the source of truth for lifecycle. The event store (doc 06) is the source of truth for history. The API does only 3 things:

1. **Create intent** — submit task, cancel task, approve, attach repo.
2. **Query state** — get task, list runs, get artifact.
3. **Human intervention** — approve, reject, respond to an agent waiting for human input.

The API must not do anything beyond these 3 functions.

### 1.2 Command APIs Return Acknowledgement — Not the Final Result

When a command is accepted, the API returns `202 Accepted` with a resource reference. The final result arrives via the event stream or polling query. The API must not block waiting for the Orchestrator to complete before returning the response.

### 1.3 Every Mutation Must Map to a State Transition + Event

No endpoint may change state without a corresponding valid state transition in doc 05 and a corresponding mandatory event in doc 06. If a mutation has no state transition, it must not exist as an endpoint.

### 1.4 UI Convenience Must Not Produce Architecturally Incorrect APIs

If the UI needs something that a properly architected API does not provide, the solution is to build a BFF (Backend for Frontend) layer — not to hack core endpoints.

---

## 2. Versioning and Compatibility Policy

### 2.1 URL Versioning

All endpoints begin with `/v1/`. No endpoint exists without a version prefix.

### 2.2 Backward Compatibility

Within the same major version (`v1`):
- Adding a field to a response: **allowed** (clients must be tolerant of unknown fields).
- Adding an optional field to a request: **allowed**.
- Renaming a field: **not allowed** — create a new field, deprecate the old one.
- Removing a field: **not allowed** in v1 — only permitted when bumping to v2.
- Changing a field's data type: **not allowed**.

### 2.3 Deprecation Policy

- Deprecated fields/endpoints must include headers `Deprecation: true` and `Sunset: <date>`.
- Minimum time from deprecated to removed: **60 days**.
- During the deprecation period, the field continues to function normally.

### 2.4 Breaking Changes

Breaking changes are only permitted when bumping the major version (`v2`). `/v1` and `/v2` must run in parallel for a minimum of **90 days** after v2 is released.

---

## 3. Common Request/Response Envelope

### 3.1 Standard Response Envelope

Every response is wrapped in the following envelope:

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

- On success: `data` contains the payload, `error` is `null`.
- On error: `data` is `null`, `error` contains the error object (see section 4).
- `meta` is always present in every response.

### 3.2 Pagination

List endpoints use cursor-based pagination:

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

Offset-based pagination is not used. The cursor is opaque — clients must not parse it.

### 3.3 Command Response (202 Accepted)

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

The `correlation_id` here is the correlation_id of the event that will be emitted — clients use it to subscribe to the event stream.

---

## 4. Error Model

Every error response uses the following structure:

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

### 4.1 Standard HTTP Status Codes

| HTTP Status | When to Use |
|---|---|
| `200 OK` | Successful query |
| `201 Created` | Resource created synchronously (rare) |
| `202 Accepted` | Command accepted, processing asynchronously |
| `400 Bad Request` | Malformed request, validation failure |
| `401 Unauthorized` | Not authenticated |
| `403 Forbidden` | Authenticated but lacking permission |
| `404 Not Found` | Resource does not exist or is not visible within the workspace |
| `409 Conflict` | Mutation violates the current state machine |
| `422 Unprocessable` | Request is syntactically valid but cannot be executed due to business logic |
| `429 Too Many Requests` | Rate limit |
| `500 Internal Server Error` | Unexpected server error |
| `503 Service Unavailable` | Service is temporarily unavailable |

### 4.2 Standard Error Codes

| `error_code` | HTTP | Description |
|---|---|---|
| `INVALID_REQUEST` | 400 | Validation failure |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Lacking permission |
| `NOT_FOUND` | 404 | Resource does not exist |
| `STATE_CONFLICT` | 409 | State machine violation — `conflict_with_state` contains the current state |
| `ALREADY_EXISTS` | 409 | Resource already exists (idempotency case) |
| `UNPROCESSABLE` | 422 | Business logic rejection |
| `RATE_LIMITED` | 429 | Rate limit |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Temporarily unavailable, `retryable: true` |

---

## 5. Idempotency Model

### 5.1 Command Endpoints Must Use `Idempotency-Key`

The following commands **require** the client to send the header `Idempotency-Key: <UUID>`:

- `POST /v1/tasks` (submit task)
- `POST /v1/tasks/:id/cancel`
- `POST /v1/runs/:id/cancel`
- `POST /v1/approvals/:id/approve`
- `POST /v1/approvals/:id/reject`
- `POST /v1/repos/snapshots` (trigger snapshot)

### 5.2 Idempotency-Key Scope

- Scope: `(workspace_id, actor_id, idempotency_key)`.
- TTL: 24 hours. After 24 hours, the same key may create a new resource.
- If a request with the same key has already been processed successfully: return the original response with `200 OK` (not `202`), along with the header `Idempotency-Replayed: true`.
- If a request with the same key is currently being processed: return `409 Conflict` with `error_code: ALREADY_EXISTS`.
- If a request with the same key previously failed: allow retry with the same key.

---

## 6. Auth and Permission Checkpoints

Each endpoint is associated with a specific permission point. Permissions are resolved by the Permission service based on `Member.role` and the Workspace `Policy` (detailed in doc 09).

| Action | Minimum Role | Policy Override |
|---|---|---|
| Submit task | `editor` | Policy can restrict by `task_type` |
| Cancel task | `editor` (owner) or `admin` | |
| Cancel another user's task | `admin` | |
| Approve/reject | `editor` with the designated approver role | Approval request specifies `approver_role` |
| Attach repo | `editor` | |
| Read task/run/artifact | `viewer` | |
| Read artifact with sensitive flag | `editor` | Policy can restrict |
| Attach terminal/session | `editor` | Policy can disable entirely |
| Admin workspace settings | `admin` | |
| Create/edit Policy | `owner` | |
| Manage secrets | `owner` or `admin` | |

**Invariant from doc 02:** Permissions must not be resolved at the UI layer. The API layer forwards the request with identity to the Permission service. The Permission service makes the decision.

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

GET    /v1/workspaces/:workspace_id/secrets          # list secret names only, no values
POST   /v1/workspaces/:workspace_id/secrets          # create binding (owner/admin)
DELETE /v1/workspaces/:workspace_id/secrets/:id      # delete binding (owner/admin)
```

### 7.2 Response Shape: Workspace

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

**Forbidden:** There is no `GET /v1/workspaces/:id/secrets/:id/value` endpoint — secret values are never exposed via the API.

---

## 8. Repo and Snapshot APIs

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

### 8.2 Response Shape: RepoSnapshot

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
- `PUT /v1/tasks/:id` — there is no generic "update task".
- `POST /v1/tasks/:id/resume` — failed Runs are not resumed (doc 05).
- `DELETE /v1/tasks/:id` — Tasks cannot be deleted, only archived.
- `POST /v1/tasks/:id/status` — there is no endpoint to set status directly.

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

Response `202 Accepted` — Task transitions to `pending`, event `task.submitted` is emitted.

**State machine check:** If `parent_task_id` exists but the parent task is `cancelled` or `failed`, return `409 STATE_CONFLICT`.

### 9.3 POST /v1/workspaces/:workspace_id/tasks/:task_id/cancel

Request body: `{ "reason": "<string | null>" }`

Response `202 Accepted` — Task transitions to `cancelled`, cascade begins.

**State machine check:** If the task is `completed` or `archived`, return `409 STATE_CONFLICT` with `conflict_with_state`.

### 9.4 Response Shape: Task

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
POST /v1/workspaces/:workspace_id/tasks/:task_id/retry   # create new Run (async, 202)
```

**Forbidden endpoints:**
- `POST /v1/runs/:id/resume` — failed Runs are not resumed.
- `PATCH /v1/runs/:id` — run_config is immutable after queued.

### 10.2 POST /v1/tasks/:task_id/retry

Creates a new Run on a Task that is `failed`. The Task must transition back to `pending` before the new Run is created.

**State machine check:** Only allowed when the Task is `failed`. All other states return `409 STATE_CONFLICT`.

### 10.3 Response Shape: Run

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

## 11. Step and AgentInvocation Query APIs

These are **query-only** surfaces — there are no command endpoints here other than human response.

```
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id/agent-invocations
GET  /v1/workspaces/:workspace_id/runs/:run_id/steps/:step_id/agent-invocations/:invocation_id

POST /v1/workspaces/:workspace_id/agent-invocations/:invocation_id/respond
     # human response when agent is waiting_human (202)
```

### 11.1 POST /agent-invocations/:id/respond

Only valid when the AgentInvocation is in `waiting_human` state.

Request:
```json
{
  "content": "<string>",
  "attachments": [ ]
}
```

**State machine check:** If the invocation is not in `waiting_human` state, return `409 STATE_CONFLICT`.

### 11.2 Response Shape: Step

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

## 12. Sandbox and Terminal APIs

### 12.1 Sandbox Query

```
GET /v1/workspaces/:workspace_id/sandboxes/:sandbox_id
GET /v1/workspaces/:workspace_id/agent-invocations/:invocation_id/sandbox
```

**Forbidden:** There are no command endpoints directly into the Sandbox from the public API. The Orchestrator is the only actor that sends terminate signals (via internal channels, not the public API).

### 12.2 Terminal/Session Attach

A terminal is an interactive session — intended only for cases where a user needs to observe or interact directly with the execution environment within policy limits.

```
POST /v1/workspaces/:workspace_id/runs/:run_id/terminal    # request terminal session (202)
GET  /v1/workspaces/:workspace_id/terminal-sessions/:session_id
DELETE /v1/workspaces/:workspace_id/terminal-sessions/:session_id  # detach
```

A terminal session is **read + limited-input only** by default. Policy can disable terminal entirely for a workspace.

**Permission checkpoint:** `attach terminal` requires at minimum the `editor` role and policy permission.

### 12.3 Response Shape: Sandbox

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
- `DELETE /v1/artifacts/:id` — Artifacts cannot be deleted.
- `PUT /v1/artifacts/:id` — A `ready` Artifact is immutable.
- `PATCH /v1/artifacts/:id/status` — Status cannot be set directly.

### 13.1 GET /artifacts/:id/download

Returns `302 Redirect` to a signed URL with a short TTL (15 minutes). Artifacts are not streamed through the API server.

**Permission checkpoint:** Artifacts with `metadata.sensitive: true` require at minimum the `editor` role and policy must not block access.

### 13.2 Response Shape: Artifact

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

**Do not expose `storage_ref` in the response** — it is an internal reference, not a URL for clients.

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
- If the approval is not in `pending` state: `409 STATE_CONFLICT`.
- If the actor does not have the designated `approver_role`: `403 FORBIDDEN`.
- If the approval has already `timed_out`: `409 STATE_CONFLICT`.

Response `202 Accepted` — event `approval.approved` is emitted, the parent entity continues its lifecycle.

### 14.2 Response Shape: Approval

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

### 15.1 Pull API — History and Polling

```
GET /v1/workspaces/:workspace_id/events
    ?aggregate_type=run&aggregate_id=<UUID>
    &after=<cursor>
    &limit=50

GET /v1/workspaces/:workspace_id/tasks/:task_id/timeline
GET /v1/workspaces/:workspace_id/runs/:run_id/timeline
```

The timeline endpoint returns all events for a Run/Task in `occurred_at` order, flattened and enriched with context. This is the primary endpoint for the UI timeline view.

### 15.2 Realtime — Server-Sent Events (SSE)

```
GET /v1/workspaces/:workspace_id/events/stream
    ?task_id=<UUID>        # subscribe by task
    ?run_id=<UUID>         # subscribe by run
    ?workspace_id=<UUID>   # subscribe to entire workspace (admin only)
```

SSE was chosen over WebSocket because:
- Unidirectional (server → client): fits the event fact model.
- Native HTTP/2 multiplexing.
- Easy reconnection with `Last-Event-ID`.

**Subscription scopes:**
- `run_id`: receive all events within a Run (including Step, AgentInvocation, Sandbox, Artifact).
- `task_id`: receive all events within a Task (all Runs of that Task).
- `workspace_id`: receive all events within a workspace — `admin` only.

**SSE event format:**

```
id: <event_id>
event: <event_type>
data: <JSON event envelope>

```

Clients use the `Last-Event-ID` header on reconnect to resume from the last position.

---

## 16. Mapping from Command to State Transition and Event

| API Command | State Transition | Mandatory Event |
|---|---|---|
| `POST /tasks` | Task: `→ pending` | `task.submitted` |
| `POST /tasks/:id/cancel` | Task: `→ cancelled` (cascade) | `task.cancelled` + cascade |
| `POST /tasks/:id/retry` | Task: `failed → pending`, Run: `→ queued` | `run.queued` |
| `POST /runs/:id/cancel` | Run: `→ cancelled` (cascade) | `run.cancelled` + cascade |
| `POST /approvals/:id/approve` | Approval: `pending → approved`, parent entity resumes | `approval.approved` + entity resume event |
| `POST /approvals/:id/reject` | Approval: `pending → rejected`, parent entity cancelled | `approval.rejected` + entity cancel event |
| `POST /agent-invocations/:id/respond` | AgentInvocation: `waiting_human → running` | `agent_invocation.human_responded` |
| `POST /repos/snapshots` | RepoSnapshot: `→ pending` | (internal snapshot event) |
| `POST /artifacts/:id/archive` | Artifact: `ready → archived` | `artifact.archived` |

---

## 17. Forbidden APIs

List of endpoints that **must not exist** — if they appear in the implementation, it is a sign that the architecture is drifting:

| Forbidden Endpoint | Reason |
|---|---|
| `POST /runs/:id/resume` | Failed Runs are not resumed — doc 05 |
| `DELETE /artifacts/:id` | Artifacts cannot be deleted — doc 04 |
| `PUT /artifacts/:id` | A ready Artifact is immutable — doc 04 |
| `PATCH /tasks/:id/status` | Status cannot be set directly — the state machine is the owner |
| `PATCH /runs/:id/status` | Same as above |
| `PATCH /runs/:id/run_config` | run_config is immutable after queued — doc 05 |
| `POST /tasks/:id/do-everything` | UI convenience endpoint — BFF layer handles this |
| `GET /secrets/:id/value` | Secret values are never exposed — doc 04 |
| `POST /sandboxes/:id/terminate` | Public API does not directly terminate sandboxes — doc 02 |
| `POST /sandboxes/:id/command` | UI does not call sandboxes directly — doc 02 |
| `PUT /events/:id` | Events are immutable — doc 06 |
| `DELETE /events/:id` | Events are immutable — doc 06 |

---

## 18. Intentionally Deferred Decisions

| Item | Reason for Deferral |
|---|---|
| `input_config` schema per `task_type` | Depends on each agent definition |
| Specific rate limiting rules (per workspace, per user) | Depends on plan/deployment topology (doc 13) |
| Signed URL TTL and storage provider | Depends on the storage layer and deployment mode |
| SSE reconnect and backpressure semantics | Depends on infrastructure (doc 13) |
| Detailed payload schema for each event type | Needs to be locked down in parallel with implementation |
| BFF layer design | Does not belong in core API contracts |

---

## 19. Next Steps

After doc 07, there are two parallel paths that can continue:

- **08 — Sandbox Security Model**: locking down isolation, policy enforcement, network egress, secret injection.
- **09 — Permission Model**: locking down detailed role/policy resolution logic, supplementing the permission checkpoints listed in this document.

Recommended order: **08 first** because the Sandbox is the highest-risk area, and many invariants in 02, 04, 05 already reference it without detailed specifications.
