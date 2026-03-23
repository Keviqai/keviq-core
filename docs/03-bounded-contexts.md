# 03. Bounded Contexts

The bounded contexts below divide the system into clearly defined domains of responsibility. These form the basis for the service map, repo structure, API contracts, and ownership going forward.

## C1. Identity and Access Context

### Responsibilities

* users;
* organizations/teams;
* workspace membership;
* roles;
* sessions;
* access policies;
* secret ownership baseline.

### Not Responsible For

* task scheduling;
* reasoning;
* artifact generation.

### Core Entities

* User
* Organization
* WorkspaceMember
* RoleBinding
* Session

## C2. Workspace Context

### Responsibilities

* defining logical workspaces;
* workspace metadata;
* workspace default configuration;
* linking repos, file roots, policies, and assets to a workspace.

### Core Entities

* Workspace
* WorkspaceSettings
* WorkspaceProfile
* WorkspaceConnection

### Notes

Workspace is the foundational unit of work in Agent OS. Most important objects must belong to a workspace.

## C3. Task Orchestration Context

### Responsibilities

* task creation;
* decomposition;
* dependency graphs;
* scheduling;
* retries;
* cancellation;
* concurrency policy;
* run lifecycle at the orchestration level.

### Core Entities

* Task
* TaskDependency
* TaskRun
* SchedulePolicy
* RetryPolicy
* RunAssignment

### Notes

This is the context closest to a "kernel/control plane." It does not perform detailed reasoning; it organizes the flow of work.

## C4. Agent Runtime Context

### Responsibilities

* bootstrapping agents;
* maintaining runtime state for a run;
* managing prompt/runtime configuration;
* tool invocation flow;
* internal sub-agent logic if applicable;
* summary/reasoning outputs;
* memory within the runtime scope.

### Core Entities

* AgentProfile
* AgentInvocation
* RuntimeState
* ToolCall
* ToolResult
* RuntimeSummary

### Notes

This is where an engine such as DeerFlow, LangGraph, or an internal engine would reside.

## C5. Tool and Connector Context

### Responsibilities

* capability registry;
* connectors for Git, browser, API, MCP, file operations;
* tool schemas;
* tool execution policy;
* tool metadata.

### Core Entities

* ToolDefinition
* ConnectorDefinition
* CapabilityBinding
* ToolPolicy
* ConnectorCredentialRef

### Notes

This context defines "what the system can do" and "what it is allowed to do," but it does not decide when to act.

## C6. Execution and Sandbox Context

### Responsibilities

* provisioning execution environments;
* mounting workspace/uploads/outputs;
* terminal sessions;
* resource quotas;
* secret injection;
* network policy;
* teardown/archive.

### Core Entities

* Sandbox
* SandboxProfile
* SandboxLease
* ResourceQuota
* NetworkPolicy
* SecretBinding

### Notes

This is the hard execution boundary of the system.

## C7. Artifact and File Context

### Responsibilities

* repo snapshots;
* uploads;
* outputs;
* generated reports;
* patches;
* file previews;
* artifact lineage;
* view/download permissions.

### Core Entities

* Artifact
* ArtifactVersion
* ArtifactLineage
* RepoSnapshot
* FileHandle

### Notes

Artifact is a first-class object. It must not be treated as a mere file attachment.

## C8. Event and Telemetry Context

### Responsibilities

* event schema;
* publish/subscribe semantics;
* correlation ids;
* audit log;
* metrics;
* traces;
* run timeline.

### Core Entities

* DomainEvent
* AuditRecord
* MetricSample
* TraceSpan
* TimelineEntry

### Notes

This is the context that ensures observability, replayability, and debuggability.

## C9. Model Gateway Context

### Responsibilities

* provider selection;
* model routing;
* fallback;
* token accounting;
* cost tracking;
* quotas;
* policy caching if needed.

### Core Entities

* ModelProvider
* ModelProfile
* ModelRoute
* UsageRecord
* BudgetPolicy

### Notes

Model access must be consolidated here to maintain engine-agnostic and provider-agnostic properties.

## C10. Human Control Context

### Responsibilities

* clarification requests;
* approvals;
* pause/resume;
* manual intervention;
* rerun triggers;
* operator notes.

### Core Entities

* ApprovalRequest
* ClarificationRequest
* InterventionAction
* ResumeToken
* OperatorNote

### Notes

This is the domain dedicated to human participation in the work lifecycle.

## C11. Web Shell Context

### Responsibilities

* desktop shell;
* window/panel layout;
* workspace navigation;
* task manager UI;
* file explorer UI;
* terminal UI;
* notifications;
* realtime rendering.

### Not Responsible For

* source of truth for runtime state;
* execution logic;
* backend policy enforcement.

### Interface Entities

* ViewState
* PanelState
* SubscriptionState
* NotificationItem

## High-level Relationships Between Contexts

1. **Identity and Access** grants access to **Workspace**.
2. **Workspace** is the anchor for **Task Orchestration**, **Artifacts**, **Tools**, and **Policies**.
3. **Task Orchestration** creates **TaskRun** instances and assigns them to **Agent Runtime** or execution workers.
4. **Agent Runtime** uses **Tool and Connector** along with **Model Gateway**.
5. **Execution and Sandbox** provides environments for side-effecting tools to operate.
6. **Artifact and File** stores inputs/outputs/snapshots from all runs.
7. **Event and Telemetry** observes all contexts.
8. **Human Control** can block, modify, or approve segments of the execution flow.
9. **Web Shell** displays and controls everything through APIs and event streams.
