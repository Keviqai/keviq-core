# 08 — Sandbox Security Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 02 Architectural Invariants, 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 07 API Contracts  
**Nguyên tắc lớn nhất:** Sandbox không phải "môi trường chạy tiện lợi" — nó là **security boundary chuẩn** của toàn hệ. Mọi thứ bên trong sandbox phải được coi là untrusted cho đến khi policy cho phép tường minh.

---

## 1. Threat Model

Hệ thống phải chống các nhóm mối đe dọa sau. Đây là danh sách đóng — mọi quyết định thiết kế trong doc này đều phải trace về ít nhất một threat.

### T1 — Agent lạm quyền tool

Agent bị prompt-injected hoặc tự suy luận sai, gọi tool vượt phạm vi được cấp: ghi file ngoài output dir, gọi API ngoài whitelist, spawn subprocess không được phép.

**Mục tiêu phòng thủ:** Capability matrix per sandbox class, tool call enforcement tại execution layer trước khi thực thi.

### T2 — Secret exfiltration

Agent đọc được secret từ env/file rồi exfiltrate qua tool call, network call, artifact content, hoặc terminal output.

**Mục tiêu phòng thủ:** Secret không bao giờ expose dưới dạng plaintext trong log/artifact/terminal output. Redaction bắt buộc. Network egress kiểm soát chặt.

### T3 — Lateral movement giữa workspace

Một sandbox của workspace A đọc/ghi data của workspace B qua shared filesystem, shared network, hoặc shared storage path.

**Mục tiêu phòng thủ:** Isolation namespace per workspace. Storage path không được suy đoán được theo pattern.

### T4 — Network misuse

Agent dùng network egress của sandbox để exfiltrate data, call model ngoài (bypass model gateway), download malicious payload, hay làm C2 channel.

**Mục tiêu phòng thủ:** Deny-by-default egress. Model gateway là đường ra duy nhất cho LLM calls. Allowlist theo domain/port, không theo IP.

### T5 — Artifact poisoning

Agent ghi nội dung độc hại vào artifact (executable, script, malformed data) rồi artifact đó được dùng làm input cho run tiếp theo.

**Mục tiêu phòng thủ:** Artifact được scan khi write. Artifact `failed` không được dùng làm input. Lineage tracking phát hiện poisoning chain.

### T6 — Terminal abuse

User mở terminal session vào sandbox rồi: escalate privilege, copy secrets ra ngoài, modify artifact ngoài output dir, hoặc giữ sandbox sống lâu hơn lifecycle cho phép.

**Mục tiêu phòng thủ:** Terminal là capability bị policy kiểm soát. Audit log đầy đủ. Idle timeout bắt buộc. Terminal không thấy env secrets.

### T7 — Persistence vượt lifecycle sandbox

Sandbox terminate nhưng vẫn còn process con, mounted volume, hoặc network socket đang mở. Data nội tại sandbox rò rỉ sang lần sandbox kế tiếp.

**Mục tiêu phòng thủ:** Hard cleanup khi terminate. Volume unmount + wipe. Process group kill. Network namespace teardown.

---

## 2. Isolation Model

Sandbox phải cô lập theo 6 chiều sau. Thiếu bất kỳ chiều nào là lỗ hổng kiến trúc.

### 2.1 Workspace isolation

- Mỗi sandbox được gắn `workspace_id` không thể thay đổi sau khi provisioned.
- Storage mount, network namespace, và secret binding đều scoped theo `workspace_id`.
- Không có shared resource nào giữa sandbox của hai workspace khác nhau — kể cả image cache hay build cache.

### 2.2 Run isolation

- Mỗi Run có một isolated working directory. Hai Run của cùng Task không được chia sẻ working directory.
- `run_id` được dùng làm namespace prefix cho mọi resource được cấp phát trong Run đó.

### 2.3 AgentInvocation isolation

- Mỗi AgentInvocation có thể có sandbox riêng hoặc dùng chung sandbox của Run tùy sandbox class.
- Nếu nhiều AgentInvocation trong cùng Run dùng chung sandbox: filesystem phải có per-invocation scratch space riêng.

### 2.4 Filesystem mount

| Mount point | Quyền | Nội dung |
|---|---|---|
| `/input` | read-only | RepoSnapshot, input artifact được mount vào |
| `/output` | read-write | Output dir — agent chỉ được ghi vào đây |
| `/tmp` | read-write | Scratch space, bị wipe khi invocation kết thúc |
| `/tools` | read-only | Tool binary/script được hệ thống mount |
| `/secrets` | read-only, scoped | Secret file được inject (xem mục 6) |
| Mọi path khác | không mount | Không access filesystem host |

**Agent không được mount hay unmount bất kỳ path nào.** Mount list là bất biến sau khi sandbox provisioned.

### 2.5 Process namespace

- Sandbox chạy trong isolated PID namespace.
- Agent process không được `fork` subprocess ngoài danh sách tool binary được phép.
- `ptrace`, `strace`, `/proc` của host không được accessible.
- Capability Linux bị drop toàn bộ ngoài tập tối thiểu cần cho tool execution.

### 2.6 Network namespace

- Mỗi sandbox có network namespace riêng.
- Mặc định: **deny all egress và ingress**.
- Egress chỉ được mở theo allowlist từ `network_egress_policy` của sandbox (xem mục 5).
- Ingress không bao giờ được mở từ bên ngoài vào sandbox. Terminal session đi qua sidecar proxy, không phải inbound port.

---

## 3. Sandbox Classes

Bốn sandbox class sau là tập tối thiểu bắt buộc. Deployment mode có thể thêm class nhưng không được bớt.

### 3.1 `read_only_repo`

Dùng cho: code audit, static analysis, documentation generation, Q&A về codebase.

| Capability | Cho phép |
|---|---|
| Đọc `/input` | ✓ |
| Ghi `/output` | ✓ (report, structured data) |
| Ghi `/tmp` | ✓ |
| Chạy subprocess | ✗ |
| Network egress | ✗ |
| Secret injection | ✗ |
| Terminal session | ✗ |
| Ghi `/input` | ✗ |

### 3.2 `code_audit`

Dùng cho: chạy static analysis tool, linter, test runner read-only.

| Capability | Cho phép |
|---|---|
| Đọc `/input` | ✓ |
| Ghi `/output` | ✓ |
| Ghi `/tmp` | ✓ |
| Chạy subprocess (whitelist) | ✓ — chỉ tool trong `/tools` |
| Network egress | ✗ (trừ package registry nếu policy cho phép) |
| Secret injection | ✗ (trừ registry credential nếu policy cho phép) |
| Terminal session | Policy-gated |
| Modify `/input` | ✗ |

### 3.3 `fix_and_patch`

Dùng cho: agent viết code, sửa bug, tạo patch, chạy test với side effects.

| Capability | Cho phép |
|---|---|
| Đọc `/input` | ✓ |
| Ghi `/output` | ✓ |
| Ghi `/tmp` | ✓ |
| Chạy subprocess (whitelist) | ✓ |
| Network egress | Policy-gated (package registry, git provider) |
| Secret injection | Policy-gated |
| Terminal session | Policy-gated |
| Modify `/input` | ✗ — output là patch/diff, không modify source |

### 3.4 `browser_task`

Dùng cho: agent điều khiển browser, web research, form automation.

| Capability | Cho phép |
|---|---|
| Đọc `/input` | ✓ |
| Ghi `/output` | ✓ (screenshot, structured data, page content) |
| Ghi `/tmp` | ✓ |
| Chạy subprocess | ✓ — browser process only |
| Network egress | Policy-gated, domain allowlist bắt buộc |
| Secret injection | Policy-gated (login credential) |
| Terminal session | ✗ — không có terminal trong browser sandbox |
| Clipboard access host | ✗ |
| Download to host filesystem | ✗ — chỉ ghi vào `/output` |

**Browser sandbox có egress policy riêng** — không dùng chung policy của code sandbox (xem mục 5.5).

---

## 4. Filesystem Policy

### 4.1 Input mounting

- `/input` được mount từ `RepoSnapshot.snapshot_storage_ref` hoặc `Artifact.storage_ref` đã `ready`.
- Mount là **read-only hard mount** — kernel-level, không thể override từ trong sandbox.
- Artifact `failed` không được mount làm `/input`. Bất kỳ attempt nào phải bị reject ở provisioning.
- Snapshot execution (tạo `RepoSnapshot` từ git remote) diễn ra trong `read_only_repo` sandbox không có internet egress — chỉ được phép pull từ git provider đã được whitelist trong policy.

### 4.2 Output directory

- `/output` là thư mục duy nhất agent được phép tạo file artifact.
- Sau khi AgentInvocation `completed`, Artifact service scan toàn bộ `/output` và tạo `Artifact` record cho mỗi file.
- File trong `/output` không được executable (bit execute bị strip khi Artifact service đọc).
- Kích thước `/output` bị giới hạn theo `resource_limits.max_output_bytes`.

### 4.3 Scratch space `/tmp`

- `/tmp` bị wipe hoàn toàn khi AgentInvocation kết thúc (dù `completed` hay `interrupted`).
- Nội dung `/tmp` không bao giờ được promote thành Artifact.
- Nội dung `/tmp` không được include trong log.

### 4.4 Xử lý partial artifact khi sandbox terminate giữa chừng

- Nếu sandbox bị terminate trong khi đang ghi `/output`: Artifact service đọc partial content, tạo Artifact record với `artifact_status = failed`, `metadata.partial_data_available = true`.
- Partial artifact không được dùng làm input. Được giữ lại cho debug.
- Checksum của partial artifact để `null`.

---

## 5. Network Egress Policy

### 5.1 Nguyên tắc: Deny by default

Mọi sandbox bắt đầu với **zero egress**. Egress chỉ được mở khi policy tường minh cho phép. Không có "default allow" ở bất kỳ sandbox class nào.

### 5.2 Model Gateway là đường ra duy nhất cho LLM calls

- Agent không được gọi trực tiếp bất kỳ model provider API nào (OpenAI, Anthropic, etc.) từ trong sandbox.
- Mọi model call phải đi qua **Model Gateway** — một service nội bộ với auth, rate limit, cost tracking, và audit.
- Nếu sandbox cần gọi model (nested agent call): phải đi qua Model Gateway endpoint nội bộ, không phải internet.
- Sandbox không bao giờ nhận API key của model provider trực tiếp.

### 5.3 Allowlist structure

Egress allowlist được định nghĩa trong `sandbox.network_egress_policy` theo schema sau:

```json
{
  "rules": [
    {
      "name": "npm-registry",
      "direction": "egress",
      "protocol": "https",
      "domains": ["registry.npmjs.org", "registry.yarnpkg.com"],
      "ports": [443],
      "requires_secret_binding": false
    },
    {
      "name": "github-pull",
      "direction": "egress",
      "protocol": "https",
      "domains": ["github.com", "api.github.com"],
      "ports": [443],
      "requires_secret_binding": true,
      "secret_binding_name": "GITHUB_TOKEN"
    }
  ]
}
```

**Quy tắc:**
- Allowlist theo domain, không theo IP (IP có thể thay đổi, dễ bị bypass).
- Port 22 (SSH) không bao giờ được phép trong sandbox.
- Wildcard domain (`*.example.com`) chỉ được dùng khi không thể enumerate, và phải có comment giải thích lý do.

### 5.4 Egress policy theo sandbox class

| Sandbox class | Default egress | Có thể mở thêm qua policy |
|---|---|---|
| `read_only_repo` | ✗ không có | ✗ không |
| `code_audit` | ✗ không có | Package registry (opt-in) |
| `fix_and_patch` | ✗ không có | Package registry, git provider (opt-in) |
| `browser_task` | ✗ không có | Domain allowlist bắt buộc khi dùng |

### 5.5 Browser sandbox egress

Browser sandbox có nhu cầu egress đặc biệt — agent cần truy cập web. Tuy nhiên:

- Allowlist domain vẫn bắt buộc — không có "browse anywhere".
- Download từ web chỉ được lưu vào `/output` — không về host filesystem.
- Browser process không được make background requests ngoài tab đang active (no background fetch, no WebSocket đến external domain không có trong allowlist).
- Credential nhập vào browser form phải được inject qua secret binding — không được user/agent gõ thủ công trong task config.

---

## 6. Secret Injection Model

### 6.1 Nguyên tắc bất biến

- Secret không bao giờ đi qua frontend.
- Secret không bao giờ xuất hiện trong log, artifact content, terminal output, hay event payload.
- Secret không bao giờ được lưu trong `run_config`, `step.input_snapshot`, hay `agent_invocation.input_messages`.
- Chỉ Sandbox provisioning layer được phép resolve `SecretBinding.secret_ref` thành giá trị thật.

### 6.2 Secret binding scope

| Scope | Ý nghĩa | Ai được phép bind |
|---|---|---|
| `workspace` | Secret dùng cho mọi run trong workspace | Workspace admin |
| `task` | Secret chỉ dùng cho một task cụ thể | Task creator (nếu có quyền) |
| `agent` | Secret chỉ inject cho agent cụ thể | Workspace admin |

### 6.3 Thời hạn secret

Secret binding là **temporary-by-default** trong sandbox:

- Secret được inject khi sandbox `provisioning`.
- Secret bị revoke khi sandbox `terminating` — không giữ lại sau terminate.
- Secret không được copy ra `/output` hay `/tmp` bởi bất kỳ tool nào.

### 6.4 Cơ chế inject

| Phương thức | Dùng cho | Ghi chú |
|---|---|---|
| Environment variable | API key, token ngắn | Chỉ visible trong process env, không expose qua `/proc/environ` ra ngoài namespace |
| File trong `/secrets` | Certificate, config file | Read-only mount, không executable |
| Sidecar token broker | OAuth flow, credential rotation | Token broker là sidecar process trong sandbox namespace, agent gọi local endpoint |

**Không dùng:** command line argument (visible trong `ps`), hardcode trong tool binary.

### 6.5 Redaction rules

Bắt buộc trong toàn bộ hệ thống:

- Mọi log pipeline đều chạy secret redactor trước khi ghi.
- Redactor dùng danh sách pattern từ SecretBinding (không phải giá trị thật) để detect và replace bằng `[REDACTED]`.
- Nếu redactor không chạy được: log phải bị drop, không ghi partial log có thể chứa secret.
- `agent_invocation.output_messages` không được chứa chuỗi khớp với bất kỳ secret pattern nào.

---

## 7. Policy Enforcement Points

Enforcement diễn ra tại 7 điểm sau. Thiếu bất kỳ điểm nào là lỗ hổng.

| Enforcement point | Ai enforce | Khi nào |
|---|---|---|
| **EP1: Trước khi cấp sandbox** | Orchestrator + Policy service | Khi Run chuyển `queued → preparing` |
| **EP2: Trước khi attach tool** | Execution layer | Khi agent dispatch tool call |
| **EP3: Trước khi mở network** | Network proxy | Khi sandbox process mở connection |
| **EP4: Trước khi attach terminal** | Terminal sidecar | Khi API nhận `POST /runs/:id/terminal` |
| **EP5: Trước khi mount secret** | Secret injection service | Trong quá trình provisioning |
| **EP6: Trước khi phát download URL** | Artifact service | Khi API nhận `GET /artifacts/:id/download` |
| **EP7: Khi artifact được write** | Artifact service | Khi `/output` được scan sau invocation |

### EP1 chi tiết — cấp sandbox

Orchestrator phải kiểm tra trước khi tạo sandbox:
- Sandbox class có phù hợp với `task_type` không.
- Workspace có đang trong giới hạn resource không (concurrent sandboxes, total cost).
- Policy hiện tại có cho phép loại task này không.
- Nếu fail: Run chuyển `preparing → failed`, không tạo sandbox.

### EP4 chi tiết — terminal

Terminal không phải "quyền UI" — đây là **sandbox capability được cấp qua policy**:
- Policy phải tường minh có `terminal: allowed` cho sandbox class tương ứng.
- Mỗi terminal session có `session_id` riêng.
- Terminal sidecar proxy toàn bộ input/output — không có direct attach vào container TTY.
- Idle timeout: 5 phút mặc định, configurable trong policy, không thể tắt.

### EP6 chi tiết — download URL

- Signed URL phải chịu policy theo `workspace_id` — URL của workspace A không hoạt động cho workspace B.
- URL không được dự đoán được từ `artifact_id` hay `run_id`. URL phải là signed token opaque.
- TTL của signed URL: 15 phút mặc định.
- Artifact nhạy cảm (`metadata.sensitivity = high`) chỉ cho phép download trong network nội bộ nếu `deployment_mode = local` hoặc `hybrid`.

---

## 8. Terminal Security

Terminal session là capability rủi ro cao nhất — phải có toàn bộ các ràng buộc sau.

### 8.1 Mặc định

- Terminal mặc định là **read-only shell** (không có write capability vào filesystem ngoài `/tmp`).
- Write vào `/output` qua terminal phải được policy tường minh cho phép (`terminal_write_output: allowed`).
- Default shell: `sh` với tập lệnh tối thiểu (no `curl`, no `wget`, no `ssh`, no `git` trừ khi sandbox class cho phép).

### 8.2 Audit log

- Toàn bộ terminal I/O (stdin và stdout) phải được ghi vào audit log.
- Audit log không bị truncate, không bị redact input (chỉ redact output theo secret pattern).
- Audit log là append-only, scoped theo `session_id`.
- Audit log được giữ lại sau khi sandbox terminate (không bị wipe cùng sandbox).

### 8.3 Timeout

- **Idle timeout:** 5 phút không có keystroke → session terminated.
- **Hard timeout:** Bằng với `resource_limits.max_duration_seconds` của sandbox — terminal không thể sống lâu hơn sandbox.
- Timeout không thể bị extend từ trong terminal session.

### 8.4 Secret visibility

- Terminal process không được có secret env variable visible. Secret env được inject vào agent process, không vào terminal process.
- `env` command trong terminal không được list secret binding names.
- `/secrets` mount không accessible từ terminal — terminal chạy trong chroot không có `/secrets`.

### 8.5 File transfer

- Copy từ sandbox ra ngoài: **chỉ qua `/output` → Artifact → signed URL**. Không có SCP, không có clipboard.
- Upload từ ngoài vào sandbox qua terminal: **không được phép**.

---

## 9. Lifecycle và Cleanup Semantics

### 9.1 Khi sandbox `terminating`

Execution layer phải thực hiện theo thứ tự:
1. Gửi SIGTERM đến toàn bộ process trong PID namespace.
2. Chờ graceful shutdown (5 giây).
3. Gửi SIGKILL đến process còn lại.
4. Close tất cả network socket.
5. Unmount tất cả volume (`/input`, `/secrets`, `/tmp`).
6. **Wipe `/tmp`** — shred hoặc secure delete.
7. Teardown network namespace.
8. Teardown PID namespace.
9. Emit `sandbox.terminated`.

**Thứ tự này bất biến.** Không được bỏ bước, không được đảo thứ tự.

### 9.2 Retained sau khi terminate

| Data | Retained | Nơi lưu |
|---|---|---|
| `/output` content | ✓ — đã promote thành Artifact trước khi terminate | Artifact storage |
| Audit log (terminal) | ✓ | Audit log store |
| `sandbox.terminated` event | ✓ | Event store |
| Execution log của tool calls | ✓ — đã ghi vào Step output_snapshot | DB |
| `/tmp` content | ✗ — wiped | — |
| `/secrets` content | ✗ — unmounted trước khi terminate | — |
| Process memory | ✗ | — |

### 9.3 Sandbox reuse

- Sandbox không được reuse giữa các AgentInvocation khác nhau khi `fix_and_patch` hoặc `browser_task`.
- `read_only_repo` và `code_audit` có thể dùng pre-warmed sandbox pool nhưng phải thực hiện **snapshot + restore** để đảm bảo clean state giữa các invocation.

---

## 10. Violation Handling

Khi policy bị vi phạm, hệ thống phải phản ứng theo thứ tự sau:

### 10.1 Luồng xử lý

```
Policy violation detected (EP2, EP3, EP4, EP5, EP6, EP7)
  │
  ├── 1. Block action ngay lập tức
  │         (tool call bị reject, network connection bị drop, terminal attach bị deny)
  │
  ├── 2. Emit security event
  │         sandbox.policy_violation (với violation_type, detail, sandbox_id, workspace_id)
  │
  ├── 3. Fail current Step
  │         step → failed, error_code = POLICY_VIOLATION
  │
  ├── 4. Interrupt AgentInvocation
  │         agent_invocation → interrupted, reason = policy_violation
  │
  ├── 5. Terminate Sandbox
  │         sandbox.terminate_requested → terminating → terminated
  │         termination_reason = policy_violation
  │
  └── 6. Artifact taint (nếu có partial output)
            artifact_status = failed
            metadata.tainted = true
            metadata.taint_reason = policy_violation
```

### 10.2 Artifact taint

- Artifact bị taint không được dùng làm input cho bất kỳ Run nào.
- Artifact bị taint không được download qua signed URL mặc định — phải có explicit override với audit log.
- Taint không được tự động remove — chỉ Workspace admin mới có thể untaint sau review.

### 10.3 Security event

`sandbox.policy_violation` là một fact event đặc biệt với các field bắt buộc:

```json
{
  "violation_type": "<network_egress | tool_unauthorized | secret_access | filesystem_write | terminal_abuse>",
  "enforcement_point": "<EP1 | EP2 | EP3 | EP4 | EP5 | EP6 | EP7>",
  "blocked_action": "<string mô tả hành động bị block>",
  "policy_rule_name": "<tên rule trong policy bị vi phạm>",
  "severity": "<low | medium | high | critical>"
}
```

- `high` và `critical` violation phải trigger alert ngoài audit log (email, webhook, hoặc ops notification tùy deployment mode).
- `critical` violation (lateral movement attempt, secret exfiltration attempt) phải lock workspace tạm thời và yêu cầu admin review.

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Sandbox runtime cụ thể (Docker, gVisor, Firecracker, WASM) | Phụ thuộc vào deployment topology (doc 13) — mỗi mode dùng runtime khác nhau |
| Pre-warmed pool implementation cho `read_only_repo` | Phụ thuộc vào implementation layer |
| Secret rotation trong khi sandbox đang `executing` | Edge case — cần thêm thiết kế |
| Egress policy cho AI tool calls (agent gọi external API) | Phụ thuộc vào tool registry — sẽ khóa cùng tool/execution layer |
| Browser sandbox network inspection (MITM proxy cho audit) | Phức tạp về legal và technical — để lại cho deployment config |
| Snapshot integrity verification khi mount `/input` | Phụ thuộc vào Artifact Lineage Model (doc 10) |

---

## 12. Bước tiếp theo

Tài liệu tiếp theo là **09 — Permission Model**: khóa role/permission matrix, policy resolution order, per-agent permissions, per-tool permissions, và cơ chế delegate permission từ workspace xuống task/run/agent. Doc 09 sẽ điền vào các chỗ "Policy-gated" trong doc này.
