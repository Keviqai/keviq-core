# 00. Product Vision

## Tên tạm thời

Agent OS

## Tuyên ngôn sản phẩm

Agent OS là một **hệ điều hành công việc mới** dành cho những người muốn ứng dụng AI vào công việc hằng ngày của họ. Hệ này không được thiết kế như một chatbot, một bộ công cụ rời rạc, hay một dashboard tự động hóa đơn thuần. Nó được thiết kế như một **môi trường làm việc hoàn chỉnh**, nơi con người, AI agent, dữ liệu, công cụ trực tuyến và tài nguyên tính toán cùng tồn tại trong một không gian điều hành thống nhất.

Agent OS phải cho phép nhiều nhóm người dùng khác nhau cùng khai thác AI theo cách có cấu trúc:

* người làm kỹ thuật dùng nó để đọc code, phân tích repo, viết code, chạy test, sửa lỗi, sinh báo cáo;
* người làm marketing dùng nó để nghiên cứu, tổng hợp, lập kế hoạch, theo dõi chiến dịch, tạo tài liệu làm việc;
* nhà quản lý dùng nó để điều phối công việc, theo dõi tiến độ, tổng hợp thông tin, tạo báo cáo, giám sát tác vụ do AI thực hiện.

## Bản chất hệ thống

Agent OS là một hệ điều hành mới theo nghĩa chức năng, không theo nghĩa kernel truyền thống. Nó phải đóng vai trò:

* là **vỏ làm việc** cho người dùng trên nền web;
* là **bộ điều phối** cho tác vụ và nhiều agent;
* là **môi trường thực thi** cho các công việc trực tuyến và coding;
* là **lớp quản trị tài nguyên, quyền hạn, artifact, và trạng thái**;
* là **cầu nối giữa người dùng, AI model, agent engine, công cụ trực tuyến và tài nguyên local/cloud**.

## Định vị khác biệt

Agent OS không cạnh tranh bằng một model riêng. Giá trị cốt lõi nằm ở:

* khả năng tổ chức công việc bằng AI ở cấp hệ điều hành;
* khả năng chạy và kiểm soát nhiều agent một cách có cấu trúc;
* khả năng kết nối online tools và coding tools trong cùng một môi trường;
* khả năng giữ ngữ cảnh công việc theo workspace thay vì theo từng cuộc chat rời rạc;
* khả năng quan sát, can thiệp và kiểm soát hoạt động của AI trong thời gian thực.

## Đối tượng người dùng ưu tiên

Phiên bản đầu tiên hướng tới:

* cá nhân làm việc cường độ cao với máy tính;
* nhóm kỹ thuật nhỏ đến trung bình;
* người làm việc tri thức cần dùng AI cho nghiên cứu, tổng hợp, phân tích, lập kế hoạch, tạo tài liệu và coding.

Hệ không khóa chặt vào một vai trò duy nhất. Mục tiêu là tạo một nền móng đủ mạnh để mở rộng sang nhiều loại công việc khác nhau, miễn là các công việc đó chủ yếu diễn ra qua internet, qua tài liệu số, qua phần mềm, qua dữ liệu và qua môi trường lập trình.

## Trục use case ưu tiên

Agent OS phải làm rất tốt các nhóm công việc sau:

1. **online knowledge work**: nghiên cứu, tổng hợp, báo cáo, phân tích, lập kế hoạch, theo dõi công việc;
2. **coding work**: đọc repo, audit code, sửa lỗi, refactor, tạo patch, chạy test, sinh artifact kỹ thuật;
3. **multi-step digital workflows**: tác vụ kéo dài nhiều bước, cần nhiều agent, cần nhiều công cụ online, cần quản lý file và báo cáo.

## Những gì chưa ưu tiên ở giai đoạn đầu

Giai đoạn đầu **không** lấy các loại công việc sau làm trọng tâm:

* thiết kế đồ họa chuyên sâu;
* dựng phim, 3D, CAD;
* xử lý media nặng theo thời gian thực;
* điều khiển phần cứng phức tạp;
* các workflow đòi hỏi UI đồ họa chuyên biệt như Figma-class editor hoặc Adobe-class editor.

Điều này không có nghĩa hệ không bao giờ hỗ trợ, mà nghĩa là kiến trúc giai đoạn đầu không được bẻ cong vì các use case đó.

## Tầm nhìn dài hạn

Về dài hạn, Agent OS phải giống một "Linux của công việc AI-native":

* có shell giao diện riêng;
* có process/task model riêng;
* có workspace/file/artifact model riêng;
* có permission/security model riêng;
* có khả năng chạy local, cloud, hoặc hybrid;
* có khả năng cắm nhiều model, nhiều engine, nhiều connector, nhiều execution backend.

Hệ phải tồn tại như một **platform**, không chỉ là một sản phẩm một tính năng.

---

# 01. System Goals and Non-goals

## System Goals

### G1. Hệ phải là một môi trường làm việc, không phải hộp chat

Mọi quyết định thiết kế phải ưu tiên mô hình workspace, task, run, artifact, terminal, file, event, agent lifecycle. Chat chỉ là một giao diện tương tác, không phải trung tâm kiến trúc.

### G2. Hệ phải hỗ trợ nhiều loại công việc số trên một trục thống nhất

Ít nhất phải thống nhất được hai nhóm chính:

* công việc trực tuyến tri thức;
* công việc coding.

Mọi loại công việc ban đầu phải đi qua cùng một xương sống: workspace → task → orchestrator → agent runtime → tools/execution → artifact → observability.

### G3. Hệ phải ưu tiên công việc kéo dài, nhiều bước, có trạng thái

System phải xử lý tốt các tác vụ không thể hoàn thành trong một prompt ngắn, bao gồm:

* phân tích repo lớn;
* quét lỗi và tạo báo cáo;
* nghiên cứu chủ đề nhiều nguồn;
* lên kế hoạch và tạo tài liệu nhiều phần;
* tác vụ cần nhiều agent và nhiều tool calls.

### G4. Hệ phải có kiến trúc local/cloud/hybrid ngay từ nền móng

Tài nguyên của Agent OS có thể đến từ:

* máy local của người dùng;
* cloud compute;
* dịch vụ online;
* object storage từ cloud hoặc tại chỗ.

Kiến trúc phải chấp nhận điều này như một đặc tính cốt lõi, không phải tính năng phụ.

### G5. Hệ phải observable và controllable

Người dùng phải thấy được:

* task nào đang chạy;
* agent nào đang làm gì;
* tool nào vừa được gọi;
* file nào vừa được tạo hoặc thay đổi;
* tiến độ và lỗi ở đâu;
* chi phí model hoặc tài nguyên tính toán tiêu tốn bao nhiêu.

Đồng thời người dùng phải có khả năng:

* dừng;
* sửa chỉ dẫn;
* duyệt/không duyệt;
* can thiệp thủ công;
* chạy lại.

### G6. Hệ phải permissioned và auditable

Không được giả định AI có toàn quyền. Hệ phải hỗ trợ:

* phân quyền theo workspace;
* phân quyền theo công cụ;
* phân quyền theo agent;
* cấp phát secrets theo policy;
* ghi nhật ký hành động và lineage của artifact.

### G7. Hệ phải tool-first và online-first

Vì định hướng công việc của hệ chủ yếu là trực tuyến và coding, nên công cụ online, API, browser automation, file operations, terminal, repo access và data connectors phải là năng lực lõi.

### G8. Hệ phải engine-agnostic và model-agnostic

Agent OS không được khóa vào một model hay một engine duy nhất. Hệ phải đủ trừu tượng để thay:

* model provider;
* agent engine;
* execution backend;
* connector protocol.

### G9. Hệ phải artifact-centric

Mọi kết quả làm việc có giá trị phải trở thành artifact có thể lưu, xem, truy vết, chia sẻ và tái sử dụng. Ví dụ:

* báo cáo;
* patch;
* file sinh ra;
* log;
* findings JSON;
* summary;
* repo snapshot.

### G10. Hệ phải giữ vững tính hệ điều hành ở cấp sản phẩm

Trải nghiệm tổng phải là: mở workspace, xem task, quản lý agent, điều phối tài nguyên, theo dõi outputs. Không để sản phẩm trôi thành một trợ lý chat có nhiều panel phụ.

## Non-goals

### N1. Không xây một chatbot đa năng rồi bọc shell bên ngoài

Chat UI không được phép trở thành lõi logic của toàn hệ.

### N2. Không tối ưu cho đồ họa sáng tạo chuyên sâu ở giai đoạn đầu

Các use case như thiết kế đồ họa nặng, dựng video chuyên sâu, sáng tạo media lớn không được chi phối kiến trúc giai đoạn đầu.

### N3. Không gắn chặt hệ vào một nhà cung cấp AI hay cloud duy nhất

System không được phụ thuộc sống còn vào một provider duy nhất cho model, storage, sandbox hay execution.

### N4. Không đồng nhất orchestrator và agent engine

Điều phối công việc và logic suy luận của agent là hai lớp riêng, không được trộn trách nhiệm.

### N5. Không để frontend trực tiếp điều khiển execution nhạy cảm

Frontend chỉ là shell điều khiển. Quyền thực thi phải đi qua backend services, policy và audit.

### N6. Không kỳ vọng AI tự động đúng tuyệt đối

Hệ phải được thiết kế cho sự can thiệp của con người, sự thất bại, sự không chắc chắn và sự cần kiểm chứng.

### N7. Không overfit vào một use case đơn lẻ

Repo audit là một use case rất mạnh, nhưng Agent OS không được bị khóa thành “nền tảng audit code”. Nó phải giữ được hình dạng platform cho nhiều công việc số.

---

# 02. Architectural Invariants

Các invariant dưới đây là những nguyên tắc bất biến. Trong quá trình phát triển, nếu một giải pháp làm vỡ invariant, mặc định coi giải pháp đó là sai trừ khi có quyết định kiến trúc mới ở cấp hệ thống.

## I1. Web UI là shell, không phải core

Frontend chỉ là lớp hiển thị và điều khiển. Mọi logic quan trọng liên quan đến task orchestration, execution, policy, persistence, artifact và security phải nằm ở backend services.

## I2. Orchestrator và Agent Engine là hai lớp riêng

* **Orchestrator** chịu trách nhiệm task graph, scheduling, retries, dependency, concurrency, cancellation, coordination.
* **Agent Engine** chịu trách nhiệm reasoning, stateful tool use, memory, sub-agent logic trong phạm vi một run.

Không lớp nào được nuốt trách nhiệm cốt lõi của lớp kia.

## I3. Mọi công việc phải đi qua mô hình chuẩn: Workspace → Task → Run → Step → Artifact

Không được có đường tắt bypass hệ mô hình lõi bằng cách cho UI gọi thẳng tool hoặc cho agent sinh output mà không gắn lineage vào task/run.

## I4. Artifact là first-class object

Mọi output có giá trị phải được lưu như artifact có metadata, ownership, lineage, preview info và quyền truy cập. Output chỉ tồn tại trong log hoặc chat transcript là chưa đủ.

## I5. Sandbox là execution boundary chuẩn

Mọi hành động nhạy cảm hoặc có side effect như:

* chạy bash;
* truy cập repo local;
* ghi file;
* chạy test/build;
* browser automation;
* network actions

phải được thực hiện trong execution environment được quản lý bởi sandbox policy hoặc execution backend tương đương.

## I6. Sandbox phải ephemeral và policy-driven

Sandbox không được là môi trường mơ hồ sống mãi không kiểm soát. Mỗi sandbox phải có:

* lifecycle rõ ràng;
* resource quota;
* network policy;
* secret policy;
* ownership theo workspace/run;
* cleanup/archive semantics.

## I7. Mọi thay đổi trạng thái dài hạn phải có persistence hoặc event contract chuẩn

Trạng thái hệ thống không được tồn tại âm thầm chỉ trong bộ nhớ tiến trình. Nếu trạng thái cần được UI, audit, retry hoặc recovery nhìn thấy thì nó phải đi qua DB hoặc event bus với schema chuẩn.

## I8. Event model là xương sống thần kinh của hệ

Mọi service phải giao tiếp theo hợp đồng sự kiện chuẩn hóa về:

* event type;
* correlation id;
* causation id;
* timestamp;
* source;
* payload schema.

Không để mỗi service tự phát event theo kiểu riêng.

## I9. Hệ phải reproducible theo snapshot + config + artifact lineage

Một run quan trọng phải có thể được truy vết thông qua:

* repo snapshot hoặc input snapshot;
* task spec;
* runtime config;
* model usage;
* tools đã gọi;
* artifacts đã sinh ra.

Không đạt điều này thì hệ không đủ tư cách là một platform làm việc nghiêm túc.

## I10. Permissions phải tồn tại ở nhiều lớp

Ít nhất phải có các lớp sau:

* user-to-workspace;
* agent-to-tool;
* run-to-secret;
* sandbox-to-network;
* artifact-to-view/download.

Không được giản lược toàn bộ security thành mỗi đăng nhập user.

## I11. Frontend không được giữ source of truth cho runtime state

Frontend có thể cache hoặc render tạm thời, nhưng source of truth cho task, run, artifact, sandbox, permissions phải ở backend.

## I12. Model layer phải là replaceable dependency

Không được mã hóa kiến trúc sao cho mọi service biết chi tiết provider model. Model access phải qua model gateway hoặc abstraction tương đương.

## I13. Tooling layer phải tách khỏi reasoning layer

Agent có thể quyết định gọi tool nào, nhưng bản thân tool implementation, capability registry và execution policy phải tách khỏi prompt/reasoning logic.

## I14. Human-in-the-loop là cơ chế lõi, không phải addon

Hệ phải thiết kế sẵn các điểm can thiệp:

* clarification;
* approval;
* pause/resume;
* manual override;
* rerun.

Không thiết kế theo giả định mọi tác vụ đều tự động hoàn toàn.

## I15. Local, cloud và hybrid đều là topology hợp lệ

Kiến trúc không được mặc định rằng mọi thứ chạy cloud hoặc mọi thứ chạy local. System phải giữ abstraction đủ để hỗ trợ ba chế độ:

* local-first;
* cloud-first;
* hybrid.

---

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

Đây là ngữ cảnh gần với “kernel/control plane” nhất. Nó không làm reasoning chi tiết; nó tổ chức dòng công việc.

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

Ngữ cảnh này định nghĩa “hệ có thể làm gì” và “được phép làm gì”, nhưng không tự quyết định khi nào làm.

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

---

# Quy ước nền tảng cho dự án

## Quy ước đặt tên

* Tài liệu: `NN-topic-name.md`
* Service: `kebab-case`
* Python package: `snake_case`
* TypeScript file: `kebab-case.ts` hoặc `PascalCase.tsx` cho component
* DB table: `snake_case` số nhiều
* Event type: `dotted.case`
* API path: `/v1/...`
* ID chuẩn: `prefix_uuid` hoặc `prefix_nanoid`

## Quy ước mô hình

* Mọi object nghiệp vụ quan trọng phải có `id`, `workspace_id`, `created_at`, `updated_at`
* Mọi object chạy thực tế phải có `status`
* Mọi resource có side effect phải có owner rõ ràng
* Mọi run quan trọng phải có correlation id xuyên suốt event chain

---

# Project Log

## Tiến độ đã hoàn thành

* Đã chốt triết lý: architecture-first, implementation-increments
* Đã chốt định vị sản phẩm: Agent OS là hệ điều hành công việc AI-native trên nền web
* Đã chốt đối tượng và use case nền: knowledge work trực tuyến + coding work
* Đã chốt hướng topology: local / cloud / hybrid đều là hợp lệ
* Đã hoàn thành bộ tài liệu nền 00–03 gồm vision, goals, invariants, bounded contexts

## Chưa thực hiện

* Core domain model chi tiết
* State machines
* Event contracts cụ thể
* API contracts
* Sandbox security model chi tiết
* Permission model chi tiết
* Repo structure chính thức
* Service map chính thức

## Trạng thái cấu trúc dự án

* Chưa tạo code repository chính thức
* Chưa tạo service skeleton
* Chưa khóa DB schema
* Chưa khóa event schema
* Chưa khóa deployment topology

## Bước tiếp theo đề xuất

* 04 Core Domain Model
* 05 State Machines
* 06 Event Contracts
* 07 API Contracts

---

# 13. Deployment Topology

## Mục tiêu của topology

Deployment topology phải hiện thực đúng toàn bộ kiến trúc lõi đã khóa ở docs 00–12. Topology không được tự tạo ra đường tắt triển khai khiến API bypass state machine, service viết chéo vào bảng không sở hữu, policy fail-open, hoặc event/outbox bị xem nhẹ. Mọi quyết định topology phải phục vụ các do-not-break (DNB1–DNB12) và các pressure points từ gate review.

## Nguyên tắc topology bất biến

### T13-1. Topology phải tôn trọng bounded contexts

Mỗi bounded context quan trọng phải có deployment responsibility rõ ràng. Không bắt buộc mỗi context là một process riêng, nhưng bắt buộc mỗi context có owner runtime, storage boundary và credential boundary rõ ràng.

### T13-2. State transition authority phải nằm ở Orchestrator domain service

Bất kỳ topology nào cũng phải đảm bảo chỉ Orchestrator domain service được phép mutate trạng thái của `Task`, `Run`, `Step`. Không service nào khác có database write quyền trực tiếp lên các status field đó.

### T13-3. Artifact service phải có storage boundary thật

Artifact metadata và artifact content phải được bảo vệ bằng boundary triển khai thật sự: DB credentials riêng cho metadata, object storage credentials riêng cho blob, và không service nào ngoài Artifact service có write access trực tiếp vào artifact metadata tables.

### T13-4. Event log và outbox là hạ tầng bắt buộc

Không topology nào hợp lệ nếu bỏ qua outbox hoặc xem event bus như chi tiết tùy chọn. Event store / message bus là thành phần first-class của deployment.

### T13-5. Fail closed phải đúng cả khi dependency down

Nếu auth, policy, secret broker, audit, hay model gateway bị down, topology phải khiến hệ fail closed thay vì fail open.

### T13-6. Local, cloud, hybrid đều là topology hợp lệ

Kiến trúc triển khai phải hỗ trợ ba mode:

* local-first;
* cloud-first;
* hybrid.

Khác biệt giữa các mode được nằm ở placement của service, storage, execution backend và trust boundary, không được làm thay đổi domain model.

### T13-7. Recovery order là một phần của topology

Startup order, readiness semantics, recovery sequence và degraded modes là thành phần của topology chứ không phải ghi chú vận hành phụ.

## Deployment units cấp cao

### 13.1 Web Shell

Vai trò:

* cung cấp UI shell;
* gọi API;
* subscribe SSE;
* render timeline, artifact lineage, task graph, terminal.

Boundary:

* không giữ source of truth;
* không cầm secrets hệ thống;
* không gọi model provider hay sandbox trực tiếp.

### 13.2 API Surface

Bao gồm:

* API Gateway / BFF;
* SSE Gateway.

Vai trò:

* command/query/human intervention surface;
* authn/authz entry point;
* response shaping;
* SSE fan-out cho client.

Boundary:

* không thực thi business state transition trực tiếp;
* không mutate domain state ngoài việc gọi đúng domain service.

### 13.3 Orchestrator Plane

Vai trò:

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

Vai trò:

* chạy AgentInvocation;
* duy trì runtime state của agent;
* tool orchestration;
* summary generation;
* runtime-side event emission;
* reconcile state sau restart.

Storage authority:

* `AgentInvocation` runtime state của chính nó.

### 13.5 Execution Plane

Bao gồm:

* Sandbox Manager;
* terminal session broker;
* execution sidecars nếu cần;
* network policy enforcement;
* secret mounting subsystem.

Storage authority:

* `Sandbox` metadata;
* execution logs tạm thời;
* terminal session metadata.

### 13.6 Artifact Plane

Bao gồm:

* Artifact Service;
* object storage;
* artifact preview subsystem;
* signed URL issuer.

Storage authority:

* `Artifact`, `ArtifactVersion`, `ArtifactLineage` metadata;
* object blobs.

### 13.7 Control Services

Bao gồm:

* Auth / Identity;
* Policy service;
* Secret broker;
* Model Gateway;
* Audit service;
* Event bus / Event store;
* telemetry stack.

## Deployment topology chuẩn theo mode

### 13.8 Local-first topology

Phù hợp cho:

* developer machine;
* small team lab;
* self-hosted cá nhân.

Cấu hình khuyến nghị:

* Web Shell: local browser + local frontend server;
* API Gateway, Orchestrator, Agent Runtime, Artifact Service, Sandbox Manager: chạy trong Docker Compose;
* PostgreSQL, Redis, object storage compatible, event bus: local containers;
* sandboxes: local Docker runtime;
* model gateway: local proxy + optional cloud provider access.

Đặc tính:

* đơn giản triển khai;
* debugging mạnh;
* trust boundary yếu hơn cloud nhưng vẫn phải giữ credential boundary logic;
* phù hợp cho development và single-node operation.

Điều cấm:

* không vì local mode mà cho mọi service dùng chung DB superuser;
* không vì local mode mà bypass artifact isolation hay state transition authority.

### 13.9 Cloud-first topology

Phù hợp cho:

* managed deployment;
* multi-tenant hoặc enterprise-managed environment.

Cấu hình khuyến nghị:

* Web Shell: CDN / edge served;
* API/SSE Gateway: autoscaled stateless services;
* Orchestrator: replicated control plane với leader election hoặc single writer discipline;
* Agent Runtime: horizontally scaled workers;
* Sandbox Manager: control service cho container runtime / Kubernetes jobs;
* object storage: managed S3-compatible;
* database: managed PostgreSQL;
* event bus: clustered deployment;
* audit storage: durable managed store tách riêng.

Đặc tính:

* scale tốt;
* policy và credential boundary rõ;
* cần readiness, startup ordering, reconcilers mạnh;
* cần hard multi-tenant isolation nếu đi enterprise.

### 13.10 Hybrid topology

Phù hợp cho:

* UI/control plane trên cloud;
* execution hoặc repo/data giữ local hoặc VPC riêng.

Mô hình chuẩn:

* Web Shell + API Surface + Orchestrator: cloud;
* local execution gateway hoặc self-hosted runner: on-prem / laptop / VPC riêng;
* Artifact plane: có thể cloud, local, hoặc split theo sensitivity;
* model gateway: cloud proxy nhưng policy-aware;
* secrets: scoped theo execution site.

Điều kiện bắt buộc:

* execution site phải được xem như một trust boundary riêng;
* event relay, audit relay và policy snapshot phải nhất quán giữa cloud plane và local execution plane;
* không cho phép execution node tự quyết định policy ngoài snapshot được cấp.

## Trust boundaries

### 13.11 Boundary A — User boundary

Ranh giới giữa browser/client và backend. Ở đây phải enforce:

* authn;
* session integrity;
* CSRF/XSS hardening;
* không lộ secrets.

### 13.12 Boundary B — Control plane boundary

Ranh giới giữa API/Gateway và internal services. Ở đây phải enforce:

* service authentication;
* command authorization;
* correlation propagation;
* auditability.

### 13.13 Boundary C — Execution boundary

Ranh giới giữa control plane và sandbox/execution plane. Ở đây phải enforce:

* policy snapshot freeze;
* secret injection constraints;
* network isolation;
* terminal gating;
* no direct model provider credentials.

### 13.14 Boundary D — Storage boundary

Ranh giới giữa services và storage systems. Ở đây phải enforce:

* DB credentials riêng theo ownership;
* schema-level isolation;
* object storage bucket/prefix policy;
* signed URL issuance control.

### 13.15 Boundary E — Audit boundary

Audit store phải được xem là trust boundary riêng vì audit là non-reconstructible. Không service nào được sửa hoặc xóa audit record sau khi ghi.

## Database topology và credential isolation

### 13.16 Database strategy

Khuyến nghị:

* một PostgreSQL cluster chung ở giai đoạn đầu;
* tách schema theo ownership context;
* tách DB user theo service;
* write permission chỉ cấp cho schema mình sở hữu.

Ví dụ schema:

* `workspace_core`
* `orchestrator_core`
* `agent_runtime`
* `execution_core`
* `artifact_core`
* `audit_core`
* `policy_core`

### 13.17 DB credential rules

* Orchestrator service account: write chỉ vào `orchestrator_core`;
* Agent Runtime: write chỉ vào `agent_runtime`;
* Artifact Service: write chỉ vào `artifact_core`;
* API Gateway: không có write trực tiếp vào domain schemas;
* sandbox sidecars: không có DB write credentials;
* debug tools / migration tools không được dùng app credentials.

### 13.18 Hard requirement từ gate review

* PP1: không service nào ngoài Orchestrator domain service được direct update `Task/Run/Step.status`;
* PP10: Artifact schema/bảng phải có credential isolation thật, không phải quy ước miệng;
* PP3: Agent Engine phải có persistent store và recovery path của riêng nó.

## Event bus, event store và outbox topology

### 13.19 Event system components

Topology chuẩn gồm ba lớp:

1. service local outbox;
2. message relay / outbox dispatcher;
3. event bus / event store consumer ecosystem.

### 13.20 Outbox invariants trong triển khai

* mọi domain mutation cần event phải ghi DB state + outbox trong cùng transaction;
* service chỉ `ready` khi outbox relay của chính nó healthy;
* sau restart, service không nhận command mới trước khi reconcile outbox backlog tối thiểu đến ngưỡng an toàn.

### 13.21 Event persistence

Ít nhất cần:

* durable event store hoặc durable bus retention;
* replay support cho recovery/rebuild;
* partitioning theo scope đã khóa ở doc 06;
* correlation searchable index.

## Recovery-aware startup topology

### 13.22 Startup order chuẩn

1. database + object storage + event infrastructure + audit storage;
2. auth/policy/secret broker/model gateway;
3. artifact service;
4. orchestrator;
5. agent runtime;
6. execution plane / sandbox manager;
7. API/SSE gateways;
8. web shell.

Lý do:

* control plane không được nhận traffic trước khi storage, policy, audit và event infrastructure sẵn sàng;
* runtime không được nhận work trước khi orchestrator và artifact service available.

### 13.23 Readiness semantics

Một service được xem là ready khi và chỉ khi:

* dependency bắt buộc reachable;
* own schema migrations hoàn tất;
* own outbox relay healthy;
* recovery/reconcile phase hoàn tất;
* policy/audit constraints trong mode hợp lệ.

### 13.24 Recovery order sau crash

#### Orchestrator

* flush/reconcile outbox;
* rebuild `Task/Run/Step` state từ event log + durable store;
* resume watchers;
* chỉ sau đó mới accept command mới.

#### Agent Runtime

* rebuild/reconcile `AgentInvocation` từ durable store và event log;
* xác định mọi invocation có `started` nhưng chưa terminal;
* interrupt hoặc reconcile chúng theo policy trước khi nhận work mới.

#### Execution Plane

* liệt kê sandbox còn active;
* đối chiếu với runtime/orchestrator;
* terminate hoặc rebind theo policy;
* emit required events còn thiếu nếu có repair workflow chính thức.

### 13.25 Dual-crash requirement

Nếu Orchestrator và Agent Runtime cùng crash, Agent Runtime không được assume không có in-flight invocation. Nó phải reconcile từ event log trước. Đây là hard requirement bám gate review PP3.

## Sandbox topology

### 13.26 Sandbox provisioning backend

Giai đoạn đầu có thể dùng:

* local Docker runtime;
* Kubernetes jobs/pods;
* remote execution runners.

Nhưng abstraction phải giữ chung các trường:

* sandbox id;
* sandbox attempt index;
* owning agent invocation id;
* policy snapshot hash;
* network profile;
* filesystem mounts;
* secret bindings;
* active flag.

### 13.27 Sandbox 1-N với AgentInvocation

Một AgentInvocation có thể có nhiều Sandbox records theo các attempt khác nhau, nhưng chỉ một active sandbox tại một thời điểm. Topology và schema phải hỗ trợ `sandbox_attempt_index`. Đây là clarify bắt buộc từ gate review.

### 13.28 Filesystem mounts

Tách rõ:

* workspace mount;
* uploads mount;
* outputs mount;
* temp mount;
* secrets mount.

`/secrets` phải unmount trước khi emit `sandbox.terminated`.

## Object storage topology

### 13.29 Bucket/prefix strategy

Tách ít nhất theo nhóm:

* uploads;
* repo snapshots;
* generated artifacts;
* logs/attachments nếu cần;
* quarantined/tainted artifacts nếu policy yêu cầu.

### 13.30 Signed URL issuance

Chỉ Artifact Service được phát signed URL. URL phải ngắn hạn, scope theo artifact version và chịu check `state × taint × permission` tại thời điểm phát URL.

## Audit topology

### 13.31 Audit durability

Audit store phải có durability SLA cao hơn logs thông thường vì audit là non-reconstructible. Topology phải ưu tiên:

* append-only storage;
* tamper-evident design nếu có thể;
* backup riêng;
* access cực hạn chế.

### 13.32 Audit degraded mode

Nếu audit write cho quyết định bắt buộc thất bại thì system fail closed theo docs 09 và 12. Điều này phải được phản ánh bằng readiness và circuit-breaking chứ không chỉ trong code logic.

## Realtime topology

### 13.33 SSE gateway

SSE gateway có thể scale stateless nếu:

* event source durable;
* hỗ trợ replay bằng `Last-Event-ID`;
* subscription scope enforce theo workspace/task/run.

### 13.34 Realtime degradation

Mất SSE không được làm thay đổi execution semantics. Chỉ ảnh hưởng khả năng quan sát realtime; state truth vẫn ở backend stores và event history.

## Deployment SLOs cấp topology

### 13.35 SLO gợi ý giai đoạn đầu

* API command ack: p95 < 500ms trong điều kiện bình thường;
* SSE propagation: p95 < 2s cho event không nặng;
* Artifact lineage view: p95 < 2s;
* sandbox provisioning: theo class, có budget riêng;
* startup recovery: bounded, observable, có phase logs.

## Topology do-not-break mapping

Topology phải hiện thực và không được phá:

* DNB1 Run không resume;
* DNB2 fail closed;
* DNB3 security violation không auto-recover;
* DNB4 degraded mode không auto-escalate permission;
* DNB5 recovery có event + audit;
* DNB6 artifact creation chỉ qua Artifact Service;
* DNB7 trace_id = correlation_id;
* DNB8 execution trace ≠ provenance trace;
* DNB9 agent không tự nâng quyền;
* DNB10 state transition authority ở Orchestrator;
* DNB11 taint write trước event emit;
* DNB12 model version không là alias khi artifact registration.

## Những điều bị cấm ở tầng topology

1. Cho nhiều service dùng chung DB superuser trong production mode.
2. Đặt Artifact metadata và Orchestrator tables dưới cùng write credential.
3. Cho sandbox gọi model provider trực tiếp.
4. Cho API Gateway ghi trực tiếp `Task/Run/Step` state.
5. Cho debug scripts sửa artifact lineage ngoài Artifact Service.
6. Cho service nhận traffic trước khi outbox/recovery phase hoàn tất.
7. Xem local mode là ngoại lệ để phá security boundary.
8. Để audit storage cùng mức durability với debug logs.

## Kết quả kỳ vọng của doc 13

Sau khi chốt topology, team phải trả lời được rõ ràng:

* service nào chạy ở đâu;
* trust boundary nằm ở đâu;
* DB/schema credential nào thuộc ai;
* startup/recovery order là gì;
* local/cloud/hybrid khác nhau ở placement nào;
* pressure points PP1, PP3, PP10 được topology xử lý bằng hạ tầng ra sao.

---

# Project Log Update

## Tiến độ đã hoàn thành

* Hoàn thành bộ lõi 00–12
* Hoàn thành gate review 00–12
* Hoàn thành doc 13 Deployment Topology

## Clarify / follow-up cần phản ánh ở doc khác

* Doc 04: thêm `sandbox_attempt_index` hoặc cờ equivalent cho quan hệ 1-N từ AgentInvocation đến Sandbox
* Doc 05: khóa rõ `AgentInvocation compensated` → `Step failed`
* Doc 06: `run.timed_out` phải emit tiếp `run.cancelled` trong cùng outbox transaction
* Doc 12: approval timeout watcher không chỉ phụ thuộc scheduler; `run_config` lock + event emit phải đi trong cùng outbox transaction

## Bước tiếp theo đề xuất

* 15 Backend Service Map
* 14 Frontend Application Map
* 16 Repo Structure Conventions
* 17 Implementation Roadmap