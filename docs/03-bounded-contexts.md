# 03. Bounded Contexts

Các bounded context dưới đây chia hệ thành những miền trách nhiệm rõ ràng. Đây là nền cho service map, repo structure, API contracts và ownership sau này.

## C1. Identity and Access Context

### Trách nhiệm

* người dùng;
* tổ chức/nhóm;
* workspace membership;
* role;
* session;
* access policy;
* secret ownership baseline.

### Không chịu trách nhiệm

* scheduling task;
* reasoning;
* artifact generation.

### Thực thể lõi

* User
* Organization
* WorkspaceMember
* RoleBinding
* Session

## C2. Workspace Context

### Trách nhiệm

* định nghĩa không gian làm việc logic;
* metadata của workspace;
* cấu hình mặc định của workspace;
* liên kết repo, file root, policies và assets của workspace.

### Thực thể lõi

* Workspace
* WorkspaceSettings
* WorkspaceProfile
* WorkspaceConnection

### Ghi chú

Workspace là đơn vị làm việc nền tảng của Agent OS. Hầu hết object quan trọng đều phải thuộc về một workspace.

## C3. Task Orchestration Context

### Trách nhiệm

* tạo task;
* decomposition;
* dependency graph;
* scheduling;
* retry;
* cancellation;
* concurrency policy;
* run lifecycle ở cấp điều phối.

### Thực thể lõi

* Task
* TaskDependency
* TaskRun
* SchedulePolicy
* RetryPolicy
* RunAssignment

### Ghi chú

Đây là ngữ cảnh gần với "kernel/control plane" nhất. Nó không làm reasoning chi tiết; nó tổ chức dòng công việc.

## C4. Agent Runtime Context

### Trách nhiệm

* dựng agent;
* giữ runtime state cho một run;
* quản lý prompt/runtime config;
* tool invocation flow;
* sub-agent logic nội bộ nếu có;
* summary/reasoning outputs;
* memory trong phạm vi runtime.

### Thực thể lõi

* AgentProfile
* AgentInvocation
* RuntimeState
* ToolCall
* ToolResult
* RuntimeSummary

### Ghi chú

Đây là nơi một engine kiểu DeerFlow, LangGraph hay engine nội bộ sẽ sống.

## C5. Tool and Connector Context

### Trách nhiệm

* capability registry;
* connector tới Git, browser, API, MCP, file operations;
* tool schema;
* tool execution policy;
* tool metadata.

### Thực thể lõi

* ToolDefinition
* ConnectorDefinition
* CapabilityBinding
* ToolPolicy
* ConnectorCredentialRef

### Ghi chú

Ngữ cảnh này định nghĩa "hệ có thể làm gì" và "được phép làm gì", nhưng không tự quyết định khi nào làm.

## C6. Execution and Sandbox Context

### Trách nhiệm

* cấp phát môi trường thực thi;
* mount workspace/uploads/outputs;
* terminal session;
* resource quota;
* secret injection;
* network policy;
* teardown/archive.

### Thực thể lõi

* Sandbox
* SandboxProfile
* SandboxLease
* ResourceQuota
* NetworkPolicy
* SecretBinding

### Ghi chú

Đây là execution boundary cứng của hệ.

## C7. Artifact and File Context

### Trách nhiệm

* repo snapshots;
* uploads;
* outputs;
* generated reports;
* patches;
* file previews;
* lineage của artifact;
* quyền xem/tải về.

### Thực thể lõi

* Artifact
* ArtifactVersion
* ArtifactLineage
* RepoSnapshot
* FileHandle

### Ghi chú

Artifact là đối tượng hạng nhất. Không được xem nó chỉ là tệp đính kèm phụ.

## C8. Event and Telemetry Context

### Trách nhiệm

* event schema;
* publish/subscribe semantics;
* correlation ids;
* audit log;
* metrics;
* traces;
* run timeline.

### Thực thể lõi

* DomainEvent
* AuditRecord
* MetricSample
* TraceSpan
* TimelineEntry

### Ghi chú

Đây là ngữ cảnh đảm bảo observability, replayability và debuggability.

## C9. Model Gateway Context

### Trách nhiệm

* chọn provider;
* route model;
* fallback;
* token accounting;
* cost tracking;
* quota;
* caching chính sách nếu cần.

### Thực thể lõi

* ModelProvider
* ModelProfile
* ModelRoute
* UsageRecord
* BudgetPolicy

### Ghi chú

Model access phải được gom vào đây để giữ engine-agnostic và provider-agnostic.

## C10. Human Control Context

### Trách nhiệm

* clarification requests;
* approvals;
* pause/resume;
* manual intervention;
* rerun triggers;
* operator notes.

### Thực thể lõi

* ApprovalRequest
* ClarificationRequest
* InterventionAction
* ResumeToken
* OperatorNote

### Ghi chú

Đây là miền dành riêng cho việc con người tham gia vào vòng đời công việc.

## C11. Web Shell Context

### Trách nhiệm

* desktop shell;
* window/panel layout;
* workspace navigation;
* task manager UI;
* file explorer UI;
* terminal UI;
* notifications;
* realtime rendering.

### Không chịu trách nhiệm

* source of truth cho runtime state;
* execution logic;
* policy enforcement ở backend.

### Thực thể giao diện

* ViewState
* PanelState
* SubscriptionState
* NotificationItem

## Quan hệ mức cao giữa các context

1. **Identity and Access** cấp quyền vào **Workspace**.
2. **Workspace** là nơi neo cho **Task Orchestration**, **Artifacts**, **Tools**, **Policies**.
3. **Task Orchestration** sinh ra **TaskRun** và giao cho **Agent Runtime** hoặc execution workers.
4. **Agent Runtime** dùng **Tool and Connector** cùng **Model Gateway**.
5. **Execution and Sandbox** cung cấp môi trường để tool có side effect hoạt động.
6. **Artifact and File** lưu input/output/snapshot của mọi run.
7. **Event and Telemetry** quan sát tất cả context.
8. **Human Control** có thể chặn, sửa hoặc duyệt các đoạn của luồng chạy.
9. **Web Shell** hiển thị và điều khiển tất cả thông qua API và event streams.
