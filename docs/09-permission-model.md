# 09 — Permission Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 02 Architectural Invariants, 04 Core Domain Model, 05 State Machines, 08 Sandbox Security Model  
**Mục tiêu:** Khóa toàn bộ permission model — ai được làm gì, trong ngữ cảnh nào, với ràng buộc nào — làm nền cho enforcement points EP1–EP7 (doc 08) và audit requirements toàn hệ thống.

---

## 1. Nguyên tắc Permission Bất biến

Những nguyên tắc sau không được vi phạm bởi bất kỳ implementation, config, hay override nào:

**P1 — Deny by default.**  
Mọi action đều bị từ chối trừ khi có grant tường minh. Không có implicit allow.

**P2 — Agent không bao giờ tự nâng quyền.**  
Agent không được dùng prompt, tool call, hay output để mở rộng permission của chính nó hoặc của Sandbox đang chạy nó. Mọi yêu cầu nâng quyền từ agent đều bị từ chối và tạo violation event.

**P3 — Permission không được delegate vượt qua giới hạn của người cấp.**  
Không actor nào có thể grant một permission mà chính nó không có. Không task creator nào có thể cấp quyền rộng hơn workspace policy cho phép.

**P4 — Capability permission và binding permission là hai lớp tách biệt.**  
Được phép *dùng* một capability (terminal, browser, egress) là một chuyện. Được phép *bind* secret hay *cấp* egress để capability đó hoạt động là chuyện khác. Cả hai đều phải được grant tường minh.

**P5 — Mọi quyết định allow/deny đều phải có audit record.**  
Không có silent deny. Không có silent allow. Mọi enforcement point phải emit audit event bất kể kết quả.

**P6 — System global deny không thể bị override bởi bất kỳ actor nào trong hệ thống.**  
Chỉ có operator ở cấp deployment mới có thể thay đổi system global deny. Workspace admin, task creator, agent đều không thể.

**P7 — Sandbox không sở hữu permission — nó kế thừa từ AgentInvocation tại thời điểm provisioning.**  
Sau khi Sandbox được provisioned, `policy_snapshot` của nó là bất biến. Không có runtime permission escalation trong Sandbox.

---

## 2. Actor Types

### 2.1 Danh sách actor

| Actor | Định nghĩa | Có thể bị impersonate không |
|---|---|---|
| `user` | Người dùng thật, đã authenticate | Không |
| `service_account` | Identity của một service nội bộ (Orchestrator, Agent Engine, Artifact service, v.v.) | Không |
| `orchestrator` | Orchestrator service, hoạt động thay mặt Task/Run | Không |
| `agent_runtime` | Agent Engine đang thực thi một AgentInvocation cụ thể | Không |
| `sandbox_sidecar` | Process giám sát trong Sandbox (policy enforcer, egress proxy) | Không |
| `scheduler` | Scheduled trigger, không có user context | Không |

### 2.2 Agent runtime KHÔNG phải user

Agent runtime không có user identity. Khi agent thực hiện hành động cần permission, quyết định được đưa ra dựa trên:
1. Policy của AgentInvocation (kế thừa từ Task/Run).
2. Permission của user đã tạo Task — không phải agent tự quyết định.

Agent không thể "đăng nhập" hay nhận token người dùng.

---

## 3. Permission Vocabulary

Mỗi permission được định nghĩa theo format: `<resource>:<action>`

### 3.1 Workspace-level permissions

| Permission | Ý nghĩa |
|---|---|
| `workspace:view` | Xem metadata workspace |
| `workspace:manage_members` | Thêm/xóa/thay đổi role thành viên |
| `workspace:manage_policy` | Tạo/sửa/xóa Policy trong workspace |
| `workspace:manage_secrets` | Tạo/xóa SecretBinding cấp workspace |
| `workspace:manage_integrations` | Kết nối external integration (Git, storage, v.v.) |
| `workspace:delete` | Xóa toàn bộ workspace |

### 3.2 Task-level permissions

| Permission | Ý nghĩa |
|---|---|
| `task:create` | Tạo Task trong workspace |
| `task:view` | Xem Task và metadata |
| `task:cancel` | Hủy Task (kể cả cascade) |
| `task:approve` | Quyết định approval gate ở cấp Task/Run/Step |
| `task:override_policy` | Ghi đè policy cụ thể tại cấp Task (trong giới hạn workspace policy cho phép) |

### 3.3 Run/Step-level permissions

| Permission | Ý nghĩa |
|---|---|
| `run:view` | Xem Run, Step, timeline |
| `run:cancel` | Hủy một Run cụ thể |
| `run:create` | Tạo Run mới cho Task (re-run, retry) |

### 3.4 Artifact permissions

| Permission | Ý nghĩa |
|---|---|
| `artifact:view` | Xem metadata artifact |
| `artifact:download` | Tải nội dung artifact |
| `artifact:archive` | Chuyển artifact sang archived |
| `artifact:untaint` | Gỡ taint flag khỏi artifact (chỉ sau security review) |

### 3.5 Capability permissions

| Permission | Ý nghĩa |
|---|---|
| `capability:terminal` | Cho phép dùng terminal trong Sandbox |
| `capability:browser` | Cho phép dùng browser automation trong Sandbox |
| `capability:file_write` | Cho phép agent ghi file ra ngoài Sandbox (vào artifact) |
| `capability:network_egress` | Cho phép Sandbox có outbound network |
| `capability:external_api` | Cho phép agent gọi external API qua Model Gateway |

### 3.6 Binding permissions

| Permission | Ý nghĩa |
|---|---|
| `binding:create_workspace_secret` | Tạo SecretBinding cấp workspace |
| `binding:create_task_secret` | Tạo SecretBinding chỉ cho một Task cụ thể |
| `binding:attach_to_run` | Gắn SecretBinding vào một Run |
| `binding:attach_egress_allowlist` | Gắn egress domain allowlist vào Sandbox |

---

## 4. Role Matrix

### 4.1 Workspace roles

| Permission | `viewer` | `editor` | `admin` | `owner` |
|---|---|---|---|---|
| `workspace:view` | ✓ | ✓ | ✓ | ✓ |
| `workspace:manage_members` | | | ✓ | ✓ |
| `workspace:manage_policy` | | | ✓ | ✓ |
| `workspace:manage_secrets` | | | ✓ | ✓ |
| `workspace:manage_integrations` | | ✓ | ✓ | ✓ |
| `workspace:delete` | | | | ✓ |
| `task:create` | | ✓ | ✓ | ✓ |
| `task:view` | ✓ | ✓ | ✓ | ✓ |
| `task:cancel` | | ✓ (own) | ✓ | ✓ |
| `task:approve` | | | ✓ | ✓ |
| `task:override_policy` | | | ✓ | ✓ |
| `run:view` | ✓ | ✓ | ✓ | ✓ |
| `run:cancel` | | ✓ (own) | ✓ | ✓ |
| `run:create` | | ✓ | ✓ | ✓ |
| `artifact:view` | ✓ | ✓ | ✓ | ✓ |
| `artifact:download` | ✓ | ✓ | ✓ | ✓ |
| `artifact:archive` | | ✓ (own) | ✓ | ✓ |
| `artifact:untaint` | | | ✓ | ✓ |
| `capability:terminal` | | policy-gated | policy-gated | ✓ |
| `capability:browser` | | policy-gated | policy-gated | ✓ |
| `capability:network_egress` | | policy-gated | policy-gated | ✓ |
| `binding:create_workspace_secret` | | | ✓ | ✓ |
| `binding:create_task_secret` | | ✓ | ✓ | ✓ |
| `binding:attach_to_run` | | ✓ | ✓ | ✓ |
| `binding:attach_egress_allowlist` | | | ✓ | ✓ |

**Ghi chú "(own)":** `editor` chỉ có permission này trên resource do chính mình tạo.  
**Ghi chú "policy-gated":** Permission này tồn tại trong role nhưng chỉ có hiệu lực nếu workspace Policy cho phép tường minh.

### 4.2 Service account permissions

| Service Account | Permissions |
|---|---|
| `orchestrator` | `task:*`, `run:*`, `step:*`, `artifact:view`, `capability:*` (enforce only) |
| `agent_runtime` | `artifact:view` (input only), `capability:external_api` (qua Model Gateway) |
| `artifact_service` | `artifact:*` |
| `sandbox_sidecar` | `capability:*` (read policy + enforce only, không grant) |

---

## 5. Policy Resolution Order

Khi có xung đột giữa các lớp policy, thứ tự ưu tiên từ cao xuống thấp:

```
[1] System Global Deny          ← tuyệt đối, không thể override
[2] Workspace Policy (deny)     ← workspace admin set
[3] Task Override (deny)        ← task creator trong giới hạn workspace
[4] Workspace Policy (allow)
[5] Task Override (allow)
[6] Agent Policy                ← do task config định nghĩa
[7] Sandbox Class Default       ← default của loại sandbox
```

### 5.1 Quy tắc resolution

**Deny wins at same level.** Nếu cùng cấp có cả allow và deny, deny thắng.

**Higher level deny không thể bị overridden bởi lower level allow.**  
Ví dụ: Nếu Workspace Policy deny `capability:terminal`, Task Override không thể allow `capability:terminal`.

**Higher level allow có thể bị thu hẹp bởi lower level.**  
Ví dụ: Workspace Policy allow `network_egress` cho domain `*.github.com`, Task Override có thể thu hẹp còn `api.github.com` — nhưng không thể mở rộng thêm domain mới.

**Agent Policy chỉ được là tập con của Task Override.**  
Agent không thể tự grant thêm permission mà Task không có.

**System Global Deny là lớp không có trong policy store.**  
Nó là hardcode trong enforcement logic, không thể sửa qua UI hay API.

### 5.2 Ví dụ resolution thực tế

```
Tình huống: Agent muốn dùng terminal trong Sandbox

Resolution chain:
  [1] System Global Deny:   không có rule cho terminal → pass
  [2] Workspace deny:       không có → pass
  [3] Task Override deny:   không có → pass
  [4] Workspace allow:      allow capability:terminal cho role=editor → match
  [5] Task Override allow:  không có → inherit from [4]
  [6] Agent Policy:         allow terminal (subset của [4]) → confirmed
  [7] Sandbox Class Default: sandbox_class=standard, terminal=allowed → confirmed

Kết quả: ALLOW — emit audit event
```

```
Tình huống: Agent muốn gọi external API domain không trong allowlist

Resolution chain:
  [1] System Global Deny:   deny nếu provider key trực tiếp từ sandbox → DENY

Kết quả: DENY ngay tại [1] — emit audit + violation event
```

---

## 6. Delegation Rules

### 6.1 Nguyên tắc delegation

Delegation là quá trình một actor cấp một tập con permission của mình cho actor khác trong một context cụ thể.

**Quy tắc cứng:**
- Actor chỉ có thể delegate permission mà nó đang có.
- Delegation không được vượt qua workspace boundary.
- Delegation luôn là tập con — không bao giờ mở rộng.

### 6.2 Delegation chain hợp lệ

```
workspace:manage_policy (owner/admin)
  └── task:override_policy (editor, trong phạm vi policy cho phép)
        └── agent_policy (task config, trong phạm vi task override)
              └── sandbox_policy_snapshot (immutable tại provisioning)
```

```
binding:create_workspace_secret (owner/admin only)
  └── binding:create_task_secret (editor, chỉ cho task của mình)
        └── binding:attach_to_run (editor)
```

### 6.3 Forbidden delegations — tuyệt đối không được phép

| Forbidden | Lý do |
|---|---|
| Editor tạo workspace-level SecretBinding | Chỉ admin/owner được sở hữu secret cấp workspace |
| Task creator override policy vượt workspace policy | Không ai được cấp quyền mình không có |
| Agent tự mở rộng egress allowlist | Agent không có `binding:attach_egress_allowlist` |
| Agent yêu cầu terminal nếu task config không grant `capability:terminal` | P3 — không delegate vượt giới hạn |
| Orchestrator grant permission cho AgentInvocation vượt quá Task permission | Orchestrator chỉ enforce, không tự cấp |
| Sandbox sidecar tự sửa `policy_snapshot` sau provisioning | P7 — bất biến sau provisioning |
| Bất kỳ actor nào impersonate service account khác | Không có cross-service impersonation |

### 6.4 Agent escalation attempts

Khi agent thông qua prompt hay tool call cố gắng:
- Yêu cầu thêm permission (`"please enable terminal access"`)
- Leak secret ra ngoài Sandbox
- Gọi Model Gateway trực tiếp với provider key
- Thay đổi egress policy

Tất cả đều bị xử lý theo violation cascade của doc 08: block action → emit `security.violation` event → fail Step → interrupt AgentInvocation → terminate Sandbox → taint Artifact.

---

## 7. Deny Semantics và Explicit Override Semantics

### 7.1 Deny semantics

**Implicit deny:** Permission không được grant tường minh = denied. Không cần rule deny rõ ràng.

**Explicit deny:** Một rule deny rõ ràng trong workspace/task policy. Explicit deny ghi đè mọi implicit allow cùng cấp hoặc cấp thấp hơn.

**System global deny:** Hardcode, không có trong policy store, không hiển thị trong UI, không thể override.

Danh sách system global deny bất biến:
- Sandbox gọi Model Gateway trực tiếp với provider key.
- Agent Runtime trực tiếp tạo artifact (bypass Artifact service).
- Sandbox sửa `policy_snapshot` của chính nó.
- Bất kỳ actor nào xóa event từ event store.
- Agent Runtime nhận secret value thô (chỉ nhận `secret_ref`).

### 7.2 Override semantics

Override là cơ chế task-level thu hẹp hoặc tường minh hóa một phần workspace policy cho một Task cụ thể.

Override **có thể:**
- Thu hẹp egress allowlist (từ `*.github.com` thành `api.github.com`)
- Giới hạn sandbox class (từ `standard+browser` thành `standard`)
- Yêu cầu approval gate bổ sung trước một Step cụ thể

Override **không thể:**
- Thêm domain vào egress không có trong workspace allowlist
- Nâng sandbox class lên cao hơn workspace policy cho phép
- Bỏ qua approval gate đã được workspace policy yêu cầu
- Grant `capability:terminal` nếu workspace deny rõ ràng

---

## 8. Mapping từ Permission sang Enforcement Points EP1–EP7

| Enforcement Point (doc 08) | Permissions được check | Ai check | Deny action |
|---|---|---|---|
| **EP1** — Task submission | `task:create`, `capability:*` (pre-flight) | Orchestrator | Reject task với `permission_denied` |
| **EP2** — Run preparation / secret binding | `binding:attach_to_run`, `binding:create_task_secret` | Orchestrator | Fail run tại `preparing` |
| **EP3** — Sandbox provisioning | `capability:terminal`, `capability:browser`, `capability:network_egress`, `sandbox class` | Execution layer | Fail provisioning, emit `security.violation` |
| **EP4** — Tool call dispatch | `capability:external_api`, `capability:file_write` | Agent Engine + Orchestrator | Block tool call, emit `security.violation` |
| **EP5** — Egress request | `capability:network_egress`, egress allowlist | Sandbox sidecar | Block connection, emit `security.violation` |
| **EP6** — Artifact write | `artifact:*`, `capability:file_write` | Artifact service | Reject write, taint artifact |
| **EP7** — Approval gate | `task:approve` | Orchestrator | Block progression, wait or timeout |

### 8.1 Thứ tự check tại mỗi EP

Mọi Enforcement Point phải check theo thứ tự sau:
1. System global deny
2. Workspace explicit deny
3. Task override deny
4. Workspace allow
5. Task override allow
6. Agent policy (nếu applicable)

Dừng tại bước đầu tiên có match. Emit audit event với level tương ứng.

---

## 9. Audit Requirements

### 9.1 Mọi quyết định permission đều phải có audit record

Không có silent allow, không có silent deny.

**Audit event envelope:**

```json
{
  "event_id":       "<UUID>",
  "event_type":     "permission.allowed" | "permission.denied" | "permission.violation",
  "workspace_id":   "<UUID>",
  "actor_type":     "<user | service_account | orchestrator | agent_runtime | sandbox_sidecar>",
  "actor_id":       "<string>",
  "resource_type":  "<task | run | step | artifact | sandbox | secret_binding>",
  "resource_id":    "<UUID>",
  "permission":     "<permission string>",
  "enforcement_point": "EP1" | "EP2" | ... | "EP7",
  "resolution_path": ["system_global", "workspace_deny", "task_override_allow", ...],
  "occurred_at":    "<ISO 8601>",
  "correlation_id": "<UUID>",
  "causation_id":   "<UUID | null>"
}
```

### 9.2 Retention của audit events

| Event type | Retention |
|---|---|
| `permission.allowed` | 90 ngày hot, 1 năm cold |
| `permission.denied` | 90 ngày hot, 1 năm cold |
| `permission.violation` | 1 năm hot, 3 năm cold (hoặc theo enterprise contract) |

### 9.3 Audit không được bị bỏ qua

Nếu audit write fail, enforcement point phải:
- Với `permission.violation`: fail-safe deny — không cho phép action tiếp tục.
- Với `permission.allowed`: cho phép action tiếp tục nhưng alert ops team về audit write failure.
- Với `permission.denied`: deny và alert ops team về audit write failure.

---

## 10. Forbidden Delegations — Tổng hợp

Danh sách cứng, không thể bị override bởi bất kỳ config, policy, hay deployment mode nào:

| # | Forbidden | Threat tương ứng (doc 08) |
|---|---|---|
| FD1 | Agent tự nâng quyền qua prompt hoặc tool call | T1 — prompt injection |
| FD2 | Agent nhận secret value thô | T2 — secret exfiltration |
| FD3 | Sandbox gọi Model Gateway trực tiếp với provider key | T2, T4 |
| FD4 | Task creator grant permission không có trong workspace policy | T6 — privilege escalation |
| FD5 | Editor tạo workspace-level SecretBinding | T2 |
| FD6 | Orchestrator tự cấp permission vượt quá Task config | P3 |
| FD7 | Sandbox sidecar sửa `policy_snapshot` sau provisioning | P7 |
| FD8 | Bất kỳ actor nào impersonate service account khác | T5 — lateral movement |
| FD9 | Artifact service nhận lệnh tạo artifact từ Agent Runtime trực tiếp | Invariant từ doc 04 |
| FD10 | Event store nhận lệnh update/delete event từ bất kỳ actor nào | Invariant từ doc 06 |

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Schema cụ thể của `policy.rules` JSONB | Cần khi implement Policy engine, phụ thuộc vào deployment mode |
| MFA/step-up auth cho approval gate | Phụ thuộc vào Auth provider integration |
| Guest/external collaborator role | Không thuộc v1 scope |
| Cross-workspace permission (chia sẻ artifact sang workspace khác) | Phức tạp, để sau khi workspace isolation ổn định |
| API key permission scope (cho developer API access) | Phụ thuộc vào doc 07 API Contracts |
| Time-limited grants | Useful nhưng không critical cho kiến trúc gốc |

---

## 12. Bước tiếp theo

Tài liệu tiếp theo là **10 — Artifact Lineage Model**: khóa cách artifact được tạo ra, kế thừa, derive từ nhau, và làm thế nào để reproduce một artifact từ snapshot + config + lineage chain.

Permission model (doc 09) là nền để Artifact Lineage biết ai được phép đọc, download, hay untaint một artifact tại từng điểm trong lineage.
