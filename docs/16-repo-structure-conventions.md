# 16 — Repo Structure Conventions

**Trạng thái:** Draft v1.0  
**Phụ thuộc:** 03 Bounded Contexts, 13 Deployment Topology, 14 Frontend Application Map, 15 Backend Service Map, Gate Review 00–12  
**Mục tiêu:** Khóa monorepo layout, ownership per package/service, naming conventions, import boundary rules, architecture tests/lint rules map từ PP1–PP10, và PR checklist để reviewer bắt vi phạm kiến trúc ngay từ ngày đầu.

---

## 1. Repo Strategy

### 1.1 Monorepo

Toàn bộ Agent OS sống trong một monorepo. Lý do:

- Import boundary enforcement dễ hơn khi cross-package — tooling có thể check ngay trong CI.
- Schema, type, event contract được share mà không qua npm publish cycle.
- Architecture tests có thể query toàn bộ codebase.
- Recovery duty, startup ordering, và pressure points dễ verify hơn.

### 1.2 Monorepo tooling

- **Package manager:** pnpm workspaces.
- **Build orchestration:** Turborepo (incremental build, cache).
- **Architecture test:** `dependency-cruiser` cho TypeScript, `pytest-importlinter` hoặc custom AST checker cho Python.

---

## 2. Top-level Layout

```
agent-os/
├── apps/                    ← Deployable applications
│   ├── web/                 ← Frontend shell (Next.js hoặc Vite)
│   ├── api-gateway/         ← SVC-05
│   ├── sse-gateway/         ← SVC-06
│   ├── orchestrator/        ← SVC-01
│   ├── agent-runtime/       ← SVC-02
│   ├── artifact-service/    ← SVC-03
│   ├── execution-service/   ← SVC-04
│   ├── auth-service/        ← SVC-07
│   ├── workspace-service/   ← SVC-08
│   ├── policy-service/      ← SVC-09
│   ├── secret-broker/       ← SVC-10
│   ├── model-gateway/       ← SVC-11
│   ├── audit-service/       ← SVC-12
│   ├── event-store/         ← SVC-13
│   ├── notification-service/← SVC-14
│   └── telemetry-service/   ← SVC-15
│
├── packages/                ← Shared libraries, NOT business logic
│   ├── domain-types/        ← TypeScript types mirror từ API schema
│   ├── event-schema/        ← Event envelope types + event_type constants
│   ├── api-client/          ← Generated API client (OpenAPI → TypeScript)
│   ├── ui-core/             ← Design system, base components
│   ├── server-state/        ← TanStack Query hooks (frontend only)
│   ├── live-state/          ← SSE subscription, reconnect (frontend only)
│   ├── ui-state/            ← Zustand stores for UI state (frontend only)
│   ├── routing/             ← Route definitions, guards
│   ├── permissions/         ← _capabilities type definitions, rendering utils
│   ├── charts/              ← Timeline, DAG, waterfall renderers
│   ├── db-client/           ← DB connection helpers (backend only)
│   ├── outbox/              ← Outbox write + relay helpers (backend only)
│   ├── logger/              ← Structured logging (backend only)
│   └── test-utils/          ← Shared test fixtures và helpers
│
├── infra/                   ← Infrastructure as code
│   ├── docker/              ← Docker Compose configs per topology mode
│   ├── k8s/                 ← Kubernetes manifests (cloud mode)
│   ├── terraform/           ← Cloud infra (nếu cần)
│   └── scripts/             ← Startup, migration, seed scripts
│
├── docs/                    ← Architecture docs 00–17
│   ├── 00-product-vision.md
│   ├── ...
│   └── 17-implementation-roadmap.md
│
├── tools/                   ← Internal tooling
│   ├── arch-test/           ← Architecture test runner
│   ├── codegen/             ← Schema → type generation
│   └── db-migrate/          ← Migration runner
│
├── .github/
│   ├── workflows/           ← CI pipelines
│   └── PULL_REQUEST_TEMPLATE.md
│
├── pnpm-workspace.yaml
├── turbo.json
└── package.json
```

---

## 3. Service Internal Layout

Mỗi app trong `apps/` theo layout chuẩn:

### 3.1 Backend service (Python/FastAPI)

```
apps/orchestrator/
├── src/
│   ├── domain/              ← Domain objects, state machine logic
│   │   ├── task.py          ← Task aggregate, transitions
│   │   ├── run.py           ← Run aggregate, transitions
│   │   └── step.py          ← Step aggregate, transitions
│   ├── application/         ← Use cases, command handlers
│   │   ├── submit_task.py
│   │   ├── cancel_task.py
│   │   └── approve_gate.py
│   ├── infrastructure/      ← DB, outbox, event consumers
│   │   ├── db/
│   │   │   ├── models.py    ← SQLAlchemy models
│   │   │   └── repo.py      ← Repository pattern
│   │   ├── outbox/
│   │   │   └── relay.py
│   │   └── event_consumer/
│   │       └── handlers.py
│   ├── api/                 ← HTTP/gRPC handlers (thin — no business logic)
│   │   └── routes.py
│   └── main.py              ← App entrypoint
├── tests/
│   ├── unit/
│   ├── integration/
│   └── arch/                ← Architecture tests cho service này
├── alembic/                 ← DB migrations (schema: orchestrator_core)
├── Dockerfile
└── pyproject.toml
```

**Quy tắc cứng:**
- `domain/` không được import từ `infrastructure/` hay `api/`.
- `api/` không được import trực tiếp từ `infrastructure/`.
- State transition chỉ được gọi từ `domain/` — không từ `api/` hay `infrastructure/`.

### 3.2 Frontend app

```
apps/web/
├── src/
│   ├── app/                 ← Next.js app router hoặc React Router
│   │   ├── workspaces/
│   │   ├── tasks/
│   │   ├── runs/
│   │   ├── artifacts/
│   │   └── approvals/
│   ├── modules/             ← Feature modules (mirror doc 14 module tree)
│   │   ├── shell/
│   │   ├── task-monitor/
│   │   ├── artifact-explorer/
│   │   ├── lineage-viewer/
│   │   ├── approval-center/
│   │   ├── investigation/
│   │   └── terminal-app/
│   └── lib/                 ← App-level wiring (không phải packages/)
│
├── tests/
│   ├── unit/
│   ├── e2e/
│   └── arch/                ← Import boundary tests cho frontend
└── ...
```

---

## 4. Naming Conventions

### 4.1 Tổng hợp conventions đã khóa ở docs trước

| Loại | Convention | Ví dụ |
|---|---|---|
| Docs | `NN-topic-name.md` | `04-core-domain-model.md` |
| Service (app folder) | `kebab-case` | `orchestrator`, `artifact-service` |
| Python package | `snake_case` | `domain`, `application`, `infrastructure` |
| Python file | `snake_case.py` | `submit_task.py`, `run.py` |
| TypeScript file | `kebab-case.ts` | `task-queries.ts` |
| React component | `PascalCase.tsx` | `TaskTimeline.tsx` |
| DB table | `snake_case`, plural | `tasks`, `runs`, `artifact_lineage_edges` |
| DB schema | `snake_case` | `orchestrator_core`, `artifact_core` |
| Event type | `aggregate.past_tense_verb` | `task.completed`, `artifact.tainted` |
| API path | `/v1/resource/:id/sub-resource` | `/v1/tasks/:taskId/runs` |
| Entity ID | `uuid` (bare) | `"3f2e1a..."` |
| Correlation ID | `uuid` | dùng chung với `trace_id` (DNB7) |
| Environment variable | `SCREAMING_SNAKE_CASE` | `ORCHESTRATOR_DB_URL` |
| Docker service | `kebab-case` | `orchestrator`, `artifact-service` |
| K8s resource | `kebab-case` | `orchestrator-deployment` |

### 4.2 Naming anti-patterns — bị cấm

| Anti-pattern | Tại sao cấm |
|---|---|
| `agentPanel`, `aiChat`, `/debug-view` trong routes | Vi phạm domain language (doc 14 FP9) |
| `SharedService`, `UtilsService`, `CommonHelper` | Signals blurry ownership |
| `*Manager` cho domain service | Naming che giấu trách nhiệm thực |
| `status` không có prefix aggregate | `status` vs `task_status`, `run_status` — phải rõ aggregate |
| `data`, `result`, `response` làm tên field trong event payload | Payload field phải semantic |
| Dùng `latest` làm model version value | DNB12 — phải là version cụ thể |

---

## 5. Import Boundary Rules

Đây là phần được enforce bằng tooling — không phải quy ước miệng.

### 5.1 Backend import boundaries

**Quy tắc trong một service:**

```
domain/     ← không được import từ application/, infrastructure/, api/
application/ ← được import domain/; không được import infrastructure/ trực tiếp
infrastructure/ ← được import domain/; không được import application/
api/         ← được import application/; không được import infrastructure/ trực tiếp
```

**Quy tắc cross-service:**

```
FORBIDDEN: apps/orchestrator → apps/artifact-service (direct import)
ALLOWED:   apps/orchestrator → packages/event-schema (shared types)
ALLOWED:   apps/orchestrator → packages/domain-types (shared types)
FORBIDDEN: apps/api-gateway → apps/orchestrator (phải qua HTTP/event)
```

Mọi cross-service communication phải qua API call hoặc event — không import Python module của service khác.

### 5.2 Frontend import boundaries

**Quy tắc packages:**

```
packages/server-state   ← chỉ được import từ apps/web và packages/permissions
packages/live-state     ← chỉ được import từ apps/web
packages/ui-state       ← chỉ được import từ apps/web
packages/ui-core        ← được import bởi bất kỳ frontend package/app nào
packages/domain-types   ← được import bởi bất kỳ package/app nào
packages/event-schema   ← được import bởi bất kỳ package/app nào
```

**Quy tắc trong frontend app:**

```
modules/task-monitor    ← không được import từ modules/artifact-explorer
modules/lineage-viewer  ← không được import từ modules/task-monitor
```

Modules giao tiếp với nhau qua routing và shared packages — không import trực tiếp.

```
FORBIDDEN: modules/task-monitor/TaskDetail.tsx imports modules/artifact-explorer/ArtifactCard.tsx
ALLOWED:   packages/ui-core/ArtifactBadge.tsx được import bởi cả hai
```

### 5.3 Không được cross backend/frontend boundary trong packages

```
FORBIDDEN: packages/server-state imports packages/outbox
FORBIDDEN: packages/ui-core imports packages/db-client
```

`server-state`, `live-state`, `ui-state`, `ui-core`, `charts`, `permissions` là frontend-only packages.  
`db-client`, `outbox`, `logger` là backend-only packages.  
`domain-types`, `event-schema`, `api-client`, `test-utils` là shared.

---

## 6. Architecture Tests

Architecture tests là code — chạy trong CI, fail build nếu vi phạm. Không phải doc để developer tự đọc và tự nhớ.

### 6.1 Pressure Point → Architecture Test mapping

| Pressure Point | Test | Tool | Fail condition |
|---|---|---|---|
| **PP1** — State transition authority ở Orchestrator | `test_no_status_write_outside_orchestrator` | `pytest-importlinter` + AST scan | Bất kỳ file nào ngoài `apps/orchestrator/src/domain/` có `UPDATE ... SET.*_status` hoặc `.task_status =` |
| **PP2** — Orchestrator outbox flush trước accept | `test_orchestrator_startup_order` | Integration test | Orchestrator readiness probe pass trước khi outbox relay healthy |
| **PP3** — Agent Runtime reconcile sau crash | `test_agent_runtime_no_accept_before_reconcile` | Integration test | `StartInvocation` thành công trước khi reconcile phase hoàn tất |
| **PP4** — Sandbox 1-N per AgentInvocation | `test_sandbox_attempt_index_required` | Schema test | `sandbox_attempts` table thiếu `attempt_index` column |
| **PP5** — Taint write trước event emit | `test_taint_db_before_outbox` | Unit test | `artifact.tainted = true` write xảy ra sau outbox insert trong cùng function |
| **PP6** — `run.timed_out` → `run.cancelled` same transaction | `test_timed_out_emits_cancelled` | Unit test | `run.timed_out` outbox entry không có `run.cancelled` entry trong cùng transaction |
| **PP7** — Tool idempotency contract | `test_tool_idempotent_flag_required` | Schema/registry test | Tool registration thiếu `idempotent` field |
| **PP8** — Approval timeout không chỉ scheduler | `test_approval_timeout_defensive_check` | Unit test | Process event không trigger approval timeout check |
| **PP9** — Model version không là alias | `test_model_version_not_alias` | Unit test | `model_gateway` trả `"latest"` hoặc `"claude-3"` (không có date suffix) |
| **PP10** — Artifact table isolation | `test_artifact_schema_credentials` | Infra test | `orchestrator` DB user có WRITE permission trên `artifact_core` schema |

### 6.2 Import boundary tests (dependency-cruiser)

File `.dependency-cruiser.js` enforce:

```javascript
module.exports = {
  forbidden: [
    // PP1: không service nào ngoài orchestrator write task_status
    {
      name: "no-cross-service-domain-import",
      from: { pathNot: "^apps/orchestrator" },
      to: { path: "^apps/orchestrator/src/domain" },
      severity: "error"
    },
    // Frontend: server-state không import db-client
    {
      name: "no-frontend-pkg-import-backend-pkg",
      from: { path: "^packages/(server-state|live-state|ui-state|ui-core|charts)" },
      to: { path: "^packages/(db-client|outbox|logger)" },
      severity: "error"
    },
    // Frontend: modules không cross-import nhau
    {
      name: "no-module-cross-import",
      from: { path: "^apps/web/src/modules/([^/]+)" },
      to: { path: "^apps/web/src/modules/(?!\\1)" },
      severity: "error"
    },
    // DNB7: không tạo traceId khác correlationId
    {
      name: "no-new-trace-id",
      from: { path: "^apps" },
      to: { path: ".*generateTraceId.*" },
      severity: "error"
    }
  ]
}
```

### 6.3 Python import linter rules

File `import-linter.ini`:

```ini
[importlinter]
root_package = orchestrator

[importlinter:contract:domain-independence]
name = Domain must not import infrastructure
type = layers
layers =
    orchestrator.api
    orchestrator.application
    orchestrator.domain
    orchestrator.infrastructure
# domain không được import application hay infrastructure

[importlinter:contract:no-cross-service]
name = Services must not directly import each other
type = forbidden
source_modules =
    orchestrator
forbidden_modules =
    artifact_service
    agent_runtime
    execution_service
```

### 6.4 Database credential test (Infra test)

```python
def test_orchestrator_cannot_write_artifact_schema():
    """Orchestrator DB user không được có WRITE permission trên artifact_core"""
    with orchestrator_db_connection() as conn:
        result = conn.execute("""
            SELECT has_schema_privilege('orchestrator_user', 'artifact_core', 'USAGE')
        """)
        assert result.scalar() == False, "PP10 violation: orchestrator has artifact_core access"
```

---

## 7. PR Checklist

File `.github/PULL_REQUEST_TEMPLATE.md` — bắt buộc check trước khi merge:

```markdown
## PR Checklist — Architecture Compliance

### Domain & State Machine
- [ ] Không có file nào ngoài `apps/orchestrator/src/domain/` mutate `task_status`, `run_status`, `step_status`
- [ ] Nếu PR thêm state transition: bám đúng doc 05 state machine, có unit test cho transition
- [ ] `run.timed_out` nếu có: emit `run.cancelled` trong cùng outbox transaction (PP6)

### Events & Outbox
- [ ] Mọi domain mutation cần event: viết DB state + outbox trong cùng transaction
- [ ] Event type name: `aggregate.past_tense_verb` (không phải present tense)
- [ ] Không có event `event_id` duplicate khả năng — dùng UUID v7 hoặc v4

### Artifacts & Lineage
- [ ] Artifact creation: chỉ qua `artifact-service` (DNB6) — không direct write
- [ ] Taint: DB write trước outbox write trong cùng transaction (PP5, DNB11)
- [ ] Model version không phải alias khi artifact registration (PP9, DNB12)

### Permissions & Security
- [ ] Không có `if (user.role === ...)` trong frontend component (FP2)
- [ ] Permission check dùng `_capabilities` từ backend response
- [ ] Không có direct WebSocket tới sandbox từ frontend (FP4)

### Frontend State
- [ ] Không có local state machine cho Task/Run/Step (FP1)
- [ ] SSE handler dùng `invalidateQueries()` — không set cache trực tiếp (FP5)
- [ ] Không có lineage compute ở client (FP3)
- [ ] Không có domain entity trong localStorage (FP7)

### Import Boundaries
- [ ] Không có cross-service Python import (chỉ qua HTTP/event)
- [ ] Không có frontend module cross-import trực tiếp (qua packages/ chỉ)
- [ ] `packages/server-state|live-state|ui-state` không import `packages/db-client|outbox`

### Recovery & Startup
- [ ] Nếu PR thay đổi startup behavior: đúng startup order doc 13 mục 13.22
- [ ] Nếu PR thêm service: có recovery duty documented và tested

### Naming
- [ ] Không có route pattern `/agent-panel`, `/debug-view` — phải dùng domain object names
- [ ] DB field cho status: có prefix aggregate (`task_status` không phải `status`)
- [ ] Event payload field: semantic names, không phải `data`, `result`, `response`
```

---

## 8. CI Pipeline Map

```
on: pull_request, push to main

jobs:
  lint:
    - eslint (TypeScript)
    - ruff (Python)
    - dependency-cruiser (import boundaries)
    - import-linter (Python boundaries)

  arch-test:
    - test_no_status_write_outside_orchestrator  (PP1)
    - test_taint_db_before_outbox                (PP5)
    - test_timed_out_emits_cancelled             (PP6)
    - test_tool_idempotent_flag_required         (PP7)
    - test_model_version_not_alias               (PP9)
    - test_approval_timeout_defensive_check      (PP8)

  unit-test:
    - per service

  integration-test:
    - test_orchestrator_startup_order            (PP2)
    - test_agent_runtime_no_accept_before_reconcile (PP3)
    - test_sandbox_attempt_index_required        (PP4)

  infra-test:
    - test_artifact_schema_credentials           (PP10)
    - test_no_superuser_in_service_credentials
    (chạy trong Docker Compose test env)

  build:
    - only runs if all above pass
```

---

## 9. Migration và Schema Ownership

### 9.1 Mỗi service tự quản lý migration của schema mình

```
apps/orchestrator/alembic/    ← orchestrator_core migrations
apps/artifact-service/alembic/ ← artifact_core migrations
apps/auth-service/alembic/    ← identity_core migrations
...
```

Không có global migration runner. Mỗi service chạy `alembic upgrade head` cho schema của mình trong startup sequence.

### 9.2 Cross-schema reference bị cấm ở DB level

```sql
-- FORBIDDEN: foreign key cross-schema
ALTER TABLE orchestrator_core.runs
  ADD CONSTRAINT fk_artifact
  FOREIGN KEY (artifact_id) REFERENCES artifact_core.artifacts(id);

-- ALLOWED: reference bằng UUID value, không foreign key constraint
-- Application-level join qua API call hoặc event
```

Lý do: cross-schema FK tạo implicit ownership coupling — vi phạm service isolation.

### 9.3 Schema versioning

Mỗi schema phải có `schema_version` table:

```sql
CREATE TABLE orchestrator_core.schema_version (
  version TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Service readiness probe check schema version trước khi accept traffic.

---

## 10. Environment Configuration

### 10.1 Per-service env vars

Mỗi service chỉ nhận env vars thuộc về mình:

```
# orchestrator
ORCHESTRATOR_DB_URL=          ← connect tới orchestrator_core schema
ORCHESTRATOR_EVENT_BUS_URL=
ORCHESTRATOR_POLICY_SERVICE_URL=
ORCHESTRATOR_ARTIFACT_SERVICE_URL=
# Không có: ARTIFACT_DB_URL, MODEL_API_KEY, SECRET_VAULT_URL

# artifact-service
ARTIFACT_DB_URL=              ← connect tới artifact_core schema
ARTIFACT_STORAGE_BUCKET=
ARTIFACT_STORAGE_CREDENTIALS= ← riêng biệt
# Không có: ORCHESTRATOR_DB_URL
```

### 10.2 Secret naming convention

```
{SERVICE_NAME}_{RESOURCE_TYPE}_{PURPOSE}
ORCHESTRATOR_DB_URL
ARTIFACT_STORAGE_ACCESS_KEY
MODEL_GATEWAY_ANTHROPIC_KEY
AUTH_JWT_SIGNING_SECRET
```

Provider API key (`*_API_KEY`, `*_ACCESS_KEY`) chỉ được present trong service sở hữu — không leak sang service khác.

---

## 11. Điểm để ngỏ có chủ đích

| Điểm | Lý do chưa khóa |
|---|---|
| Turborepo pipeline config chi tiết | Cần profile thực tế khi có đủ service |
| `dependency-cruiser` full config | Template ở trên là khung — cần mở rộng khi codebase lớn hơn |
| Pre-commit hooks (husky vs lefthook) | Preference, không ảnh hưởng kiến trúc |
| Changesets / versioning strategy cho packages | Cần khi packages bắt đầu được consume bởi external |
| Test coverage thresholds | Cần baseline từ codebase thực tế |
| Branch strategy (trunk-based vs gitflow) | Phụ thuộc team size và release cadence |

---

## 12. Bước tiếp theo

Tài liệu cuối cùng là **17 — Implementation Roadmap**: chia Phase A/B/C theo architecture đã khóa, vertical slices, milestone criteria, và entry conditions cho từng phase — đảm bảo team bắt đầu code đúng thứ tự và không bị trôi khỏi architecture.
