# 08 — Sandbox Security Model

**Status:** Draft v1.0
**Dependencies:** 02 Architectural Invariants, 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 07 API Contracts
**Core Principle:** The Sandbox is not a "convenient execution environment" — it is the **canonical security boundary** of the entire system. Everything inside a sandbox must be treated as untrusted until explicitly permitted by policy.

---

## 1. Threat Model

The system must defend against the following threat groups. This is a closed list — every design decision in this document must trace back to at least one threat.

### T1 — Agent Tool Privilege Escalation

An agent is prompt-injected or reasons incorrectly, calling tools beyond its granted scope: writing files outside the output directory, calling APIs outside the allowlist, spawning unauthorized subprocesses.

**Defense objective:** Capability matrix per sandbox class, tool call enforcement at the execution layer before execution.

### T2 — Secret Exfiltration

An agent reads a secret from env/file and exfiltrates it via tool call, network call, artifact content, or terminal output.

**Defense objective:** Secrets are never exposed as plaintext in logs/artifacts/terminal output. Redaction is mandatory. Network egress is tightly controlled.

### T3 — Lateral Movement Between Workspaces

A sandbox belonging to workspace A reads/writes data of workspace B via shared filesystem, shared network, or shared storage path.

**Defense objective:** Isolation namespace per workspace. Storage paths must not be guessable by pattern.

### T4 — Network Misuse

An agent uses the sandbox's network egress to exfiltrate data, call external models (bypassing the model gateway), download malicious payloads, or establish a C2 channel.

**Defense objective:** Deny-by-default egress. The Model Gateway is the only exit for LLM calls. Allowlist by domain/port, not by IP.

### T5 — Artifact Poisoning

An agent writes malicious content into an artifact (executable, script, malformed data), and that artifact is then used as input for a subsequent run.

**Defense objective:** Artifacts are scanned on write. `failed` Artifacts cannot be used as input. Lineage tracking detects poisoning chains.

### T6 — Terminal Abuse

A user opens a terminal session into a sandbox and: escalates privileges, copies secrets out, modifies artifacts outside the output directory, or keeps the sandbox alive beyond the permitted lifecycle.

**Defense objective:** Terminal is a policy-controlled capability. Full audit logging. Mandatory idle timeout. Terminal cannot see environment secrets.

### T7 — Persistence Beyond Sandbox Lifecycle

A sandbox terminates but child processes, mounted volumes, or open network sockets remain. Internal sandbox data leaks to the next sandbox instance.

**Defense objective:** Hard cleanup on terminate. Volume unmount + wipe. Process group kill. Network namespace teardown.

---

## 2. Isolation Model

A Sandbox must be isolated along the following 6 dimensions. Missing any dimension is an architectural vulnerability.

### 2.1 Workspace Isolation

- Each sandbox is assigned a `workspace_id` that cannot be changed after provisioning.
- Storage mounts, network namespaces, and secret bindings are all scoped by `workspace_id`.
- There are no shared resources between sandboxes of two different workspaces — including image cache and build cache.

### 2.2 Run Isolation

- Each Run has an isolated working directory. Two Runs of the same Task must not share a working directory.
- `run_id` is used as the namespace prefix for all resources allocated within that Run.

### 2.3 AgentInvocation Isolation

- Each AgentInvocation may have its own sandbox or share the Run's sandbox depending on the sandbox class.
- If multiple AgentInvocations within the same Run share a sandbox: the filesystem must have per-invocation scratch space.

### 2.4 Filesystem Mounts

| Mount Point | Permissions | Content |
|---|---|---|
| `/input` | read-only | RepoSnapshot, input artifacts mounted here |
| `/output` | read-write | Output directory — agent may only write here |
| `/tmp` | read-write | Scratch space, wiped when invocation ends |
| `/tools` | read-only | Tool binaries/scripts mounted by the system |
| `/secrets` | read-only, scoped | Secret files injected (see section 6) |
| All other paths | not mounted | No host filesystem access |

**The agent is not permitted to mount or unmount any path.** The mount list is immutable after the sandbox is provisioned.

### 2.5 Process Namespace

- The sandbox runs in an isolated PID namespace.
- The agent process is not permitted to `fork` subprocesses outside the allowed tool binary list.
- `ptrace`, `strace`, and host `/proc` are not accessible.
- Linux capabilities are dropped entirely except the minimum set needed for tool execution.

### 2.6 Network Namespace

- Each sandbox has its own network namespace.
- Default: **deny all egress and ingress**.
- Egress is only opened according to the allowlist from the sandbox's `network_egress_policy` (see section 5).
- Ingress is never opened from outside into the sandbox. Terminal sessions go through a sidecar proxy, not inbound ports.

---

## 3. Sandbox Classes

The following four sandbox classes are the minimum required set. Deployment modes may add classes but must not remove any.

### 3.1 `read_only_repo`

Used for: code audit, static analysis, documentation generation, Q&A about codebases.

| Capability | Allowed |
|---|---|
| Read `/input` | Yes |
| Write `/output` | Yes (reports, structured data) |
| Write `/tmp` | Yes |
| Run subprocesses | No |
| Network egress | No |
| Secret injection | No |
| Terminal session | No |
| Write `/input` | No |

### 3.2 `code_audit`

Used for: running static analysis tools, linters, read-only test runners.

| Capability | Allowed |
|---|---|
| Read `/input` | Yes |
| Write `/output` | Yes |
| Write `/tmp` | Yes |
| Run subprocesses (whitelist) | Yes — only tools in `/tools` |
| Network egress | No (except package registry if policy permits) |
| Secret injection | No (except registry credentials if policy permits) |
| Terminal session | Policy-gated |
| Modify `/input` | No |

### 3.3 `fix_and_patch`

Used for: agent writing code, fixing bugs, creating patches, running tests with side effects.

| Capability | Allowed |
|---|---|
| Read `/input` | Yes |
| Write `/output` | Yes |
| Write `/tmp` | Yes |
| Run subprocesses (whitelist) | Yes |
| Network egress | Policy-gated (package registry, git provider) |
| Secret injection | Policy-gated |
| Terminal session | Policy-gated |
| Modify `/input` | No — output is a patch/diff, source is not modified |

### 3.4 `browser_task`

Used for: agent controlling a browser, web research, form automation.

| Capability | Allowed |
|---|---|
| Read `/input` | Yes |
| Write `/output` | Yes (screenshots, structured data, page content) |
| Write `/tmp` | Yes |
| Run subprocesses | Yes — browser process only |
| Network egress | Policy-gated, domain allowlist mandatory |
| Secret injection | Policy-gated (login credentials) |
| Terminal session | No — no terminal in browser sandbox |
| Host clipboard access | No |
| Download to host filesystem | No — may only write to `/output` |

**The browser sandbox has its own egress policy** — it does not share the code sandbox policy (see section 5.5).

---

## 4. Filesystem Policy

### 4.1 Input Mounting

- `/input` is mounted from `RepoSnapshot.snapshot_storage_ref` or a `ready` `Artifact.storage_ref`.
- The mount is a **read-only hard mount** — kernel-level, cannot be overridden from within the sandbox.
- A `failed` Artifact must not be mounted as `/input`. Any such attempt must be rejected at provisioning.
- Snapshot execution (creating a `RepoSnapshot` from a git remote) occurs within a `read_only_repo` sandbox with no internet egress — only pulling from git providers whitelisted in the policy is permitted.

### 4.2 Output Directory

- `/output` is the only directory where the agent is permitted to create artifact files.
- After an AgentInvocation `completed`, the Artifact service scans the entire `/output` and creates an `Artifact` record for each file.
- Files in `/output` are not executable (the execute bit is stripped when the Artifact service reads them).
- The size of `/output` is limited by `resource_limits.max_output_bytes`.

### 4.3 Scratch Space `/tmp`

- `/tmp` is completely wiped when the AgentInvocation ends (whether `completed` or `interrupted`).
- Content in `/tmp` is never promoted to an Artifact.
- Content in `/tmp` is not included in logs.

### 4.4 Handling Partial Artifacts When a Sandbox Terminates Mid-operation

- If the sandbox is terminated while writing to `/output`: the Artifact service reads the partial content, creates an Artifact record with `artifact_status = failed`, `metadata.partial_data_available = true`.
- Partial artifacts cannot be used as input. They are retained for debugging.
- The checksum of a partial artifact is set to `null`.

---

## 5. Network Egress Policy

### 5.1 Principle: Deny by Default

Every sandbox starts with **zero egress**. Egress is only opened when policy explicitly permits it. There is no "default allow" in any sandbox class.

### 5.2 Model Gateway Is the Only Exit for LLM Calls

- The agent is not permitted to directly call any model provider API (OpenAI, Anthropic, etc.) from within the sandbox.
- All model calls must go through the **Model Gateway** — an internal service with auth, rate limiting, cost tracking, and audit.
- If the sandbox needs to call a model (nested agent call): it must go through the internal Model Gateway endpoint, not the internet.
- The sandbox never receives model provider API keys directly.

### 5.3 Allowlist Structure

The egress allowlist is defined in `sandbox.network_egress_policy` using the following schema:

```json
{
  "rules": [
    {
      "name": "npm-registry",
      "direction": "egress",
      "protocol": "https",
      "domains": ["registry.npmjs.org", "registry.yarnpkg.com"],
      "ports": [443],
      "requires_secret_binding": false
    },
    {
      "name": "github-pull",
      "direction": "egress",
      "protocol": "https",
      "domains": ["github.com", "api.github.com"],
      "ports": [443],
      "requires_secret_binding": true,
      "secret_binding_name": "GITHUB_TOKEN"
    }
  ]
}
```

**Rules:**
- Allowlist by domain, not by IP (IPs can change and are easily bypassed).
- Port 22 (SSH) is never permitted in sandboxes.
- Wildcard domains (`*.example.com`) may only be used when enumeration is not possible, and must include a comment explaining the reason.

### 5.4 Egress Policy by Sandbox Class

| Sandbox Class | Default Egress | Can Be Extended via Policy |
|---|---|---|
| `read_only_repo` | None | No |
| `code_audit` | None | Package registry (opt-in) |
| `fix_and_patch` | None | Package registry, git provider (opt-in) |
| `browser_task` | None | Domain allowlist mandatory when used |

### 5.5 Browser Sandbox Egress

The browser sandbox has special egress requirements — the agent needs web access. However:

- A domain allowlist is still mandatory — there is no "browse anywhere".
- Downloads from the web may only be saved to `/output` — not to the host filesystem.
- The browser process must not make background requests outside the active tab (no background fetch, no WebSocket to external domains not on the allowlist).
- Credentials entered into browser forms must be injected via secret binding — they must not be manually typed by the user/agent in the task config.

---

## 6. Secret Injection Model

### 6.1 Immutable Principles

- Secrets never pass through the frontend.
- Secrets never appear in logs, artifact content, terminal output, or event payloads.
- Secrets are never stored in `run_config`, `step.input_snapshot`, or `agent_invocation.input_messages`.
- Only the Sandbox provisioning layer is permitted to resolve `SecretBinding.secret_ref` to its actual value.

### 6.2 Secret Binding Scope

| Scope | Meaning | Who Can Bind |
|---|---|---|
| `workspace` | Secret used for all runs in the workspace | Workspace admin |
| `task` | Secret used only for a specific task | Task creator (if authorized) |
| `agent` | Secret injected only for a specific agent | Workspace admin |

### 6.3 Secret Lifetime

Secret bindings are **temporary-by-default** within a sandbox:

- Secrets are injected when the sandbox is `provisioning`.
- Secrets are revoked when the sandbox is `terminating` — not retained after termination.
- Secrets must not be copied to `/output` or `/tmp` by any tool.

### 6.4 Injection Mechanisms

| Method | Used For | Notes |
|---|---|---|
| Environment variable | API keys, short-lived tokens | Only visible in process env, not exposed via `/proc/environ` outside the namespace |
| File in `/secrets` | Certificates, config files | Read-only mount, not executable |
| Sidecar token broker | OAuth flows, credential rotation | Token broker is a sidecar process in the sandbox namespace, agent calls a local endpoint |

**Not used:** command line arguments (visible in `ps`), hardcoded in tool binaries.

### 6.5 Redaction Rules

Mandatory across the entire system:

- All log pipelines run a secret redactor before writing.
- The redactor uses pattern lists from SecretBinding (not actual values) to detect and replace with `[REDACTED]`.
- If the redactor cannot run: the log must be dropped, not written as a partial log that may contain secrets.
- `agent_invocation.output_messages` must not contain strings matching any secret pattern.

---

## 7. Policy Enforcement Points

Enforcement occurs at the following 7 points. Missing any point is a vulnerability.

| Enforcement Point | Enforced By | When |
|---|---|---|
| **EP1: Before provisioning sandbox** | Orchestrator + Policy service | When Run transitions `queued → preparing` |
| **EP2: Before attaching tool** | Execution layer | When agent dispatches a tool call |
| **EP3: Before opening network** | Network proxy | When a sandbox process opens a connection |
| **EP4: Before attaching terminal** | Terminal sidecar | When API receives `POST /runs/:id/terminal` |
| **EP5: Before mounting secret** | Secret injection service | During provisioning |
| **EP6: Before issuing download URL** | Artifact service | When API receives `GET /artifacts/:id/download` |
| **EP7: When artifact is written** | Artifact service | When `/output` is scanned after invocation |

### EP1 Detail — Sandbox Provisioning

The Orchestrator must check before creating a sandbox:
- Whether the sandbox class is appropriate for the `task_type`.
- Whether the workspace is within resource limits (concurrent sandboxes, total cost).
- Whether the current policy permits this type of task.
- If the check fails: the Run transitions `preparing → failed`, no sandbox is created.

### EP4 Detail — Terminal

A terminal is not a "UI privilege" — it is a **sandbox capability granted via policy**:
- The policy must explicitly contain `terminal: allowed` for the corresponding sandbox class.
- Each terminal session has its own `session_id`.
- The terminal sidecar proxies all input/output — there is no direct attach to the container TTY.
- Idle timeout: 5 minutes by default, configurable in policy, cannot be disabled.

### EP6 Detail — Download URL

- The signed URL must be policy-scoped by `workspace_id` — a URL from workspace A must not work for workspace B.
- The URL must not be predictable from `artifact_id` or `run_id`. The URL must be an opaque signed token.
- Default TTL for signed URLs: 15 minutes.
- Sensitive artifacts (`metadata.sensitivity = high`) may only be downloaded within the internal network if `deployment_mode = local` or `hybrid`.

---

## 8. Terminal Security

A terminal session is the highest-risk capability — all of the following constraints must apply.

### 8.1 Defaults

- The terminal defaults to a **read-only shell** (no write capability to the filesystem outside `/tmp`).
- Writing to `/output` via terminal must be explicitly permitted by policy (`terminal_write_output: allowed`).
- Default shell: `sh` with a minimal command set (no `curl`, no `wget`, no `ssh`, no `git` unless the sandbox class permits it).

### 8.2 Audit Log

- All terminal I/O (stdin and stdout) must be recorded in the audit log.
- The audit log is not truncated, input is not redacted (only output is redacted according to secret patterns).
- The audit log is append-only, scoped by `session_id`.
- The audit log is retained after the sandbox terminates (not wiped with the sandbox).

### 8.3 Timeout

- **Idle timeout:** 5 minutes without a keystroke → session terminated.
- **Hard timeout:** Equal to the sandbox's `resource_limits.max_duration_seconds` — the terminal cannot outlive the sandbox.
- Timeout cannot be extended from within the terminal session.

### 8.4 Secret Visibility

- The terminal process must not have secret environment variables visible. Secret env vars are injected into the agent process, not the terminal process.
- The `env` command in the terminal must not list secret binding names.
- The `/secrets` mount is not accessible from the terminal — the terminal runs in a chroot without `/secrets`.

### 8.5 File Transfer

- Copy from sandbox to outside: **only via `/output` → Artifact → signed URL**. No SCP, no clipboard.
- Upload from outside into the sandbox via terminal: **not permitted**.

---

## 9. Lifecycle and Cleanup Semantics

### 9.1 When Sandbox Is `terminating`

The Execution layer must perform the following in order:
1. Send SIGTERM to all processes in the PID namespace.
2. Wait for graceful shutdown (5 seconds).
3. Send SIGKILL to remaining processes.
4. Close all network sockets.
5. Unmount all volumes (`/input`, `/secrets`, `/tmp`).
6. **Wipe `/tmp`** — shred or secure delete.
7. Tear down the network namespace.
8. Tear down the PID namespace.
9. Emit `sandbox.terminated`.

**This order is immutable.** No steps may be skipped, no order may be changed.

### 9.2 Retained After Termination

| Data | Retained | Storage Location |
|---|---|---|
| `/output` content | Yes — promoted to Artifact before termination | Artifact storage |
| Audit log (terminal) | Yes | Audit log store |
| `sandbox.terminated` event | Yes | Event store |
| Execution log of tool calls | Yes — written to Step output_snapshot | DB |
| `/tmp` content | No — wiped | — |
| `/secrets` content | No — unmounted before termination | — |
| Process memory | No | — |

### 9.3 Sandbox Reuse

- Sandboxes must not be reused between different AgentInvocations for `fix_and_patch` or `browser_task`.
- `read_only_repo` and `code_audit` may use a pre-warmed sandbox pool but must perform **snapshot + restore** to ensure a clean state between invocations.

---

## 10. Violation Handling

When a policy is violated, the system must respond in the following order:

### 10.1 Handling Flow

```
Policy violation detected (EP2, EP3, EP4, EP5, EP6, EP7)
  │
  ├── 1. Block the action immediately
  │         (tool call rejected, network connection dropped, terminal attach denied)
  │
  ├── 2. Emit security event
  │         sandbox.policy_violation (with violation_type, detail, sandbox_id, workspace_id)
  │
  ├── 3. Fail the current Step
  │         step → failed, error_code = POLICY_VIOLATION
  │
  ├── 4. Interrupt the AgentInvocation
  │         agent_invocation → interrupted, reason = policy_violation
  │
  ├── 5. Terminate the Sandbox
  │         sandbox.terminate_requested → terminating → terminated
  │         termination_reason = policy_violation
  │
  └── 6. Taint the Artifact (if partial output exists)
            artifact_status = failed
            metadata.tainted = true
            metadata.taint_reason = policy_violation
```

### 10.2 Artifact Taint

- Tainted artifacts must not be used as input for any Run.
- Tainted artifacts cannot be downloaded via signed URL by default — an explicit override with audit logging is required.
- Taint cannot be automatically removed — only a Workspace admin can untaint after review.

### 10.3 Security Event

`sandbox.policy_violation` is a special fact event with the following mandatory fields:

```json
{
  "violation_type": "<network_egress | tool_unauthorized | secret_access | filesystem_write | terminal_abuse>",
  "enforcement_point": "<EP1 | EP2 | EP3 | EP4 | EP5 | EP6 | EP7>",
  "blocked_action": "<string describing the blocked action>",
  "policy_rule_name": "<name of the policy rule that was violated>",
  "severity": "<low | medium | high | critical>"
}
```

- `high` and `critical` violations must trigger alerts beyond the audit log (email, webhook, or ops notification depending on deployment mode).
- `critical` violations (lateral movement attempt, secret exfiltration attempt) must temporarily lock the workspace and require admin review.

---

## 11. Intentionally Deferred Decisions

| Item | Reason for Deferral |
|---|---|
| Specific sandbox runtime (Docker, gVisor, Firecracker, WASM) | Depends on deployment topology (doc 13) — each mode uses a different runtime |
| Pre-warmed pool implementation for `read_only_repo` | Depends on the implementation layer |
| Secret rotation while sandbox is `executing` | Edge case — requires further design |
| Egress policy for AI tool calls (agent calling external APIs) | Depends on the tool registry — will be locked down with the tool/execution layer |
| Browser sandbox network inspection (MITM proxy for audit) | Legally and technically complex — deferred to deployment config |
| Snapshot integrity verification when mounting `/input` | Depends on the Artifact Lineage Model (doc 10) |

---

## 12. Next Steps

The next document is **09 — Permission Model**: locking down the role/permission matrix, policy resolution order, per-agent permissions, per-tool permissions, and the mechanism for delegating permissions from workspace down to task/run/agent. Doc 09 will fill in the "Policy-gated" items referenced in this document.
