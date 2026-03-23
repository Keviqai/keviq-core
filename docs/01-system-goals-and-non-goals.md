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

Repo audit là một use case rất mạnh, nhưng Agent OS không được bị khóa thành "nền tảng audit code". Nó phải giữ được hình dạng platform cho nhiều công việc số.
