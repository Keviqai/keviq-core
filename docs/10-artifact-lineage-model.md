# 10 — Artifact Lineage Model

**Status:** Draft v1.0
**Dependencies:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model
**Goal:** Lock down how artifacts are created, inherited, derived, and reproduced — including root types, lineage edges, the reproducibility tuple, taint propagation, access rules by state/taint, and archive semantics.

---

## 1. Lineage Invariants

**L1 — Every artifact must have provenance.**
No artifact appears out of thin air. Every artifact, when created, must have a lineage root and an explicit provenance record. An artifact without provenance is invalid and must not be used as input.

**L2 — Lineage is append-only.**
Once a lineage edge is written, it must not be modified or deleted. If there is an error, write a correction record — do not modify the existing edge.

**L3 — Taint propagates along lineage, not in reverse.**
If a parent artifact is tainted → child artifacts may be tainted. A tainted child artifact does not taint its parent in reverse.

**L4 — A tainted artifact must not be used as input.**
Regardless of role, an artifact with `tainted = true` must not be attached to any Run/Step until it has been explicitly untainted by an actor with `artifact:untaint`.

**L5 — Reproducibility is an obligation, not a feature.**
Every `generated` artifact must have sufficient information to reproduce it from scratch: input snapshot, config, tool/model provenance, and lineage chain. If this information is incomplete, the artifact must not transition to `ready`.

**L6 — `artifact_service` is the only entity allowed to create and write artifacts.**
Agent Runtime, Orchestrator, and Sandbox must not write directly to storage. All artifact creation goes through the Artifact service. (Adheres to FD9 from doc 09.)

---

## 2. Artifact Root Types

Root type determines the original source of an artifact — the starting point of every lineage chain.

### 2.1 `upload`

An artifact directly uploaded by a user into the workspace. No parent artifact.

**Required provenance fields:**

| Field | Content |
|---|---|
| `root_type` | `upload` |
| `uploaded_by_id` | UUID → User |
| `uploaded_at` | timestamp |
| `original_filename` | string |
| `checksum` | SHA-256 of the original file |
| `workspace_id` | UUID |

**No Run/Step context** — uploads occur outside the task execution flow.

### 2.2 `repo_snapshot`

An artifact that is a snapshot of a Git repository at a specific commit. Typically used as input for coding tasks.

**Required provenance fields:**

| Field | Content |
|---|---|
| `root_type` | `repo_snapshot` |
| `source_url` | URL of the source repository |
| `commit_sha` | Full SHA |
| `branch` | Branch name (nullable) |
| `snapshot_tool` | Tool used to create the snapshot (name + version) |
| `snapshotted_by_id` | UUID → User or `system` |
| `snapshotted_at` | timestamp |

### 2.3 `generated`

An artifact produced by an AgentInvocation or Tool within a Run. This is the most common artifact type and has the strictest provenance requirements.

**Required provenance fields:**

| Field | Content |
|---|---|
| `root_type` | `generated` |
| `run_id` | UUID → Run |
| `step_id` | UUID → Step (nullable if run-level artifact) |
| `agent_invocation_id` | UUID → AgentInvocation (nullable if from a direct tool) |
| `tool_name` | Name of the tool that created the artifact (nullable if from agent output) |
| `model_id` | Model used (if from agent) |
| `model_version` | Full model version |
| `run_config_hash` | SHA-256 of `run.run_config` at execution time |
| `input_artifact_ids` | List of artifact_ids used as input |

### 2.4 `imported`

An artifact pulled in from an external source (API, external storage, webhook) — not directly uploaded by a user and not from a repository.

**Required provenance fields:**

| Field | Content |
|---|---|
| `root_type` | `imported` |
| `source_url` | Source URL |
| `import_tool` | Tool/integration used |
| `imported_by_id` | UUID → User or service account |
| `imported_at` | timestamp |
| `checksum` | SHA-256 of the imported content |

---

## 3. Lineage Edges

A lineage edge represents a directed relationship between a parent artifact and a child artifact. Every edge must be recorded when the child artifact is created.

### 3.1 Edge types

| Edge type | Meaning | Number of parents |
|---|---|---|
| `derived_from` | Child artifact was created directly from the content of the parent, without an explicit transformation. Example: agent reads file A and creates file B. | 1 |
| `transformed_from` | Child artifact is the result of a specific, describable transformation. Example: convert PDF → Markdown, compile code → binary. | 1 |
| `aggregated_from` | Child artifact is an aggregation of multiple parent artifacts. Example: a report synthesized from multiple analysis artifacts. | ≥ 2 |
| `promoted_from` | Child artifact is the selected/confirmed version from multiple candidate artifacts of the same type. Example: choosing best-of-3 drafts. | ≥ 1 |

### 3.2 Lineage edge record

```json
{
  "edge_id":          "<UUID>",
  "child_artifact_id": "<UUID>",
  "parent_artifact_id": "<UUID>",
  "edge_type":        "derived_from | transformed_from | aggregated_from | promoted_from",
  "run_id":           "<UUID>",
  "step_id":          "<UUID | null>",
  "created_at":       "<ISO 8601>",
  "transform_detail": { }
}
```

`transform_detail` is optional JSON describing the transformation: transform name, parameters, tool version — used for reproduction.

### 3.3 Lineage is a DAG, not a tree

A child artifact can have multiple parents (via `aggregated_from`). The lineage graph is a **Directed Acyclic Graph**. Cycles are invalid and must be rejected when the Artifact service writes an edge.

---

## 4. Reproducibility Tuple

Every `generated` artifact must contain sufficient information in the following **reproducibility tuple** to be re-executed and produce an artifact with identical content (deterministic) or equivalent content (semantic-equivalent if the model is non-deterministic).

```
Reproducibility Tuple = (
  input_snapshot,
  run_config,
  tool_provenance,
  model_provenance,
  lineage_chain
)
```

### 4.1 `input_snapshot`

All artifacts used as input, referenced by `artifact_id` + `checksum`. Not by URL, not by filename — must be an immutable reference.

### 4.2 `run_config`

Snapshot of `run.run_config` at the time the Run leaves `queued`. Stored as `run_config_hash` (SHA-256) in provenance. The full config is stored in the Run record and does not change.

### 4.3 `tool_provenance`

For each tool used in the Step that produced this artifact:
- `tool_name`
- `tool_version`
- `tool_config_hash`

### 4.4 `model_provenance`

For each model call in the AgentInvocation that produced this artifact:
- `model_id` (e.g., `claude-sonnet-4-20250514`)
- Full `model_version` (aliases like `latest` must not be used)
- `temperature`, `max_tokens`, and other sampling params
- `system_prompt_hash` (SHA-256 of the system prompt)

**Reason for not using aliases:** `latest` changes over time, invalidating the reproducibility tuple.

### 4.5 `lineage_chain`

An ordered list of all edges from root to the current artifact. Used to trace and verify the entire derivation chain.

### 4.6 Validate reproducibility before `artifact.ready`

The Artifact service must verify all 5 components of the tuple before transitioning an artifact to `ready`. If any component is missing, the artifact transitions to `failed` with `failure_reason: incomplete_provenance`.

---

## 5. Taint Propagation Rules

### 5.1 Sources of taint

An artifact becomes tainted when:

| Source | Trigger |
|---|---|
| **Security violation** | Sandbox violated policy while producing the artifact (from doc 08 violation cascade) |
| **Untrusted input** | Artifact was derived_from or transformed_from a tainted artifact |
| **Manual taint** | Admin/owner explicitly marks the artifact as tainted after security review |
| **Model anomaly** | Model Gateway detects output showing signs of prompt injection or malicious content |

### 5.2 Taint propagation by edge type

| Edge type | Propagation rule |
|---|---|
| `derived_from` | If parent is tainted → child is **automatically tainted** |
| `transformed_from` | If parent is tainted → child is **automatically tainted** |
| `aggregated_from` | If **any** parent is tainted → child is **automatically tainted** |
| `promoted_from` | If the selected artifact is tainted → child is tainted. If only rejected candidates are tainted → child is **not tainted** |

### 5.3 Taint is a property of the artifact, not the edge

Taint is stored on the artifact (`tainted: bool`, `taint_reason: string`, `tainted_at: timestamp`), not on the edge. This makes querying "is this artifact tainted" an O(1) operation, not a graph traversal.

However, **taint propagation checks must traverse the lineage graph** when a new artifact is created — the Artifact service must check all parents in the lineage before finalization.

### 5.4 Taint does not self-clear

Taint can only be removed when:
1. An actor with `artifact:untaint` explicitly calls the untaint API.
2. After untainting, `untaint_review_id` and `untainted_by_id` must be recorded in the artifact record.
3. Child artifacts of a tainted artifact are **not automatically untainted** when the parent is untainted — each child artifact must be reviewed and untainted individually.

### 5.5 Taint propagation event

When taint propagation occurs automatically, the Artifact service must emit:

```json
{
  "event_type": "artifact.tainted",
  "payload": {
    "artifact_id":           "<UUID>",
    "taint_reason":          "propagated_from_parent",
    "parent_artifact_id":    "<UUID>",
    "propagation_edge_type": "derived_from | transformed_from | aggregated_from"
  }
}
```

---

## 6. Access Rules by State, Taint, and Ownership

The role matrix in doc 09 is a necessary condition — not sufficient. Download and access permissions for artifacts also depend on state and taint status.

### 6.1 Full access matrix

| Artifact state | Tainted | `artifact:view` | `artifact:download` | `artifact:untaint` |
|---|---|---|---|---|
| `pending` | — | ✓ (owner/admin/editor) | ✗ | ✗ |
| `writing` | — | ✓ (owner/admin/editor) | ✗ | ✗ |
| `ready` | false | ✓ (viewer+) | ✓ (viewer+) | N/A |
| `ready` | true | ✓ (viewer+) | ✗ | ✓ (admin/owner only) |
| `failed` | — | ✓ (editor+) | ✓ (editor+, partial, debug only) | ✗ |
| `superseded` | false | ✓ (editor+) | ✓ (editor+) | N/A |
| `superseded` | true | ✓ (editor+) | ✗ | ✓ (admin/owner only) |
| `archived` | false | ✓ (editor+) | ✓ (editor+, cold latency) | N/A |
| `archived` | true | ✓ (editor+) | ✗ | ✓ (admin/owner only) |

**Additional rules:**
- A `failed` artifact with `partial_data_available: true` can only be downloaded by `editor+` and must include the `debug_only: true` flag in the response header.
- A tainted artifact **must never be used as input** for a Run/Step, regardless of role.
- An `archived` artifact can be downloaded but has a different SLA (cold storage retrieval latency depends on deployment mode).

### 6.2 Signed URL policy

All artifact downloads must go through a **signed URL** issued by the Artifact service. No direct storage URLs are exposed outside the Artifact service.

**Signed URL properties:**

| Property | Value |
|---|---|
| TTL | 15 minutes (default) / 1 hour (maximum, requires explicit request) |
| Scope | Bound to `artifact_id` + `user_id` + `workspace_id` |
| Single-use | Configurable per workspace (default: multi-use within TTL) |
| Revocable | Admin can revoke active signed URLs |
| Taint check | Artifact service checks taint status **at URL issuance time**, not at URL request time |

**Taint check at URL issuance:** If an artifact becomes tainted after the URL is issued but before the URL is used, the Artifact service must reject the request at the storage layer (not wait for TTL to expire).

---

## 7. Archive vs Delete Semantics

### 7.1 No delete

Artifacts are never deleted. They can only be archived. This is an invariant from doc 04 and doc 05.

**Reason:** Deleting an artifact breaks the lineage chain of child artifacts. Even `failed` artifacts must be retained for lineage debugging.

### 7.2 Archive semantics

Archive means moving the artifact to cold storage while its metadata remains queryable in the hot tier.

| After archive | Still possible | No longer possible |
|---|---|---|
| View metadata | ✓ | |
| Query lineage | ✓ | |
| Download | ✓ (with cold latency) | |
| Use as input for a new Run | ✓ (if not tainted) | |
| Revert back to `ready` | | ✗ |
| Untaint | ✓ (admin/owner) | |

### 7.3 Archive triggers

| Trigger | Condition |
|---|---|
| Scheduled archival | Artifact in `ready`/`superseded`/`failed` state after N days (configurable per workspace) |
| Manual archival | `editor+` calls the archive API |
| Run archival cascade | When a Run is archived, all artifacts associated with that Run are archived |
| Workspace retention policy | Workspace policy defines retention windows per `artifact_type` |

### 7.4 Archiving must not occur for artifacts that are inputs to active Runs

If an artifact is referenced by a Run with `run_status` in `[queued, preparing, running, waiting_approval, completing]`, archiving is blocked until the Run completes.

---

## 8. Lineage Query API (Minimum Surface Area)

This document does not lock down the implementation, but it does lock down the minimum surface area that the Artifact service must expose:

| Query | Meaning |
|---|---|
| `GET /artifacts/{id}/lineage/ancestors` | All ancestor artifacts (BFS/DFS up to root) |
| `GET /artifacts/{id}/lineage/descendants` | All descendant artifacts |
| `GET /artifacts/{id}/lineage/graph` | Full DAG subgraph around this artifact |
| `GET /artifacts/{id}/provenance` | Complete reproducibility tuple |
| `GET /artifacts/{id}/taint-status` | Taint status + taint propagation path |
| `POST /artifacts/{id}/untaint` | Untaint (requires `artifact:untaint`) |

---

## 9. Mapping to Event Contracts (doc 06)

All taint and lineage changes must have corresponding events:

| Lineage event | Event type | Key payload fields |
|---|---|---|
| Lineage edge recorded | `artifact.lineage_recorded` | `child_artifact_id`, `parent_artifact_id`, `edge_type` |
| Artifact automatically tainted | `artifact.tainted` | `artifact_id`, `taint_reason`, `parent_artifact_id` |
| Artifact manually tainted | `artifact.tainted` | `artifact_id`, `taint_reason: manual`, `tainted_by_id` |
| Artifact untainted | `artifact.untainted` | `artifact_id`, `untainted_by_id`, `untaint_review_id` |
| Signed URL issued | `artifact.url_issued` | `artifact_id`, `issued_to_user_id`, `expires_at` |
| Signed URL revoked | `artifact.url_revoked` | `artifact_id`, `revoked_by_id` |

---

## 10. Intentionally Deferred Decisions

| Item | Reason not yet locked |
|---|---|
| Specific retention windows per `artifact_type` | Depends on deployment topology (doc 13) and workspace contract |
| Cold storage implementation (S3, GCS, local volume) | Depends on deployment mode — local vs cloud vs hybrid |
| Semantic equivalence definition for non-deterministic reproduction | Needed when implementing reproducibility verification; complex and varies by model type |
| Cross-workspace artifact sharing | Outside v1 scope |
| Artifact versioning schema (major.minor) | Safe to defer — the `superseded` edge already handles the primary use case |
| DRM / export control for enterprise workspaces | Depends on enterprise contract; not part of core architecture |

---

## 11. Next Steps

The next document is **11 — Observability Model**: locking down how the system is observed — traces, metrics, logs, health checks, and alerting policy — providing the foundation for the operations team to monitor, debug, and recover without needing to read source code.

The Lineage model (doc 10) provides artifact ancestry paths for observability: when an artifact `failed` or is tainted, the observability layer needs to know the full lineage to surface the correct context for the investigator.
