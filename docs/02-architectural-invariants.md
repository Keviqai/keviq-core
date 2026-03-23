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
