# 04 — Core Domain Model

**Status:** Draft v1.0
**Dependencies:** 00 Product Vision, 01 Goals & Non-goals, 02 Invariants, 03 Bounded Contexts
**Document objective:** Lock down all core business objects, their relationships, aggregate boundaries, and sources of truth — forming the foundation for DB schemas, API schemas, event schemas, and state machines.

---

## 1. Naming Conventions

| Rule | Rationale |
|---|---|
| PascalCase for entities | Distinguishes them from fields/attributes |
| snake_case for fields | Consistent with DB and JSON conventions |
| No abbreviations in entity names | `AgentInvocation` not `AgentInvoc` |
| Field names use `_at` for timestamps | `created_at`, `started_at`, `completed_at` |
| Field names use `_id` for foreign keys | `workspace_id`, `task_id` |
| Field names use `_status` for state | `run_status`, `artifact_status` |

---

## 2. Entity Map Overview

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

## 3. Detailed Entities

---

### 3.1 User

A user identity in the system. Not bound to any specific workspace.

**Source of truth:** Auth layer / identity store

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | Primary key |
| `email` | string | ✓ | Globally unique |
| `display_name` | string | ✓ | Display name |
| `auth_provider` | enum | ✓ | `local`, `google`, `github`, `sso` |
| `auth_provider_id` | string | | External provider ID |
| `created_at` | timestamp | ✓ | |
| `last_active_at` | timestamp | | |

**Relationships:** A User joins a Workspace through the `Member` entity.

---

### 3.2 Workspace

The highest-level organizational unit. All resources belong to a specific Workspace.

**Source of truth:** Workspace service

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | Primary key |
| `slug` | string | ✓ | URL-safe, globally unique |
| `display_name` | string | ✓ | |
| `plan` | enum | ✓ | `personal`, `team`, `enterprise` |
| `deployment_mode` | enum | ✓ | `local`, `cloud`, `hybrid` |
| `owner_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |
| `settings` | JSONB | | Workspace-level configuration |

**Aggregate root:** Workspace is the aggregate root for Member, Policy, and SecretBinding.

---

### 3.3 Member

Links a User to a Workspace, carrying role and permissions.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `user_id` | UUID → User | ✓ | |
| `role` | enum | ✓ | `owner`, `admin`, `editor`, `viewer` |
| `joined_at` | timestamp | ✓ | |
| `invited_by_id` | UUID → User | | |

**Constraint:** `(workspace_id, user_id)` is unique.

---

### 3.4 Policy

Rules that govern behavior within a Workspace: permissions, sandbox limits, model access, egress rules.

**Source of truth:** Permission/Policy service

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `name` | string | ✓ | |
| `scope` | enum | ✓ | `workspace`, `task_type`, `agent`, `tool` |
| `rules` | JSONB | ✓ | List of rules following a standardized schema |
| `is_default` | boolean | ✓ | |
| `created_at` | timestamp | ✓ | |

**Note:** Policies must not be resolved at the UI or Tool layer. Only the Orchestrator and Sandbox are allowed to read and enforce Policies.

---

### 3.5 SecretBinding

A mechanism to inject secrets into a Sandbox without exposing raw values to any other layer.

**Source of truth:** Secret store (Vault / KMS depending on deployment mode)

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `name` | string | ✓ | Alias used in run config, e.g., `OPENAI_KEY` |
| `secret_ref` | string | ✓ | Pointer to the secret store, not the actual value |
| `scope` | enum | ✓ | `workspace`, `task`, `agent` |
| `created_by_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |

**Invariant:** Secret values must not be stored in the domain model. Only `secret_ref` is stored.

---

### 3.6 RepoSnapshot

A point-in-time snapshot of a Git repository — a fixed input for a Task/Run that ensures reproducibility.

**Source of truth:** Storage layer

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `source_url` | string | ✓ | Original repo URL |
| `commit_sha` | string | ✓ | SHA of the snapshotted commit |
| `branch` | string | | |
| `snapshot_storage_ref` | string | ✓ | Pointer to the snapshot file in storage |
| `size_bytes` | int | | |
| `created_at` | timestamp | ✓ | |
| `created_by_id` | UUID → User | ✓ | |

---

### 3.7 Task

A unit of work created by a user. A Task declares "what needs to be done," not "how to execute it."

**Source of truth:** Orchestrator

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `title` | string | ✓ | |
| `description` | text | | |
| `task_type` | enum | ✓ | `coding`, `research`, `analysis`, `operation`, `custom` |
| `task_status` | enum | ✓ | See State Machine |
| `input_config` | JSONB | ✓ | Input parameters: repo, prompt, params |
| `repo_snapshot_id` | UUID → RepoSnapshot | | If the task involves code |
| `policy_id` | UUID → Policy | | Policy applied to this task |
| `created_by_id` | UUID → User | ✓ | |
| `created_at` | timestamp | ✓ | |
| `updated_at` | timestamp | ✓ | |
| `parent_task_id` | UUID → Task | | If this is a subtask |

**Aggregate root:** Task is the aggregate root for Run.

---

### 3.8 Run

A single execution of a Task. A Task may have multiple Runs (retry, re-run, experimental run).

**Source of truth:** Orchestrator

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `task_id` | UUID → Task | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized for fast queries |
| `run_status` | enum | ✓ | See State Machine |
| `trigger_type` | enum | ✓ | `manual`, `scheduled`, `event`, `approval` |
| `triggered_by_id` | UUID → User | | Null if triggered by event/schedule |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `duration_ms` | int | | |
| `run_config` | JSONB | ✓ | Snapshot of configuration at runtime (immutable after started) |
| `error_summary` | text | | |
| `created_at` | timestamp | ✓ | |

**Invariant:** `run_config` must not be modified after the Run transitions to `running`.
**Invariant:** Every Run must be reproducible from `run_config` + `repo_snapshot_id` + artifact lineage.

---

### 3.9 Step

The smallest traceable unit of execution within a Run. Includes agent invocations, tool calls, approval gates, and logic steps.

**Source of truth:** Orchestrator

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `run_id` | UUID → Run | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `step_type` | enum | ✓ | `agent_invocation`, `tool_call`, `approval_gate`, `condition`, `transform` |
| `step_status` | enum | ✓ | See State Machine |
| `sequence` | int | ✓ | Order within the Run |
| `parent_step_id` | UUID → Step | | If this is a sub-step |
| `input_snapshot` | JSONB | | Input at execution time |
| `output_snapshot` | JSONB | | Captured output |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `error_detail` | JSONB | | |

---

### 3.10 AgentInvocation

A single call into the agent runtime. Separated from Step because a single Step may spawn multiple AgentInvocations (multi-turn, retry, fan-out).

**Source of truth:** Agent Engine

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `step_id` | UUID → Step | ✓ | |
| `run_id` | UUID → Run | ✓ | Denormalized |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `agent_id` | string | ✓ | Identifier for the agent definition |
| `model_id` | string | ✓ | Model used (e.g., `claude-3-7-sonnet`) |
| `invocation_status` | enum | ✓ | See State Machine |
| `prompt_tokens` | int | | |
| `completion_tokens` | int | | |
| `total_cost_usd` | decimal | | |
| `input_messages` | JSONB | | Full snapshot of input messages |
| `output_messages` | JSONB | | Full snapshot of output |
| `tool_calls` | JSONB | | List of tool calls generated |
| `started_at` | timestamp | | |
| `completed_at` | timestamp | | |
| `error_detail` | JSONB | | |

**Invariant:** The Agent Engine does not own artifacts. Artifacts are created only by the Artifact service after an AgentInvocation completes.

---

### 3.11 Sandbox

An isolated execution environment for an AgentInvocation or a group of tool calls.

**Source of truth:** Execution/Sandbox layer

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `agent_invocation_id` | UUID → AgentInvocation | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | Denormalized |
| `sandbox_type` | enum | ✓ | `container`, `vm`, `wasm`, `subprocess` |
| `sandbox_status` | enum | ✓ | See State Machine |
| `policy_snapshot` | JSONB | ✓ | Policy applied at sandbox creation time (immutable) |
| `resource_limits` | JSONB | ✓ | CPU, memory, network, timeout |
| `network_egress_policy` | JSONB | ✓ | Network whitelist/blacklist |
| `started_at` | timestamp | | |
| `terminated_at` | timestamp | | |
| `termination_reason` | enum | | `completed`, `timeout`, `policy_violation`, `error`, `manual` |

**Invariant:** Sandboxes are ephemeral — internal state must not persist across invocations.
**Invariant:** The UI layer must not call Sandbox directly.

---

### 3.12 Artifact

A valuable output produced by a Run/Step/AgentInvocation. Represents a long-lived result.

**Source of truth:** Artifact service / Storage layer

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `run_id` | UUID → Run | ✓ | |
| `step_id` | UUID → Step | | Null if the artifact belongs to the entire Run |
| `artifact_type` | enum | ✓ | `file`, `code_patch`, `report`, `dataset`, `log`, `structured_data` |
| `artifact_status` | enum | ✓ | `pending`, `writing`, `ready`, `failed`, `archived` |
| `name` | string | ✓ | |
| `storage_ref` | string | ✓ | Pointer to storage (not a direct URL) |
| `size_bytes` | int | | |
| `checksum` | string | ✓ | SHA-256 of the content |
| `lineage` | JSONB | | List of parent `artifact_id` values (if this is a derived artifact) |
| `metadata` | JSONB | | Additional information specific to the artifact_type |
| `created_at` | timestamp | ✓ | |
| `created_by_invocation_id` | UUID → AgentInvocation | | |

**Invariant:** Artifacts must not be deleted — they may only be archived.
**Invariant:** A `ready` Artifact's `checksum` must not be modified.

---

### 3.13 Event

An append-only log of all significant state changes in the system.

**Source of truth:** Event store (append-only)

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | ✓ | |
| `workspace_id` | UUID → Workspace | ✓ | |
| `event_type` | string | ✓ | e.g., `task.created`, `run.started`, `artifact.ready` |
| `aggregate_type` | enum | ✓ | `workspace`, `task`, `run`, `step`, `agent_invocation`, `artifact` |
| `aggregate_id` | UUID | ✓ | ID of the entity that emitted the event |
| `payload` | JSONB | ✓ | Event data |
| `correlation_id` | UUID | ✓ | Links events within the same Run |
| `causation_id` | UUID | | ID of the event that caused this one |
| `actor_type` | enum | ✓ | `user`, `agent`, `system`, `scheduler` |
| `actor_id` | string | ✓ | ID of the actor |
| `occurred_at` | timestamp | ✓ | |
| `schema_version` | string | ✓ | e.g., `1.0` |

**Invariant:** Events must not be updated or deleted after being written.
**Invariant:** All long-lived state changes must have a corresponding Event.

---

## 4. Aggregate Boundaries

| Aggregate Root | Owned Entities | Must Not Own |
|---|---|---|
| Workspace | Member, Policy, SecretBinding | Task (separate), User (global) |
| Task | Run | Step (belongs to Run), Artifact (belongs to Run) |
| Run | Step, Artifact | AgentInvocation (belongs to Step) |
| Step | AgentInvocation | Sandbox (belongs to AgentInvocation) |
| AgentInvocation | Sandbox | Artifact (owned by Artifact service) |

---

## 5. Consolidated Relationships

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

Event ← (emitted by any entity)
```

---

## 6. Source of Truth by Layer

| Entity | Responsible Layer |
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

## 7. Intentionally Deferred Decisions

| Item | Reason for Deferral |
|---|---|
| Specific schema for `policy.rules` | Requires locking down the Permission Model (doc 09) first |
| Specific schema for `input_config` per `task_type` | Requires locking down API Contracts (doc 07) first |
| Storage mechanism for AgentInvocation `input_messages` / `output_messages` | Depends on storage strategy and privacy model |
| Detailed `artifact.lineage` schema | Requires locking down the Artifact Lineage Model (doc 10) first |
| `sandbox.network_egress_policy` schema | Requires locking down the Sandbox Security Model (doc 08) first |

---

## 8. Next Steps

The next document to be written is **05 — State Machines**, covering:

- Task lifecycle
- Run lifecycle
- Step lifecycle
- AgentInvocation lifecycle
- Sandbox lifecycle
- Artifact lifecycle
- Approval flow

All of these are directly based on the entities defined in this document.
