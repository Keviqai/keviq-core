# 02. Architectural Invariants

The invariants below are immutable principles. During development, if a solution violates an invariant, the solution is considered incorrect by default unless a new architectural decision is made at the system level.

## I1. Web UI is a shell, not the core

The frontend is only a display and control layer. All critical logic related to task orchestration, execution, policy, persistence, artifacts, and security must reside in backend services.

## I2. Orchestrator and Agent Engine are two separate layers

* **Orchestrator** is responsible for the task graph, scheduling, retries, dependency, concurrency, cancellation, and coordination.
* **Agent Engine** is responsible for reasoning, stateful tool use, memory, and sub-agent logic within the scope of a single run.

Neither layer may absorb the core responsibilities of the other.

## I3. All work must follow the standard model: Workspace → Task → Run → Step → Artifact

There must be no shortcuts that bypass the core model by letting the UI call tools directly or letting agents produce output without attaching lineage to a task/run.

## I4. Artifact is a first-class object

Every valuable output must be stored as an artifact with metadata, ownership, lineage, preview info, and access permissions. Output that exists only in logs or chat transcripts is insufficient.

## I5. Sandbox is the standard execution boundary

All sensitive or side-effecting actions such as:

* running bash;
* accessing local repos;
* writing files;
* running tests/builds;
* browser automation;
* network actions

must be performed within an execution environment managed by sandbox policy or an equivalent execution backend.

## I6. Sandbox must be ephemeral and policy-driven

A sandbox must not be an ambiguous environment that persists indefinitely without oversight. Each sandbox must have:

* a well-defined lifecycle;
* resource quotas;
* network policy;
* secret policy;
* ownership scoped to a workspace/run;
* cleanup/archive semantics.

## I7. All long-lived state changes must have a standard persistence or event contract

System state must not exist silently only in process memory. If state needs to be visible to the UI, audit, retry, or recovery mechanisms, it must go through the database or event bus with a standardized schema.

## I8. The event model is the nervous system backbone

All services must communicate via a standardized event contract covering:

* event type;
* correlation id;
* causation id;
* timestamp;
* source;
* payload schema.

Services must not emit events in ad-hoc, service-specific formats.

## I9. The system must be reproducible via snapshot + config + artifact lineage

An important run must be traceable through:

* the repo snapshot or input snapshot;
* the task spec;
* the runtime config;
* model usage;
* tools that were called;
* artifacts that were produced.

Without this, the system does not qualify as a serious work platform.

## I10. Permissions must exist at multiple layers

At minimum, the following layers are required:

* user-to-workspace;
* agent-to-tool;
* run-to-secret;
* sandbox-to-network;
* artifact-to-view/download.

Security must not be reduced to user login alone.

## I11. The frontend must not hold the source of truth for runtime state

The frontend may cache or render temporarily, but the source of truth for tasks, runs, artifacts, sandboxes, and permissions must reside in the backend.

## I12. The model layer must be a replaceable dependency

The architecture must not be coded such that every service knows provider-specific model details. Model access must go through a model gateway or equivalent abstraction.

## I13. The tooling layer must be separate from the reasoning layer

An agent may decide which tool to call, but the tool implementation itself, the capability registry, and the execution policy must be separated from prompt/reasoning logic.

## I14. Human-in-the-loop is a core mechanism, not an add-on

The system must be designed with built-in intervention points:

* clarification;
* approval;
* pause/resume;
* manual override;
* rerun.

The design must not assume that all tasks run fully automatically.

## I15. Local, cloud, and hybrid are all valid topologies

The architecture must not assume that everything runs in the cloud or everything runs locally. The system must maintain sufficient abstraction to support three modes:

* local-first;
* cloud-first;
* hybrid.
