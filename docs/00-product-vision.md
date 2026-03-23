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
