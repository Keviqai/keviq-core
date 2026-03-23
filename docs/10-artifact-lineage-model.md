# 10 — Artifact Lineage Model

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 04 Core Domain Model, 05 State Machines, 06 Event Contracts, 08 Sandbox Security Model, 09 Permission Model  
**Mục tiêu:** Khóa cách artifact được sinh ra, kế thừa, derive, và reproduce — bao gồm root types, lineage edges, reproducibility tuple, taint propagation, access rules theo state/taint, và archive semantics.

---

## 1. Nguyên tắc Lineage Bất biến

**L1 — Mọi artifact đều có provenance.**  
Không có artifact "từ trên trời rơi xuống". Mọi artifact khi được tạo phải có lineage root và provenance record tường minh. Artifact không có provenance là artifact không hợp lệ và không được dùng làm input.

**L2 — Lineage là append-only.**  
Một khi lineage edge được ghi, không được sửa hay xóa. Nếu có sai sót, ghi correction record — không sửa edge cũ.

**L3 — Taint lan theo lineage, không lan ngược.**  
Artifact cha bị taint → artifact con có thể taint. Artifact con bị taint không taint ngược lên cha.

**L4 — Artifact taint không được dùng làm input.**  
Dù role là gì, artifact có `tainted = true` không được gắn vào bất kỳ Run/Step nào cho đến khi được untaint tường minh bởi actor có `artifact:untaint`.

**L5 — Reproducibility là nghĩa vụ, không phải tính năng.**  
Mọi artifact `generated` phải có đủ thông tin để reproduce lại từ đầu: input snapshot, config, tool/model provenance, và lineage chain. Nếu không đủ thông tin này, artifact không được chuyển sang `ready`.

**L6 — `artifact_service` là nơi duy nhất được phép tạo và ghi artifact.**  
Agent Runtime, Orchestrator, và Sandbox không được trực tiếp ghi vào storage. Mọi artifact creation đi qua Artifact service. (Bám vào FD9 từ doc 09.)

---

## 2. Artifact Root Types

Root type xác định nguồn gốc ban đầu của artifact — điểm khởi đầu của mọi lineage chain.

### 2.1 `upload`

Artifact do người dùng upload trực tiếp vào workspace. Không có parent artifact.

**Provenance fields bắt buộc:**

| Field | Nội dung |
|---|---|
| `root_type` | `upload` |
| `uploaded_by_id` | UUID → User |
| `uploaded_at` | timestamp |
| `original_filename` | string |
| `checksum` | SHA-256 của file gốc |
| `workspace_id` | UUID |

**Không có Run/Step context** — upload xảy ra ngoài task execution flow.

### 2.2 `repo_snapshot`

Artifact là ảnh chụp của một Git repository tại một commit cụ thể. Thường là input đầu vào cho coding task.

**Provenance fields bắt buộc:**

| Field | Nội dung |
|---|---|
| `root_type` | `repo_snapshot` |
| `source_url` | URL repo gốc |
| `commit_sha` | SHA đầy đủ |
| `branch` | tên branch (nullable) |
| `snapshot_tool` | tool dùng để snapshot (tên + version) |
| `snapshotted_by_id` | UUID → User hoặc `system` |
| `snapshotted_at` | timestamp |

### 2.3 `generated`

Artifact được tạo ra bởi một AgentInvocation hoặc Tool trong một Run. Đây là artifact phổ biến nhất và có yêu cầu provenance nghiêm nhất.

**Provenance fields bắt buộc:**

| Field | Nội dung |
|---|---|
| `root_type` | `generated` |
| `run_id` | UUID → Run |
| `step_id` | UUID → Step (nullable nếu là run-level artifact) |
| `agent_invocation_id` | UUID → AgentInvocation (nullable nếu từ tool trực tiếp) |
| `tool_name` | tên tool tạo artifact (nullable nếu từ agent output) |
| `model_id` | model được dùng (nếu từ agent) |
| `model_version` | version đầy đủ của model |
| `run_config_hash` | SHA-256 của `run.run_config` tại thời điểm chạy |
| `input_artifact_ids` | danh sách artifact_id dùng làm input |

### 2.4 `imported`

Artifact được kéo vào từ external source (API, external storage, webhook) không phải do user upload trực tiếp và không phải từ repo.

**Provenance fields bắt buộc:**

| Field | Nội dung |
|---|---|
| `root_type` | `imported` |
| `source_url` | URL nguồn gốc |
| `import_tool` | tool/integration được dùng |
| `imported_by_id` | UUID → User hoặc service account |
| `imported_at` | timestamp |
| `checksum` | SHA-256 của nội dung nhập về |

---

## 3. Lineage Edges

Lineage edge thể hiện quan hệ có hướng giữa artifact cha và artifact con. Mọi edge đều phải được ghi khi artifact con được tạo.

### 3.1 Các loại edge

| Edge type | Ý nghĩa | Số cha |
|---|---|---|
| `derived_from` | Artifact con được tạo ra trực tiếp từ nội dung của cha, không qua transform rõ ràng. Ví dụ: agent đọc file A và tạo file B. | 1 |
| `transformed_from` | Artifact con là kết quả của một transformation xác định và có thể mô tả được. Ví dụ: convert PDF → Markdown, compile code → binary. | 1 |
| `aggregated_from` | Artifact con tổng hợp từ nhiều artifact cha. Ví dụ: report tổng hợp từ nhiều analysis artifact. | ≥ 2 |
| `promoted_from` | Artifact con là bản được chọn/xác nhận từ nhiều artifact candidate cùng loại. Ví dụ: chọn best-of-3 draft. | ≥ 1 |

### 3.2 Lineage edge record

```json
{
  "edge_id":          "<UUID>",
  "child_artifact_id": "<UUID>",
  "parent_artifact_id": "<UUID>",
  "edge_type":        "derived_from | transformed_from | aggregated_from | promoted_from",
  "run_id":           "<UUID>",
  "step_id":          "<UUID | null>",
  "created_at":       "<ISO 8601>",
  "transform_detail": { }
}
```

`transform_detail` là optional JSON mô tả transformation: tên transform, params, tool version — dùng để reproduce.

### 3.3 Lineage là DAG, không phải cây

Một artifact con có thể có nhiều cha (qua `aggregated_from`). Lineage graph là **Directed Acyclic Graph**. Cycle là bất hợp lệ và phải bị reject khi Artifact service ghi edge.

---

## 4. Reproducibility Tuple

Mọi artifact `generated` phải có đủ thông tin trong **reproducibility tuple** sau để có thể chạy lại và nhận artifact với nội dung giống hệt (deterministic) hoặc tương đương (semantic-equivalent nếu model non-deterministic).

```
Reproducibility Tuple = (
  input_snapshot,
  run_config,
  tool_provenance,
  model_provenance,
  lineage_chain
)
```

### 4.1 `input_snapshot`

Toàn bộ artifact dùng làm input, được tham chiếu bằng `artifact_id` + `checksum`. Không phải URL, không phải tên file — phải là immutable reference.

### 4.2 `run_config`

Snapshot của `run.run_config` tại thời điểm Run rời `queued`. Được lưu dưới dạng `run_config_hash` (SHA-256) trong provenance. Config đầy đủ được lưu trong Run record và không thay đổi.

### 4.3 `tool_provenance`

Với mỗi tool được dùng trong Step sinh ra artifact này:
- `tool_name`
- `tool_version`
- `tool_config_hash`

### 4.4 `model_provenance`

Với mỗi model call trong AgentInvocation sinh ra artifact này:
- `model_id` (VD: `claude-sonnet-4-20250514`)
- `model_version` đầy đủ (không được dùng alias như `latest`)
- `temperature`, `max_tokens`, và các sampling params
- `system_prompt_hash` (SHA-256 của system prompt)

**Lý do không dùng alias:** `latest` thay đổi theo thời gian, làm reproducibility tuple không còn valid.

### 4.5 `lineage_chain`

Danh sách có thứ tự của tất cả edge từ root đến artifact hiện tại. Dùng để trace và verify toàn bộ chuỗi derivation.

### 4.6 Validate reproducibility trước khi `artifact.ready`

Artifact service phải verify đủ 5 thành phần của tuple trước khi chuyển artifact sang `ready`. Nếu thiếu bất kỳ thành phần nào, artifact chuyển sang `failed` với `failure_reason: incomplete_provenance`.

---

## 5. Taint Propagation Rules

### 5.1 Nguồn gốc taint

Artifact bị taint khi:

| Nguồn | Trigger |
|---|---|
| **Security violation** | Sandbox vi phạm policy khi tạo ra artifact (từ doc 08 violation cascade) |
| **Untrusted input** | Artifact được derived_from hoặc transformed_from một artifact đã tainted |
| **Manual taint** | Admin/owner tường minh đánh dấu artifact là tainted sau security review |
| **Model anomaly** | Model Gateway phát hiện output có dấu hiệu prompt injection hoặc malicious content |

### 5.2 Taint propagation theo edge type

| Edge type | Propagation rule |
|---|---|
| `derived_from` | Nếu cha tainted → con **bị taint tự động** |
| `transformed_from` | Nếu cha tainted → con **bị taint tự động** |
| `aggregated_from` | Nếu **bất kỳ** cha nào tainted → con **bị taint tự động** |
| `promoted_from` | Nếu artifact được chọn tainted → con tainted. Nếu chỉ candidate bị reject tainted → con **không bị taint** |

### 5.3 Taint là property của artifact, không phải edge

Taint được lưu trên artifact (`tainted: bool`, `taint_reason: string`, `tainted_at: timestamp`), không phải trên edge. Điều này giúp query "artifact này có bị taint không" là O(1), không phải graph traversal.

Tuy nhiên, **taint propagation check phải traverse lineage graph** khi artifact mới được tạo — Artifact service phải check toàn bộ cha trong lineage trước khi finalize.

### 5.4 Taint không tự xóa

Taint chỉ được xóa khi:
1. Actor có `artifact:untaint` tường minh gọi untaint API.
2. Sau khi untaint, `untaint_review_id` và `untainted_by_id` phải được ghi vào artifact record.
3. Artifact con của artifact bị taint **không tự động untaint** khi cha được untaint — mỗi artifact con phải được review và untaint riêng.

### 5.5 Taint propagation event

Khi taint propagation xảy ra tự động, Artifact service phải emit:

```json
{
  "event_type": "artifact.tainted",
  "payload": {
    "artifact_id":           "<UUID>",
    "taint_reason":          "propagated_from_parent",
    "parent_artifact_id":    "<UUID>",
    "propagation_edge_type": "derived_from | transformed_from | aggregated_from"
  }
}
```

---

## 6. Access Rules theo State, Taint, và Ownership

Role matrix trong doc 09 là điều kiện cần — không phải đủ. Quyền download và access artifact còn phụ thuộc vào state và taint status.

### 6.1 Access matrix đầy đủ

| Artifact state | Tainted | `artifact:view` | `artifact:download` | `artifact:untaint` |
|---|---|---|---|---|
| `pending` | — | ✓ (owner/admin/editor) | ✗ | ✗ |
| `writing` | — | ✓ (owner/admin/editor) | ✗ | ✗ |
| `ready` | false | ✓ (viewer+) | ✓ (viewer+) | N/A |
| `ready` | true | ✓ (viewer+) | ✗ | ✓ (admin/owner only) |
| `failed` | — | ✓ (editor+) | ✓ (editor+, partial, debug only) | ✗ |
| `superseded` | false | ✓ (editor+) | ✓ (editor+) | N/A |
| `superseded` | true | ✓ (editor+) | ✗ | ✓ (admin/owner only) |
| `archived` | false | ✓ (editor+) | ✓ (editor+, cold latency) | N/A |
| `archived` | true | ✓ (editor+) | ✗ | ✓ (admin/owner only) |

**Quy tắc bổ sung:**
- Artifact `failed` với `partial_data_available: true` chỉ được download bởi `editor+` và phải có flag `debug_only: true` trong response header.
- Artifact tainted **không bao giờ được dùng làm input** cho Run/Step, bất kể role.
- Artifact `archived` có thể download nhưng có SLA khác (cold storage retrieval latency phụ thuộc deployment mode).

### 6.2 Signed URL policy

Mọi artifact download phải qua **signed URL** do Artifact service phát ra. Không có direct storage URL nào được expose ra ngoài Artifact service.

**Signed URL properties:**

| Property | Giá trị |
|---|---|
| TTL | 15 phút (mặc định) / 1 giờ (tối đa, cần explicit request) |
| Scope | Gắn với `artifact_id` + `user_id` + `workspace_id` |
| Single-use | Có thể config per-workspace (mặc định: multi-use trong TTL) |
| Revocable | Admin có thể revoke signed URL đang active |
| Taint check | Artifact service check taint status **tại thời điểm phát URL**, không phải tại thời điểm request URL |

**Taint check tại phát URL:** Nếu artifact bị taint sau khi URL được phát nhưng trước khi URL được dùng, Artifact service phải reject request tại storage layer (không phải chờ TTL expire).

---

## 7. Archive vs Delete Semantics

### 7.1 Không có delete

Artifact không bị xóa. Chỉ được archived. Đây là invariant từ doc 04 và doc 05.

**Lý do:** Xóa artifact làm đứt lineage chain của các artifact con. Kể cả artifact `failed` cũng phải giữ để debug lineage.

### 7.2 Archive semantics

Archive là chuyển artifact sang cold storage với metadata vẫn còn queryable ở hot tier.

| Sau khi archive | Còn làm được | Không còn làm được |
|---|---|---|
| Xem metadata | ✓ | |
| Query lineage | ✓ | |
| Download | ✓ (với cold latency) | |
| Dùng làm input cho Run mới | ✓ (nếu không tainted) | |
| Chuyển ngược về `ready` | | ✗ |
| Untaint | ✓ (admin/owner) | |

### 7.3 Archive trigger

| Trigger | Điều kiện |
|---|---|
| Scheduled archival | Artifact `ready`/`superseded`/`failed` sau N ngày (config per workspace) |
| Manual archival | `editor+` gọi archive API |
| Run archival cascade | Khi Run được archived, tất cả artifact gắn với Run đó được archive |
| Workspace retention policy | Workspace policy định nghĩa retention window cho từng `artifact_type` |

### 7.4 Archive không được xảy ra với artifact đang là input của Run active

Nếu artifact đang được tham chiếu bởi một Run có `run_status` trong `[queued, preparing, running, waiting_approval, completing]`, archive bị block cho đến khi Run kết thúc.

---

## 8. Lineage Query API (surface area tối thiểu)

Doc này không khóa implementation, nhưng khóa surface area tối thiểu mà Artifact service phải expose:

| Query | Ý nghĩa |
|---|---|
| `GET /artifacts/{id}/lineage/ancestors` | Toàn bộ artifact tổ tiên (BFS/DFS lên root) |
| `GET /artifacts/{id}/lineage/descendants` | Toàn bộ artifact con cháu |
| `GET /artifacts/{id}/lineage/graph` | Full DAG subgraph quanh artifact này |
| `GET /artifacts/{id}/provenance` | Reproducibility tuple đầy đủ |
| `GET /artifacts/{id}/taint-status` | Taint status + taint propagation path |
| `POST /artifacts/{id}/untaint` | Untaint (yêu cầu `artifact:untaint`) |

---

## 9. Mapping sang Event Contracts (doc 06)

Mọi thay đổi taint và lineage phải có event tương ứng:

| Sự kiện lineage | Event type | Key payload fields |
|---|---|---|
| Lineage edge được ghi | `artifact.lineage_recorded` | `child_artifact_id`, `parent_artifact_id`, `edge_type` |
| Artifact bị taint tự động | `artifact.tainted` | `artifact_id`, `taint_reason`, `parent_artifact_id` |
| Artifact bị taint thủ công | `artifact.tainted` | `artifact_id`, `taint_reason: manual`, `tainted_by_id` |
| Artifact được untaint | `artifact.untainted` | `artifact_id`, `untainted_by_id`, `untaint_review_id` |
| Signed URL được phát | `artifact.url_issued` | `artifact_id`, `issued_to_user_id`, `expires_at` |
| Signed URL bị revoke | `artifact.url_revoked` | `artifact_id`, `revoked_by_id` |

---

## 10. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Retention window cụ thể theo `artifact_type` | Phụ thuộc deployment topology (doc 13) và workspace contract |
| Cold storage implementation (S3, GCS, local volume) | Phụ thuộc deployment mode — local vs cloud vs hybrid |
| Semantic equivalence definition cho non-deterministic reproduction | Cần khi implement reproducibility verification, phức tạp theo model type |
| Cross-workspace artifact sharing | Ngoài v1 scope |
| Artifact versioning schema (major.minor) | Đủ để để ngỏ — `superseded` edge đã xử lý use case chính |
| DRM / export control cho workspace enterprise | Phụ thuộc enterprise contract, không thuộc core architecture |

---

## 11. Bước tiếp theo

Tài liệu tiếp theo là **11 — Observability Model**: khóa cách hệ thống được quan sát — traces, metrics, logs, health checks, và alerting policy — làm nền để team vận hành có thể monitor, debug, và recover mà không cần đọc source code.

Lineage model (doc 10) cung cấp artifact ancestry path cho observability: khi một artifact `failed` hoặc bị taint, observability layer cần biết toàn bộ lineage để surface đúng context cho người điều tra.
