# 00. Product Vision

## Working Title

Agent OS

## Product Manifesto

Agent OS is a **new work operating system** designed for people who want to apply AI to their daily work. It is not designed as a chatbot, a collection of disconnected tools, or a simple automation dashboard. It is designed as a **complete work environment** where humans, AI agents, data, online tools, and computing resources coexist in a unified operational space.

Agent OS must enable many different user groups to leverage AI in a structured way:

* technical users use it to read code, analyze repos, write code, run tests, fix bugs, and generate reports;
* marketing professionals use it for research, synthesis, planning, campaign tracking, and creating work documents;
* managers use it to coordinate tasks, track progress, consolidate information, create reports, and supervise AI-executed operations.

## System Nature

Agent OS is a new operating system in the functional sense, not in the traditional kernel sense. It must serve as:

* a **work shell** for users on the web;
* an **orchestrator** for tasks and multiple agents;
* an **execution environment** for online work and coding;
* a **resource management, permissions, artifact, and state layer**;
* a **bridge between users, AI models, agent engines, online tools, and local/cloud resources**.

## Differentiation

Agent OS does not compete by having a proprietary model. Its core value lies in:

* the ability to organize AI-powered work at the operating system level;
* the ability to run and control multiple agents in a structured manner;
* the ability to connect online tools and coding tools within the same environment;
* the ability to maintain work context per workspace rather than per isolated chat session;
* the ability to observe, intervene, and control AI activity in real time.

## Priority User Segments

The first version targets:

* individuals who work intensively with computers;
* small to medium technical teams;
* knowledge workers who need AI for research, synthesis, analysis, planning, document creation, and coding.

The system is not locked to a single role. The goal is to create a foundation strong enough to expand into many types of work, as long as those tasks primarily occur via the internet, digital documents, software, data, and programming environments.

## Priority Use Case Axes

Agent OS must excel at the following work categories:

1. **online knowledge work**: research, synthesis, reporting, analysis, planning, task tracking;
2. **coding work**: reading repos, code audits, bug fixes, refactoring, patch creation, running tests, generating technical artifacts;
3. **multi-step digital workflows**: long-running tasks requiring multiple steps, multiple agents, multiple online tools, and file/report management.

## Out of Scope for Initial Phase

The initial phase does **not** prioritize the following types of work:

* advanced graphic design;
* film production, 3D, CAD;
* heavy real-time media processing;
* complex hardware control;
* workflows requiring specialized graphical UIs like a Figma-class or Adobe-class editor.

This does not mean the system will never support them — it means the initial architecture must not be bent to accommodate those use cases.

## Long-term Vision

In the long run, Agent OS should resemble a "Linux for AI-native work":

* with its own UI shell;
* with its own process/task model;
* with its own workspace/file/artifact model;
* with its own permission/security model;
* capable of running locally, in the cloud, or in hybrid mode;
* capable of plugging in multiple models, engines, connectors, and execution backends.

The system must exist as a **platform**, not merely a single-feature product.

---

# 01. System Goals and Non-goals

## System Goals

### G1. The system must be a work environment, not a chat box

All design decisions must prioritize the workspace, task, run, artifact, terminal, file, event, and agent lifecycle models. Chat is merely one interaction interface, not the architectural center.

### G2. The system must support multiple types of digital work on a unified backbone

At minimum, it must unify two major groups:

* online knowledge work;
* coding work.

All initial work types must flow through the same backbone: workspace → task → orchestrator → agent runtime → tools/execution → artifact → observability.

### G3. The system must prioritize long-running, multi-step, stateful work

The system must handle tasks that cannot be completed in a single short prompt, including:

* large repo analysis;
* bug scanning and report generation;
* multi-source topic research;
* multi-part planning and document creation;
* tasks requiring multiple agents and multiple tool calls.

### G4. The system must have a local/cloud/hybrid architecture from the foundation

Agent OS resources may come from:

* the user's local machine;
* cloud compute;
* online services;
* object storage from the cloud or on-premises.

The architecture must accept this as a core characteristic, not an afterthought.

### G5. The system must be observable and controllable

Users must be able to see:

* which tasks are running;
* what each agent is doing;
* which tools were just called;
* which files were just created or modified;
* where progress and errors stand;
* how much model or compute resources have been consumed.

Simultaneously, users must be able to:

* stop;
* modify instructions;
* approve/reject;
* manually intervene;
* rerun.

### G6. The system must be permissioned and auditable

AI must not be assumed to have full authority. The system must support:

* workspace-level permissions;
* tool-level permissions;
* agent-level permissions;
* policy-based secret provisioning;
* action logging and artifact lineage tracking.

### G7. The system must be tool-first and online-first

Since the system's work orientation is primarily online and coding-related, online tools, APIs, browser automation, file operations, terminals, repo access, and data connectors must be core capabilities.

### G8. The system must be engine-agnostic and model-agnostic

Agent OS must not be locked into a single model or engine. The system must be abstract enough to swap:

* model providers;
* agent engines;
* execution backends;
* connector protocols.

### G9. The system must be artifact-centric

All valuable work outputs must become artifacts that can be saved, viewed, traced, shared, and reused. Examples:

* reports;
* patches;
* generated files;
* logs;
* findings JSON;
* summaries;
* repo snapshots.

### G10. The system must maintain its operating system identity at the product level

The overall experience must be: open a workspace, view tasks, manage agents, orchestrate resources, track outputs. The product must not drift into becoming a chat assistant with supplementary panels.

## Non-goals

### N1. Do not build a general-purpose chatbot then wrap a shell around it

Chat UI must not become the core logic of the entire system.

### N2. Do not optimize for advanced creative graphics in the initial phase

Use cases such as heavy graphic design, intensive video production, and large media creation must not drive the initial architecture.

### N3. Do not lock the system to a single AI or cloud provider

The system must not critically depend on a single provider for models, storage, sandboxes, or execution.

### N4. Do not conflate the orchestrator and agent engine

Task orchestration and agent reasoning logic are two separate layers whose responsibilities must not be mixed.

### N5. Do not let the frontend directly control sensitive execution

The frontend is only a control shell. Execution authority must go through backend services, policy, and audit.

### N6. Do not expect AI to be perfectly correct automatically

The system must be designed with the assumption that AI will make mistakes. Observability, human-in-the-loop, taint tracking, and audit are not optional features but structural necessities.

---

# 02. Architectural Invariants

These are non-negotiable rules of the system. Any implementation that violates them is considered architecturally broken, regardless of whether it "works" in testing.

## I1. Frontend does not directly call domain backend services

All requests from the frontend must go through the API Gateway. The frontend does not know the existence of internal services like orchestrator, artifact-service, or agent-runtime-service. This ensures a single point for authn/authz, response shaping, and audit.

## I2. State transition authority for Task/Run/Step belongs exclusively to the Orchestrator

No other service, no API handler, no frontend, and no agent may directly change the status of Task, Run, or Step. Only the Orchestrator domain service performs state transitions.

## I3. Every domain mutation that requires an event must write DB state + outbox in the same transaction

This is the outbox pattern. No "fire event then write DB" or "write DB then fire event separately." Both must be in the same database transaction.

## I4. Artifact creation goes exclusively through artifact-service

No service, no agent, and no sandbox may directly write to artifact metadata tables or object storage. All artifact creation must go through the artifact-service API.

## I5. Model calls go exclusively through model-gateway

No service, no agent, and no sandbox holds provider API keys directly. All LLM calls must be routed through model-gateway.

## I6. Fail closed when auth/policy/audit dependencies are down

When auth-service, policy-service, or audit-service is unreachable, the system must deny all requests rather than silently allowing them.

## I7. Audit records are append-only and immutable

Once written, audit records cannot be updated or deleted. The audit store must enforce this at the database level.

## I8. Each service owns exactly one DB schema with no overlap

No schema is owned by two services. Cross-schema foreign keys are prohibited. Cross-service data access must go through APIs or events.

## I9. Secret values are never stored in service databases

Service databases only store secret references (pointers). Actual secret values reside in external vault/KMS systems.

## I10. Policy snapshots are immutable after sandbox provisioning

Once a sandbox is provisioned with a policy snapshot, that snapshot cannot be modified. Any policy change requires a new sandbox.

## I11. Correlation ID equals Trace ID

There is no separate trace ID generation. The correlation_id injected at the API Gateway is the trace_id used throughout the system.

## I12. SSE is an observation layer only — not a source of truth

SSE events are used for real-time UI updates and query cache invalidation. They do not carry authoritative state. If SSE is missed, refetching from APIs must yield correct state.

## I13. Recovery must produce events and audit records

Any recovery or reconciliation process must emit proper events and audit records, not silently fix state.

## I14. Taint write must precede event emit

When tainting an artifact, the database flag must be written before the outbox event is inserted, within the same transaction.

## I15. Model version must not be an alias

When recording model version in artifact provenance, the resolved specific version must be used, never an alias like "latest" or "claude-3".

---

# 03. Bounded Contexts

## Context Map

| ID | Context Name | Core Responsibility |
|---|---|---|
| C1 | Identity and Access | User identity, authentication, authorization, roles |
| C2 | Workspace | Workspace lifecycle, members, settings, connections |
| C3 | Task Orchestration | Task/Run/Step lifecycle, state machines, scheduling, cancellation |
| C4 | Agent Runtime | AgentInvocation execution, reasoning loop, tool dispatch |
| C5 | Tool and Connector | Tool registry, connector management, capability declaration |
| C6 | Execution and Sandbox | Sandbox lifecycle, policy enforcement, terminal, secret mounting |
| C7 | Artifact and File | Artifact creation, lineage, taint, signed URLs, provenance |
| C8 | Event and Telemetry | Event store, telemetry, metrics, alerting |
| C9 | Model Gateway | LLM routing, fallback, cost tracking, version resolution |
| C10 | Human Control | Approval flows, notifications, human-in-the-loop |
| C11 | Web Shell / Control | Frontend shell, API gateway, SSE gateway |

## Context Relationships

### Upstream/Downstream

* C3 (Task Orchestration) is upstream of C4 (Agent Runtime): Orchestrator assigns work to Agent Runtime.
* C4 (Agent Runtime) is upstream of C6 (Execution and Sandbox): Agent Runtime requests sandbox provisioning.
* C4 (Agent Runtime) is upstream of C7 (Artifact and File): Agent Runtime registers artifacts through artifact-service.
* C9 (Model Gateway) is upstream of C4 (Agent Runtime): Model Gateway serves model calls.
* C1 (Identity and Access) is upstream of all contexts: provides identity and permission decisions.

### Anti-corruption Layers

* C11 (Web Shell) communicates with all backend contexts exclusively through C11's API Gateway — never directly.
* C6 (Execution and Sandbox) communicates with C9 (Model Gateway) only indirectly — sandbox has no model provider credentials.

---

# 04-12 (See individual document files)

---

# 13. Deployment Topology

## Topology Objectives

The deployment topology must correctly implement the entire core architecture locked in docs 00–12. The topology must not create deployment shortcuts that allow APIs to bypass state machines, services to cross-write into tables they do not own, policies to fail open, or events/outbox to be neglected. Every topology decision must serve the do-not-break rules (DNB1–DNB12) and pressure points from the gate review.

## Immutable Topology Principles

### T13-1. Topology must respect bounded contexts

Each important bounded context must have clear deployment responsibility. It is not mandatory that each context be a separate process, but it is mandatory that each context has a clear owner runtime, storage boundary, and credential boundary.

### T13-2. State transition authority must reside in the Orchestrator domain service

Any topology must ensure that only the Orchestrator domain service is permitted to mutate the state of `Task`, `Run`, `Step`. No other service has direct database write permission on those status fields.

### T13-3. Artifact service must have a real storage boundary

Artifact metadata and artifact content must be protected by a real deployment boundary: separate DB credentials for metadata, separate object storage credentials for blobs, and no service other than the Artifact service has direct write access to artifact metadata tables.

### T13-4. Event log and outbox are mandatory infrastructure

No topology is valid if it omits the outbox or treats the event bus as an optional detail. The event store / message bus is a first-class deployment component.

### T13-5. Fail closed must hold even when dependencies are down

If auth, policy, secret broker, audit, or model gateway is down, the topology must cause the system to fail closed rather than fail open.

### T13-6. Local, cloud, and hybrid are all valid topologies

The deployment architecture must support three modes:

* local-first;
* cloud-first;
* hybrid.

Differences between modes lie in the placement of services, storage, execution backends, and trust boundaries — they must not alter the domain model.

### T13-7. Recovery order is part of the topology

Startup order, readiness semantics, recovery sequences, and degraded modes are components of the topology, not supplementary operational notes.

## High-level Deployment Units

### 13.1 Web Shell

Role:

* provides the UI shell;
* calls APIs;
* subscribes to SSE;
* renders timeline, artifact lineage, task graph, terminal.

Boundary:

* does not hold source of truth;
* does not hold system secrets;
* does not call model providers or sandboxes directly.

### 13.2 API Surface

Includes:

* API Gateway / BFF;
* SSE Gateway.

Role:

* command/query/human intervention surface;
* authn/authz entry point;
* response shaping;
* SSE fan-out to clients.

Boundary:

* does not execute business state transitions directly;
* does not mutate domain state except by calling the appropriate domain service.

### 13.3 Orchestrator Plane

Role:

* task decomposition;
* scheduling;
* dependency graph;
* retries;
* cancellation cascade;
* timeout watchers;
* recovery orchestration.

Storage authority:

* `Task`, `Run`, `Step`.

### 13.4 Agent Runtime Plane

Role:

* runs AgentInvocations;
* maintains agent runtime state;
* tool orchestration;
* summary generation;
* runtime-side event emission;
* reconciles state after restart.

Storage authority:

* `AgentInvocation` runtime state of its own.

### 13.5 Execution Plane

Includes:

* Sandbox Manager;
* terminal session broker;
* execution sidecars if needed;
* network policy enforcement;
* secret mounting subsystem.

Storage authority:

* `Sandbox` metadata;
* temporary execution logs;
* terminal session metadata.

### 13.6 Artifact Plane

Includes:

* Artifact Service;
* object storage;
* artifact preview subsystem;
* signed URL issuer.

Storage authority:

* `Artifact`, `ArtifactVersion`, `ArtifactLineage` metadata;
* object blobs.

### 13.7 Control Services

Includes:

* Auth / Identity;
* Policy service;
* Secret broker;
* Model Gateway;
* Audit service;
* Event bus / Event store;
* telemetry stack.

## Standard Deployment Topology by Mode

### 13.8 Local-first topology

Suitable for:

* developer machines;
* small team labs;
* individual self-hosted setups.

Recommended configuration:

* Web Shell: local browser + local frontend server;
* API Gateway, Orchestrator, Agent Runtime, Artifact Service, Sandbox Manager: running in Docker Compose;
* PostgreSQL, Redis, object storage compatible, event bus: local containers;
* sandboxes: local Docker runtime;
* model gateway: local proxy + optional cloud provider access.

Characteristics:

* simple to deploy;
* strong debugging capabilities;
* weaker trust boundary than cloud but must still maintain credential boundary logic;
* suitable for development and single-node operation.

Prohibited:

* local mode does not justify having all services use a shared DB superuser;
* local mode does not justify bypassing artifact isolation or state transition authority.

### 13.9 Cloud-first topology

Suitable for:

* managed deployments;
* multi-tenant or enterprise-managed environments.

Recommended configuration:

* Web Shell: CDN / edge served;
* API/SSE Gateway: autoscaled stateless services;
* Orchestrator: replicated control plane with leader election or single writer discipline;
* Agent Runtime: horizontally scaled workers;
* Sandbox Manager: control service for container runtime / Kubernetes jobs;
* object storage: managed S3-compatible;
* database: managed PostgreSQL;
* event bus: clustered deployment;
* audit storage: durable managed store, separate.

Characteristics:

* scales well;
* clear policy and credential boundaries;
* requires robust readiness, startup ordering, and reconcilers;
* requires hard multi-tenant isolation for enterprise use.

### 13.10 Hybrid topology

Suitable for:

* UI/control plane on the cloud;
* execution or repo/data kept local or in a private VPC.

Standard model:

* Web Shell + API Surface + Orchestrator: cloud;
* local execution gateway or self-hosted runner: on-prem / laptop / private VPC;
* Artifact plane: can be cloud, local, or split by sensitivity;
* model gateway: cloud proxy but policy-aware;
* secrets: scoped per execution site.

Mandatory conditions:

* execution site must be treated as a separate trust boundary;
* event relay, audit relay, and policy snapshot must be consistent between cloud plane and local execution plane;
* execution nodes must not make policy decisions beyond the snapshot they were given.

## Trust Boundaries

### 13.11 Boundary A — User boundary

The boundary between browser/client and backend. Must enforce:

* authn;
* session integrity;
* CSRF/XSS hardening;
* no secret exposure.

### 13.12 Boundary B — Control plane boundary

The boundary between API/Gateway and internal services. Must enforce:

* service authentication;
* command authorization;
* correlation propagation;
* auditability.

### 13.13 Boundary C — Execution boundary

The boundary between control plane and sandbox/execution plane. Must enforce:

* policy snapshot freeze;
* secret injection constraints;
* network isolation;
* terminal gating;
* no direct model provider credentials.

### 13.14 Boundary D — Storage boundary

The boundary between services and storage systems. Must enforce:

* separate DB credentials per ownership;
* schema-level isolation;
* object storage bucket/prefix policy;
* signed URL issuance control.

### 13.15 Boundary E — Audit boundary

The audit store must be treated as a separate trust boundary because audit is non-reconstructible. No service may modify or delete audit records after writing.

## Database Topology and Credential Isolation

### 13.16 Database strategy

Recommended:

* a single shared PostgreSQL cluster in the initial phase;
* schemas separated by ownership context;
* DB users separated by service;
* write permissions granted only to owned schemas.

Example schemas:

* `workspace_core`
* `orchestrator_core`
* `agent_runtime`
* `execution_core`
* `artifact_core`
* `audit_core`
* `policy_core`

### 13.17 DB credential rules

* Orchestrator service account: write only to `orchestrator_core`;
* Agent Runtime: write only to `agent_runtime`;
* Artifact Service: write only to `artifact_core`;
* API Gateway: no direct write to domain schemas;
* sandbox sidecars: no DB write credentials;
* debug tools / migration tools must not use application credentials.

### 13.18 Hard requirements from gate review

* PP1: no service other than the Orchestrator domain service may directly update `Task/Run/Step.status`;
* PP10: Artifact schema/tables must have real credential isolation, not just verbal convention;
* PP3: Agent Engine must have its own persistent store and recovery path.

## Event Bus, Event Store, and Outbox Topology

### 13.19 Event system components

The standard topology consists of three layers:

1. service-local outbox;
2. message relay / outbox dispatcher;
3. event bus / event store consumer ecosystem.

### 13.20 Outbox invariants in deployment

* every domain mutation that requires an event must write DB state + outbox in the same transaction;
* a service is only `ready` when its own outbox relay is healthy;
* after restart, a service must not accept new commands before reconciling the outbox backlog to at least a safe threshold.

### 13.21 Event persistence

At minimum requires:

* durable event store or durable bus retention;
* replay support for recovery/rebuild;
* partitioning by the scope locked in doc 06;
* correlation-searchable index.

## Recovery-aware Startup Topology

### 13.22 Standard startup order

1. database + object storage + event infrastructure + audit storage;
2. auth/policy/secret broker/model gateway;
3. artifact service;
4. orchestrator;
5. agent runtime;
6. execution plane / sandbox manager;
7. API/SSE gateways;
8. web shell.

Rationale:

* the control plane must not accept traffic before storage, policy, audit, and event infrastructure are ready;
* the runtime must not accept work before orchestrator and artifact service are available.

### 13.23 Readiness semantics

A service is considered ready if and only if:

* mandatory dependencies are reachable;
* own schema migrations are complete;
* own outbox relay is healthy;
* recovery/reconcile phase is complete;
* policy/audit constraints are in a valid mode.

### 13.24 Recovery order after crash

#### Orchestrator

* flush/reconcile outbox;
* rebuild `Task/Run/Step` state from event log + durable store;
* resume watchers;
* only then accept new commands.

#### Agent Runtime

* rebuild/reconcile `AgentInvocation` from durable store and event log;
* identify all invocations that have `started` but no terminal event;
* interrupt or reconcile them per policy before accepting new work.

#### Execution Plane

* enumerate sandboxes still active;
* cross-reference with runtime/orchestrator;
* terminate or rebind per policy;
* emit required events that are missing if a formal repair workflow exists.

### 13.25 Dual-crash requirement

If Orchestrator and Agent Runtime crash simultaneously, Agent Runtime must not assume there are no in-flight invocations. It must reconcile from the event log first. This is a hard requirement per gate review PP3.

## Sandbox Topology

### 13.26 Sandbox provisioning backend

The initial phase may use:

* local Docker runtime;
* Kubernetes jobs/pods;
* remote execution runners.

However, the abstraction must maintain the following common fields:

* sandbox id;
* sandbox attempt index;
* owning agent invocation id;
* policy snapshot hash;
* network profile;
* filesystem mounts;
* secret bindings;
* active flag.

### 13.27 Sandbox 1-N with AgentInvocation

An AgentInvocation may have multiple Sandbox records across different attempts, but only one active sandbox at any given time. The topology and schema must support `sandbox_attempt_index`. This is a mandatory clarification from the gate review.

### 13.28 Filesystem mounts

Clearly separated:

* workspace mount;
* uploads mount;
* outputs mount;
* temp mount;
* secrets mount.

`/secrets` must be unmounted before emitting `sandbox.terminated`.

## Object Storage Topology

### 13.29 Bucket/prefix strategy

Separated at minimum by group:

* uploads;
* repo snapshots;
* generated artifacts;
* logs/attachments if needed;
* quarantined/tainted artifacts if policy requires.

### 13.30 Signed URL issuance

Only the Artifact Service may issue signed URLs. URLs must be short-lived, scoped per artifact version, and subject to `state × taint × permission` checks at the time of issuance.

## Audit Topology

### 13.31 Audit durability

The audit store must have a higher durability SLA than regular logs because audit is non-reconstructible. The topology must prioritize:

* append-only storage;
* tamper-evident design if possible;
* separate backup;
* extremely restricted access.

### 13.32 Audit degraded mode

If an audit write for a mandatory decision fails, the system fails closed per docs 09 and 12. This must be reflected through readiness and circuit-breaking, not just in code logic.

## Realtime Topology

### 13.33 SSE gateway

The SSE gateway can scale statelessly if:

* the event source is durable;
* replay is supported via `Last-Event-ID`;
* subscription scope is enforced per workspace/task/run.

### 13.34 Realtime degradation

Loss of SSE must not change execution semantics. It only affects real-time observability; state truth remains in backend stores and event history.

## Topology-level Deployment SLOs

### 13.35 Suggested initial-phase SLOs

* API command ack: p95 < 500ms under normal conditions;
* SSE propagation: p95 < 2s for non-heavy events;
* Artifact lineage view: p95 < 2s;
* sandbox provisioning: per class, with a dedicated budget;
* startup recovery: bounded, observable, with phase logs.

## Topology Do-Not-Break Mapping

The topology must implement and must not break:

* DNB1 Run does not resume;
* DNB2 fail closed;
* DNB3 security violation does not auto-recover;
* DNB4 degraded mode does not auto-escalate permissions;
* DNB5 recovery produces events + audit;
* DNB6 artifact creation goes exclusively through Artifact Service;
* DNB7 trace_id = correlation_id;
* DNB8 execution trace ≠ provenance trace;
* DNB9 agent cannot self-escalate permissions;
* DNB10 state transition authority resides in Orchestrator;
* DNB11 taint write precedes event emit;
* DNB12 model version must not be an alias during artifact registration.

## Prohibited at the Topology Level

1. Having multiple services share a DB superuser in production mode.
2. Placing Artifact metadata and Orchestrator tables under the same write credential.
3. Allowing sandboxes to call model providers directly.
4. Allowing the API Gateway to directly write `Task/Run/Step` state.
5. Allowing debug scripts to modify artifact lineage outside of Artifact Service.
6. Allowing a service to accept traffic before outbox/recovery phase is complete.
7. Treating local mode as an exception to bypass security boundaries.
8. Giving audit storage the same durability level as debug logs.

## Expected Outcomes of Doc 13

After finalizing the topology, the team must be able to clearly answer:

* which service runs where;
* where trust boundaries are;
* which DB/schema credentials belong to whom;
* what the startup/recovery order is;
* where local/cloud/hybrid differ in placement;
* how pressure points PP1, PP3, PP10 are handled by the topology through infrastructure.

---

# Project Log Update

## Completed Progress

* Completed core docs 00–12
* Completed gate review 00–12
* Completed doc 13 Deployment Topology

## Clarifications / follow-ups to reflect in other docs

* Doc 04: add `sandbox_attempt_index` or equivalent flag for the 1-N relationship from AgentInvocation to Sandbox
* Doc 05: lock the `AgentInvocation compensated` → `Step failed` transition
* Doc 06: `run.timed_out` must emit a subsequent `run.cancelled` in the same outbox transaction
* Doc 12: approval timeout watcher must not depend solely on a scheduler; `run_config` lock + event emit must be in the same outbox transaction

## Proposed Next Steps

* 15 Backend Service Map
* 14 Frontend Application Map
* 16 Repo Structure Conventions
* 17 Implementation Roadmap
