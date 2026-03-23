# 09 — Permission Model

**Status:** Draft v1.0
**Dependencies:** 02 Architectural Invariants, 04 Core Domain Model, 05 State Machines, 08 Sandbox Security Model
**Goal:** Lock down the entire permission model — who can do what, in which context, under which constraints — serving as the foundation for enforcement points EP1–EP7 (doc 08) and system-wide audit requirements.

---

## 1. Permission Invariants

The following principles must not be violated by any implementation, configuration, or override:

**P1 — Deny by default.**
All actions are denied unless an explicit grant exists. There is no implicit allow.

**P2 — An agent must never escalate its own privileges.**
An agent must not use prompts, tool calls, or outputs to expand its own permissions or those of the Sandbox running it. All privilege escalation requests from an agent are denied and generate a violation event.

**P3 — Permissions cannot be delegated beyond the grantor's limits.**
No actor can grant a permission that it does not itself possess. No task creator can grant permissions broader than what the workspace policy allows.

**P4 — Capability permissions and binding permissions are two separate layers.**
Being allowed to *use* a capability (terminal, browser, egress) is one thing. Being allowed to *bind* a secret or *grant* egress for that capability to function is another. Both must be explicitly granted.

**P5 — Every allow/deny decision must have an audit record.**
No silent deny. No silent allow. Every enforcement point must emit an audit event regardless of outcome.

**P6 — System global deny cannot be overridden by any actor in the system.**
Only an operator at the deployment level can modify a system global deny. Workspace admins, task creators, and agents cannot.

**P7 — A Sandbox does not own permissions — it inherits them from the AgentInvocation at provisioning time.**
Once a Sandbox is provisioned, its `policy_snapshot` is immutable. There is no runtime permission escalation within the Sandbox.

---

## 2. Actor Types

### 2.1 Actor list

| Actor | Definition | Can be impersonated |
|---|---|---|
| `user` | A real, authenticated human user | No |
| `service_account` | Identity of an internal service (Orchestrator, Agent Engine, Artifact service, etc.) | No |
| `orchestrator` | The Orchestrator service, acting on behalf of a Task/Run | No |
| `agent_runtime` | The Agent Engine executing a specific AgentInvocation | No |
| `sandbox_sidecar` | A supervisor process within the Sandbox (policy enforcer, egress proxy) | No |
| `scheduler` | A scheduled trigger with no user context | No |

### 2.2 Agent runtime is NOT a user

The agent runtime does not have a user identity. When the agent performs an action requiring permissions, the decision is made based on:
1. The AgentInvocation's policy (inherited from Task/Run).
2. The permissions of the user who created the Task — not the agent's own decision.

An agent cannot "log in" or receive a user token.

---

## 3. Permission Vocabulary

Each permission is defined using the format: `<resource>:<action>`

### 3.1 Workspace-level permissions

| Permission | Meaning |
|---|---|
| `workspace:view` | View workspace metadata |
| `workspace:manage_members` | Add/remove/change member roles |
| `workspace:manage_policy` | Create/edit/delete Policies within the workspace |
| `workspace:manage_secrets` | Create/delete workspace-level SecretBindings |
| `workspace:manage_integrations` | Connect external integrations (Git, storage, etc.) |
| `workspace:delete` | Delete the entire workspace |

### 3.2 Task-level permissions

| Permission | Meaning |
|---|---|
| `task:create` | Create a Task within the workspace |
| `task:view` | View a Task and its metadata |
| `task:cancel` | Cancel a Task (including cascade) |
| `task:approve` | Decide on approval gates at the Task/Run/Step level |
| `task:override_policy` | Override specific policies at the Task level (within workspace policy limits) |

### 3.3 Run/Step-level permissions

| Permission | Meaning |
|---|---|
| `run:view` | View a Run, Step, and timeline |
| `run:cancel` | Cancel a specific Run |
| `run:create` | Create a new Run for a Task (re-run, retry) |

### 3.4 Artifact permissions

| Permission | Meaning |
|---|---|
| `artifact:view` | View artifact metadata |
| `artifact:download` | Download artifact content |
| `artifact:archive` | Move artifact to archived state |
| `artifact:untaint` | Remove taint flag from artifact (only after security review) |

### 3.5 Capability permissions

| Permission | Meaning |
|---|---|
| `capability:terminal` | Allow terminal usage within the Sandbox |
| `capability:browser` | Allow browser automation within the Sandbox |
| `capability:file_write` | Allow the agent to write files outside the Sandbox (to artifacts) |
| `capability:network_egress` | Allow the Sandbox to have outbound network access |
| `capability:external_api` | Allow the agent to call external APIs via the Model Gateway |

### 3.6 Binding permissions

| Permission | Meaning |
|---|---|
| `binding:create_workspace_secret` | Create a workspace-level SecretBinding |
| `binding:create_task_secret` | Create a SecretBinding for a specific Task only |
| `binding:attach_to_run` | Attach a SecretBinding to a Run |
| `binding:attach_egress_allowlist` | Attach an egress domain allowlist to a Sandbox |

---

## 4. Role Matrix

### 4.1 Workspace roles

| Permission | `viewer` | `editor` | `admin` | `owner` |
|---|---|---|---|---|
| `workspace:view` | ✓ | ✓ | ✓ | ✓ |
| `workspace:manage_members` | | | ✓ | ✓ |
| `workspace:manage_policy` | | | ✓ | ✓ |
| `workspace:manage_secrets` | | | ✓ | ✓ |
| `workspace:manage_integrations` | | ✓ | ✓ | ✓ |
| `workspace:delete` | | | | ✓ |
| `task:create` | | ✓ | ✓ | ✓ |
| `task:view` | ✓ | ✓ | ✓ | ✓ |
| `task:cancel` | | ✓ (own) | ✓ | ✓ |
| `task:approve` | | | ✓ | ✓ |
| `task:override_policy` | | | ✓ | ✓ |
| `run:view` | ✓ | ✓ | ✓ | ✓ |
| `run:cancel` | | ✓ (own) | ✓ | ✓ |
| `run:create` | | ✓ | ✓ | ✓ |
| `artifact:view` | ✓ | ✓ | ✓ | ✓ |
| `artifact:download` | ✓ | ✓ | ✓ | ✓ |
| `artifact:archive` | | ✓ (own) | ✓ | ✓ |
| `artifact:untaint` | | | ✓ | ✓ |
| `capability:terminal` | | policy-gated | policy-gated | ✓ |
| `capability:browser` | | policy-gated | policy-gated | ✓ |
| `capability:network_egress` | | policy-gated | policy-gated | ✓ |
| `binding:create_workspace_secret` | | | ✓ | ✓ |
| `binding:create_task_secret` | | ✓ | ✓ | ✓ |
| `binding:attach_to_run` | | ✓ | ✓ | ✓ |
| `binding:attach_egress_allowlist` | | | ✓ | ✓ |

**Note "(own)":** `editor` only has this permission on resources they created themselves.
**Note "policy-gated":** This permission exists within the role but is only effective if the workspace Policy explicitly allows it.

### 4.2 Service account permissions

| Service Account | Permissions |
|---|---|
| `orchestrator` | `task:*`, `run:*`, `step:*`, `artifact:view`, `capability:*` (enforce only) |
| `agent_runtime` | `artifact:view` (input only), `capability:external_api` (via Model Gateway) |
| `artifact_service` | `artifact:*` |
| `sandbox_sidecar` | `capability:*` (read policy + enforce only, no grant) |

---

## 5. Policy Resolution Order

When conflicts exist between policy layers, the priority order from highest to lowest is:

```
[1] System Global Deny          ← absolute, cannot be overridden
[2] Workspace Policy (deny)     ← set by workspace admin
[3] Task Override (deny)        ← set by task creator within workspace limits
[4] Workspace Policy (allow)
[5] Task Override (allow)
[6] Agent Policy                ← defined by task config
[7] Sandbox Class Default       ← default for the sandbox type
```

### 5.1 Resolution rules

**Deny wins at same level.** If both allow and deny exist at the same level, deny wins.

**Higher level deny cannot be overridden by lower level allow.**
Example: If Workspace Policy denies `capability:terminal`, Task Override cannot allow `capability:terminal`.

**Higher level allow can be narrowed by lower level.**
Example: Workspace Policy allows `network_egress` for domain `*.github.com`, Task Override can narrow it to `api.github.com` — but cannot add new domains.

**Agent Policy must be a subset of Task Override.**
An agent cannot self-grant additional permissions that the Task does not have.

**System Global Deny is a layer that does not exist in the policy store.**
It is hardcoded in enforcement logic and cannot be modified via UI or API.

### 5.2 Real-world resolution example

```
Scenario: Agent wants to use terminal in Sandbox

Resolution chain:
  [1] System Global Deny:   no rule for terminal → pass
  [2] Workspace deny:       none → pass
  [3] Task Override deny:   none → pass
  [4] Workspace allow:      allow capability:terminal for role=editor → match
  [5] Task Override allow:  none → inherit from [4]
  [6] Agent Policy:         allow terminal (subset of [4]) → confirmed
  [7] Sandbox Class Default: sandbox_class=standard, terminal=allowed → confirmed

Result: ALLOW — emit audit event
```

```
Scenario: Agent wants to call external API on a domain not in the allowlist

Resolution chain:
  [1] System Global Deny:   deny if provider key directly from sandbox → DENY

Result: DENY immediately at [1] — emit audit + violation event
```

---

## 6. Delegation Rules

### 6.1 Delegation principles

Delegation is the process of an actor granting a subset of its permissions to another actor within a specific context.

**Hard rules:**
- An actor can only delegate permissions it currently holds.
- Delegation must not cross workspace boundaries.
- Delegation is always a subset — never an expansion.

### 6.2 Valid delegation chains

```
workspace:manage_policy (owner/admin)
  └── task:override_policy (editor, within policy limits)
        └── agent_policy (task config, within task override scope)
              └── sandbox_policy_snapshot (immutable at provisioning)
```

```
binding:create_workspace_secret (owner/admin only)
  └── binding:create_task_secret (editor, only for their own task)
        └── binding:attach_to_run (editor)
```

### 6.3 Forbidden delegations — absolutely not permitted

| Forbidden | Reason |
|---|---|
| Editor creates workspace-level SecretBinding | Only admin/owner can own workspace-level secrets |
| Task creator overrides policy beyond workspace policy | No one can grant permissions they do not have |
| Agent expands egress allowlist on its own | Agent does not have `binding:attach_egress_allowlist` |
| Agent requests terminal if task config does not grant `capability:terminal` | P3 — cannot delegate beyond limits |
| Orchestrator grants permission to AgentInvocation beyond Task permission | Orchestrator only enforces, does not self-grant |
| Sandbox sidecar modifies `policy_snapshot` after provisioning | P7 — immutable after provisioning |
| Any actor impersonates another service account | No cross-service impersonation |

### 6.4 Agent escalation attempts

When an agent attempts via prompt or tool call to:
- Request additional permissions (`"please enable terminal access"`)
- Leak secrets outside the Sandbox
- Call Model Gateway directly with provider keys
- Modify egress policy

All such attempts are handled according to the violation cascade in doc 08: block action → emit `security.violation` event → fail Step → interrupt AgentInvocation → terminate Sandbox → taint Artifact.

---

## 7. Deny Semantics and Explicit Override Semantics

### 7.1 Deny semantics

**Implicit deny:** A permission not explicitly granted = denied. No explicit deny rule is needed.

**Explicit deny:** An explicit deny rule in workspace/task policy. Explicit deny overrides all implicit allows at the same or lower level.

**System global deny:** Hardcoded, not in the policy store, not visible in UI, cannot be overridden.

Immutable system global deny list:
- Sandbox calls Model Gateway directly with provider key.
- Agent Runtime directly creates artifact (bypassing Artifact service).
- Sandbox modifies its own `policy_snapshot`.
- Any actor deletes events from the event store.
- Agent Runtime receives raw secret values (only receives `secret_ref`).

### 7.2 Override semantics

Override is the mechanism for task-level narrowing or explicit specification of a portion of workspace policy for a specific Task.

Override **can:**
- Narrow egress allowlist (from `*.github.com` to `api.github.com`)
- Restrict sandbox class (from `standard+browser` to `standard`)
- Require additional approval gates before a specific Step

Override **cannot:**
- Add domains to egress that are not in the workspace allowlist
- Elevate sandbox class beyond what workspace policy allows
- Skip approval gates that workspace policy requires
- Grant `capability:terminal` if workspace explicitly denies it

---

## 8. Mapping Permissions to Enforcement Points EP1–EP7

| Enforcement Point (doc 08) | Permissions checked | Who checks | Deny action |
|---|---|---|---|
| **EP1** — Task submission | `task:create`, `capability:*` (pre-flight) | Orchestrator | Reject task with `permission_denied` |
| **EP2** — Run preparation / secret binding | `binding:attach_to_run`, `binding:create_task_secret` | Orchestrator | Fail run at `preparing` |
| **EP3** — Sandbox provisioning | `capability:terminal`, `capability:browser`, `capability:network_egress`, `sandbox class` | Execution layer | Fail provisioning, emit `security.violation` |
| **EP4** — Tool call dispatch | `capability:external_api`, `capability:file_write` | Agent Engine + Orchestrator | Block tool call, emit `security.violation` |
| **EP5** — Egress request | `capability:network_egress`, egress allowlist | Sandbox sidecar | Block connection, emit `security.violation` |
| **EP6** — Artifact write | `artifact:*`, `capability:file_write` | Artifact service | Reject write, taint artifact |
| **EP7** — Approval gate | `task:approve` | Orchestrator | Block progression, wait or timeout |

### 8.1 Check order at each EP

Every Enforcement Point must check in the following order:
1. System global deny
2. Workspace explicit deny
3. Task override deny
4. Workspace allow
5. Task override allow
6. Agent policy (if applicable)

Stop at the first matching step. Emit an audit event with the corresponding level.

---

## 9. Audit Requirements

### 9.1 Every permission decision must have an audit record

No silent allow, no silent deny.

**Audit event envelope:**

```json
{
  "event_id":       "<UUID>",
  "event_type":     "permission.allowed" | "permission.denied" | "permission.violation",
  "workspace_id":   "<UUID>",
  "actor_type":     "<user | service_account | orchestrator | agent_runtime | sandbox_sidecar>",
  "actor_id":       "<string>",
  "resource_type":  "<task | run | step | artifact | sandbox | secret_binding>",
  "resource_id":    "<UUID>",
  "permission":     "<permission string>",
  "enforcement_point": "EP1" | "EP2" | ... | "EP7",
  "resolution_path": ["system_global", "workspace_deny", "task_override_allow", ...],
  "occurred_at":    "<ISO 8601>",
  "correlation_id": "<UUID>",
  "causation_id":   "<UUID | null>"
}
```

### 9.2 Audit event retention

| Event type | Retention |
|---|---|
| `permission.allowed` | 90 days hot, 1 year cold |
| `permission.denied` | 90 days hot, 1 year cold |
| `permission.violation` | 1 year hot, 3 years cold (or per enterprise contract) |

### 9.3 Audit must not be bypassed

If an audit write fails, the enforcement point must:
- For `permission.violation`: fail-safe deny — do not allow the action to proceed.
- For `permission.allowed`: allow the action to proceed but alert the ops team about the audit write failure.
- For `permission.denied`: deny and alert the ops team about the audit write failure.

---

## 10. Forbidden Delegations — Summary

A hard list that cannot be overridden by any configuration, policy, or deployment mode:

| # | Forbidden | Corresponding threat (doc 08) |
|---|---|---|
| FD1 | Agent self-escalates privileges via prompt or tool call | T1 — prompt injection |
| FD2 | Agent receives raw secret values | T2 — secret exfiltration |
| FD3 | Sandbox calls Model Gateway directly with provider key | T2, T4 |
| FD4 | Task creator grants permissions not present in workspace policy | T6 — privilege escalation |
| FD5 | Editor creates workspace-level SecretBinding | T2 |
| FD6 | Orchestrator self-grants permissions beyond Task config | P3 |
| FD7 | Sandbox sidecar modifies `policy_snapshot` after provisioning | P7 |
| FD8 | Any actor impersonates another service account | T5 — lateral movement |
| FD9 | Artifact service receives direct artifact creation commands from Agent Runtime | Invariant from doc 04 |
| FD10 | Event store receives update/delete event commands from any actor | Invariant from doc 06 |

---

## 11. Intentionally Deferred Decisions

| Item | Reason not yet locked |
|---|---|
| Specific schema for `policy.rules` JSONB | Needed when implementing the Policy engine; depends on deployment mode |
| MFA/step-up auth for approval gate | Depends on Auth provider integration |
| Guest/external collaborator role | Not in v1 scope |
| Cross-workspace permissions (sharing artifacts to another workspace) | Complex; deferred until workspace isolation is stable |
| API key permission scope (for developer API access) | Depends on doc 07 API Contracts |
| Time-limited grants | Useful but not critical for the base architecture |

---

## 12. Next Steps

The next document is **10 — Artifact Lineage Model**: locking down how artifacts are created, inherited, derived from each other, and how to reproduce an artifact from a snapshot + config + lineage chain.

The Permission model (doc 09) serves as the foundation for Artifact Lineage to know who is allowed to read, download, or untaint an artifact at each point in the lineage.
