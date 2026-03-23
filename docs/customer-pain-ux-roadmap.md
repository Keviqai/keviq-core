# Keviq Core — Customer/Pain Matrix + UI/UX Roadmap theo quý

## 1) Mục tiêu tài liệu

Tài liệu này chuyển phần research trước đó thành một khung ra quyết định sản phẩm theo thứ tự:

**Customer segments → Pain matrix → UX priorities → UI/UX roadmap theo quý → Product epics → Kiến trúc cần xây**

Nguyên tắc:

* Không bắt đầu từ feature list.
* Không bắt đầu từ microservice.
* Bắt đầu từ nhóm khách hàng đau nhất khi cộng tác với agent trong công việc thật.

---

## 2) Giả thuyết định vị Keviq Core

**Keviq Core = AI Workspace OS cho review-heavy knowledge work**

Không phải:

* chatbot builder,
* visual workflow builder trước tiên,
* coding agent platform thuần.

Là:

* nơi team **giao việc cho agent**,
* **quan sát** agent đang làm gì,
* **can thiệp/duyệt** ở bước nhạy cảm,
* nhận **artifact có provenance**,
* và cộng tác trên output đó như một môi trường làm việc thực sự.

---

## 3) Customer Matrix

### Segment A — Knowledge & Research Ops

**Ví dụ**: PM, research / strategy, analyst, content ops, enablement

**Công việc thuê agent làm**: research nhiều nguồn, tổng hợp và tóm tắt, viết brief / memo / report / proposal, chuẩn bị tài liệu ra quyết định

**Pain chính**: không biết có tin output được không, khó kiểm tra agent đã làm các bước nào, chat history dài nhưng khó biến thành deliverable, mất thời gian review lại từ đầu

**Độ phù hợp**: Rất cao

### Segment B — Review-heavy Operations

**Ví dụ**: finance ops, legal ops, procurement, vendor ops, support tier 2, QA / compliance-like flows

**Công việc thuê agent làm**: xử lý ticket/case nhiều bước, chuẩn bị hồ sơ / checklist / draft response, tổng hợp evidence, điền form / tạo tài liệu / đề xuất bước tiếp theo

**Pain chính**: workflow không dừng đúng lúc để xin duyệt, người duyệt thiếu ngữ cảnh, sợ agent hành động vượt quyền, khó audit

**Độ phù hợp**: Cực cao

### Segment C — Delivery / Service Teams

**Ví dụ**: agency, consulting nhỏ, internal service team, marketing ops delivery

**Công việc thuê agent làm**: chuẩn bị deliverable, research cho client/internal stakeholder, tạo draft tài liệu, chuẩn hóa các bước lặp lại

**Pain chính**: nhảy qua nhiều tool, khó reuse workflow, khó giao trách nhiệm khi AI tham gia

**Độ phù hợp**: Cao

### Segment D — Autonomous Coding Teams (thấp ưu tiên ở phase đầu)

---

## 4) Pain Matrix

| Pain cluster | Mô tả | Freq | Sev | WTP | Fit |
|---|---|---|---|---|---|
| P1 — Không thấy agent đang làm gì | Không biết agent ở bước nào, dùng nguồn nào, gọi tool nào | 5 | 5 | 5 | 5 |
| P2 — Không dừng đúng lúc để duyệt | Workflow không có pause/resume mượt; approver thiếu context | 4 | 5 | 5 | 5 |
| P3 — Output không dám dùng | Không có provenance, không biết tự tin bao nhiêu | 5 | 5 | 5 | 5 |
| P4 — Agent khó đoán khi có quyền thật | Sợ agent chạm tích hợp ngoài phạm vi | 4 | 5 | 5 | 4 |
| P5 — Context gãy khi đổi trạng thái | Đổi artifact/task/người duyệt đều làm đứt ngữ cảnh | 4 | 4 | 4 | 4 |
| P6 — Không biết cách làm việc với agent | Không rõ giao việc thế nào, ai chịu trách nhiệm | 5 | 4 | 4 | 5 |

---

## 5) Wedge đầu tiên

**Review-heavy knowledge work cho team 5–50 người**

Use cases đầu tiên:
1. Research brief → human review → final artifact
2. Case prep / ops memo → approval → publish/export
3. Multi-step draft generation → reviewer comments → revised artifact

---

## 6) UX Principles

1. **Clarity over magic** — Agent không được là hộp đen
2. **Delegation over prompting** — Giao việc như giao cho nhân viên
3. **Intervention over passive waiting** — Can thiệp đúng lúc
4. **Artifacts over chat history** — Giá trị ở output, không ở transcript
5. **Trust by evidence** — Provenance, trace, review surface
6. **Team-first, not solo-first** — Môi trường cộng tác

---

## 7) UI/UX Roadmap theo quý

### Q1 — Establish Trust to Delegate

**Mục tiêu**: User dám giao việc đầu tiên cho agent

**Surfaces**: New Task Brief, Workspace Home v1, Onboarding & Guidance

**KPI**: task creation completion rate, time to first successful task, % từ template

### Q2 — Make Agent Work Observable

**Mục tiêu**: Agent từ black box thành observable

**Surfaces**: Run Room, Activity Feed v2, Notifications v1

**KPI**: % run giải thích được, time to detect blocked run

### Q3 — Human-in-the-Loop & Artifact Review

**Mục tiêu**: Duyệt và review output nhanh, có ngữ cảnh

**Surfaces**: Approval Center, Artifact Center v1, Reviewer Mode

**KPI**: approval turnaround time, % artifact dùng được không rework

### Q4 — Team Collaboration & Governance

**Mục tiêu**: Từ tool cá nhân thành workspace nhóm

**Surfaces**: Shared Workspace Views, Admin & Policy Console, Usage & Audit

**KPI**: số task >1 collaborator, policy violation prevented

---

## 8) Product Epic Map

| Group | Epics |
|-------|-------|
| A — Delegation UX | Task Brief Schema, Task/Agent Templates, Output Contract, Risk/Scope Summary |
| B — Runtime Transparency | Run State Machine, Step Timeline, Tool/Source Trace, Live Streaming, Controls |
| C — Approval & Review | Approval Requests, Routing, Decision Context, Artifact Review, Comments/Diff |
| D — Artifact OS | Storage, Versioning, Compare Runs, Provenance/Lineage, Export/Share |
| E — Collaboration | Shared Views, Presence, Mentions, Inbox/Queues, Playbooks |
| F — Governance | Policy Engine, Secrets/Integrations, Usage Metering, Audit, Retention |

---

## 9) Architecture Layers

1. **Experience Layer**: Next.js frontend surfaces
2. **Application Layer**: Task, Run, Approval, Artifact, Notification, Policy, Audit services
3. **Agent Runtime Layer**: Model gateway, tool registry, execution loop, sandbox
4. **Event & Trace Layer**: Append-only event log, SSE/WS, timeline projection, provenance graph
5. **Storage Layer**: PostgreSQL, object storage, Redis, search/index

---

## 10) North Star (12 tháng)

**Một team có thể giao việc cho agent, theo dõi agent, duyệt bước nhạy cảm, và xuất ra artifact đáng tin — tất cả trong cùng một workspace.**

3 chỉ số: Delegated Task Success Rate, Human Review Efficiency, Trustable Output Rate
