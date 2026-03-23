# 01. System Goals and Non-goals

## System Goals

### G1. The system must be a work environment, not a chat box

Every design decision must prioritize the workspace, task, run, artifact, terminal, file, event, and agent lifecycle models. Chat is merely an interaction interface, not the architectural center.

### G2. The system must support multiple types of digital work on a unified backbone

At minimum, it must unify two major groups:

* online knowledge work;
* coding work.

All types of work must initially flow through the same backbone: workspace → task → orchestrator → agent runtime → tools/execution → artifact → observability.

### G3. The system must prioritize long-running, multi-step, stateful work

The system must handle tasks that cannot be completed in a single short prompt, including:

* analyzing large repos;
* scanning for bugs and generating reports;
* researching topics across multiple sources;
* creating plans and multi-part documents;
* tasks requiring multiple agents and many tool calls.

### G4. The system must have local/cloud/hybrid architecture from the foundation

Agent OS resources may come from:

* the user's local machine;
* cloud compute;
* online services;
* object storage from the cloud or on-premises.

The architecture must treat this as a core characteristic, not an add-on feature.

### G5. The system must be observable and controllable

Users must be able to see:

* which tasks are running;
* what each agent is doing;
* which tool was just called;
* which file was just created or modified;
* where progress stands and where errors occurred;
* how much model or compute resources have been consumed.

At the same time, users must have the ability to:

* stop;
* modify instructions;
* approve/reject;
* manually intervene;
* rerun.

### G6. The system must be permissioned and auditable

AI must not be assumed to have full access. The system must support:

* workspace-level permissions;
* tool-level permissions;
* agent-level permissions;
* policy-driven secret provisioning;
* action logging and artifact lineage tracking.

### G7. The system must be tool-first and online-first

Since the system is oriented toward online and coding work, online tools, APIs, browser automation, file operations, terminal, repo access, and data connectors must be core capabilities.

### G8. The system must be engine-agnostic and model-agnostic

Agent OS must not be locked to a single model or engine. The system must be abstract enough to swap:

* model providers;
* agent engines;
* execution backends;
* connector protocols.

### G9. The system must be artifact-centric

Every valuable work output must become an artifact that can be saved, viewed, traced, shared, and reused. Examples:

* reports;
* patches;
* generated files;
* logs;
* JSON findings;
* summaries;
* repo snapshots.

### G10. The system must maintain its operating system identity at the product level

The overall experience must be: open a workspace, view tasks, manage agents, orchestrate resources, monitor outputs. The product must not drift into becoming a chat assistant with auxiliary panels.

## Non-goals

### N1. Do not build a general-purpose chatbot with a shell wrapper

The chat UI must not become the core logic of the entire system.

### N2. Do not optimize for intensive creative graphics in the initial phase

Use cases such as heavy graphic design, intensive video production, and large-scale media creation must not drive initial architecture decisions.

### N3. Do not lock the system to a single AI or cloud provider

The system must not have a critical dependency on any single provider for models, storage, sandboxing, or execution.

### N4. Do not conflate the orchestrator and the agent engine

Work orchestration and agent reasoning logic are two separate layers; their responsibilities must not be mixed.

### N5. Do not let the frontend directly control sensitive execution

The frontend is only a control shell. Execution authority must go through backend services, policy, and audit.

### N6. Do not assume AI will be perfectly correct

The system must be designed for human intervention, failure, uncertainty, and the need for verification.

### N7. Do not overfit to a single use case

Repo auditing is a very strong use case, but Agent OS must not become locked into being a "code audit platform." It must retain its platform shape for many types of digital work.
