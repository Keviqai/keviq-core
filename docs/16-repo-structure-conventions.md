# 16 — Repo Structure Conventions

**Status:** Draft v1.0
**Dependencies:** 03 Bounded Contexts, 13 Deployment Topology, 14 Frontend Application Map, 15 Backend Service Map, Gate Review 00–12
**Objective:** Lock the monorepo layout, ownership per package/service, naming conventions, import boundary rules, architecture tests/lint rules mapping from PP1–PP10, and PR checklist so that reviewers catch architecture violations from day one.

---

## 1. Repo Strategy

### 1.1 Monorepo

The entire Agent OS lives in a single monorepo. Rationale:

- Import boundary enforcement is easier with cross-package access — tooling can check directly in CI.
- Schema, type, and event contract sharing works without npm publish cycles.
- Architecture tests can query the entire codebase.
- Recovery duty, startup ordering, and pressure points are easier to verify.

### 1.2 Monorepo tooling

- **Package manager:** pnpm workspaces.
- **Build orchestration:** Turborepo (incremental build, cache).
- **Architecture test:** `dependency-cruiser` for TypeScript, `pytest-importlinter` or custom AST checker for Python.

---

## 2. Top-level Layout

```
agent-os/
├── apps/                    ← Deployable applications
│   ├── web/                 ← Frontend shell (Next.js or Vite)
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
│   ├── domain-types/        ← TypeScript types mirrored from API schema
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
│   └── test-utils/          ← Shared test fixtures and helpers
│
├── infra/                   ← Infrastructure as code
│   ├── docker/              ← Docker Compose configs per topology mode
│   ├── k8s/                 ← Kubernetes manifests (cloud mode)
│   ├── terraform/           ← Cloud infra (if needed)
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

Each app in `apps/` follows a standard layout:

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
│   └── arch/                ← Architecture tests for this service
├── alembic/                 ← DB migrations (schema: orchestrator_core)
├── Dockerfile
└── pyproject.toml
```

**Hard rules:**
- `domain/` must not import from `infrastructure/` or `api/`.
- `api/` must not import directly from `infrastructure/`.
- State transitions may only be invoked from `domain/` — not from `api/` or `infrastructure/`.

### 3.2 Frontend app

```
apps/web/
├── src/
│   ├── app/                 ← Next.js app router or React Router
│   │   ├── workspaces/
│   │   ├── tasks/
│   │   ├── runs/
│   │   ├── artifacts/
│   │   └── approvals/
│   ├── modules/             ← Feature modules (mirrors doc 14 module tree)
│   │   ├── shell/
│   │   ├── task-monitor/
│   │   ├── artifact-explorer/
│   │   ├── lineage-viewer/
│   │   ├── approval-center/
│   │   ├── investigation/
│   │   └── terminal-app/
│   └── lib/                 ← App-level wiring (not packages/)
│
├── tests/
│   ├── unit/
│   ├── e2e/
│   └── arch/                ← Import boundary tests for frontend
└── ...
```

---

## 4. Naming Conventions

### 4.1 Summary of conventions locked in previous docs

| Type | Convention | Example |
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
| Correlation ID | `uuid` | shared with `trace_id` (DNB7) |
| Environment variable | `SCREAMING_SNAKE_CASE` | `ORCHESTRATOR_DB_URL` |
| Docker service | `kebab-case` | `orchestrator`, `artifact-service` |
| K8s resource | `kebab-case` | `orchestrator-deployment` |

### 4.2 Naming anti-patterns — prohibited

| Anti-pattern | Why prohibited |
|---|---|
| `agentPanel`, `aiChat`, `/debug-view` in routes | Violates domain language (doc 14 FP9) |
| `SharedService`, `UtilsService`, `CommonHelper` | Signals blurry ownership |
| `*Manager` for domain service | Naming obscures actual responsibility |
| `status` without aggregate prefix | `status` vs `task_status`, `run_status` — aggregate must be clear |
| `data`, `result`, `response` as field names in event payload | Payload fields must be semantic |
| Using `latest` as model version value | DNB12 — must be a specific version |

---

## 5. Import Boundary Rules

This section is enforced by tooling — not by verbal convention.

### 5.1 Backend import boundaries

**Rules within a service:**

```
domain/     ← must not import from application/, infrastructure/, api/
application/ ← may import domain/; must not import infrastructure/ directly
infrastructure/ ← may import domain/; must not import application/
api/         ← may import application/; must not import infrastructure/ directly
```

**Cross-service rules:**

```
FORBIDDEN: apps/orchestrator → apps/artifact-service (direct import)
ALLOWED:   apps/orchestrator → packages/event-schema (shared types)
ALLOWED:   apps/orchestrator → packages/domain-types (shared types)
FORBIDDEN: apps/api-gateway → apps/orchestrator (must go through HTTP/event)
```

All cross-service communication must go through API calls or events — no importing Python modules from another service.

### 5.2 Frontend import boundaries

**Package rules:**

```
packages/server-state   ← may only be imported from apps/web and packages/permissions
packages/live-state     ← may only be imported from apps/web
packages/ui-state       ← may only be imported from apps/web
packages/ui-core        ← may be imported by any frontend package/app
packages/domain-types   ← may be imported by any package/app
packages/event-schema   ← may be imported by any package/app
```

**Rules within the frontend app:**

```
modules/task-monitor    ← must not import from modules/artifact-explorer
modules/lineage-viewer  ← must not import from modules/task-monitor
```

Modules communicate with each other through routing and shared packages — no direct imports.

```
FORBIDDEN: modules/task-monitor/TaskDetail.tsx imports modules/artifact-explorer/ArtifactCard.tsx
ALLOWED:   packages/ui-core/ArtifactBadge.tsx may be imported by both
```

### 5.3 No crossing the backend/frontend boundary within packages

```
FORBIDDEN: packages/server-state imports packages/outbox
FORBIDDEN: packages/ui-core imports packages/db-client
```

`server-state`, `live-state`, `ui-state`, `ui-core`, `charts`, `permissions` are frontend-only packages.
`db-client`, `outbox`, `logger` are backend-only packages.
`domain-types`, `event-schema`, `api-client`, `test-utils` are shared.

---

## 6. Architecture Tests

Architecture tests are code — they run in CI and fail the build on violation. They are not documentation for developers to read and remember.

### 6.1 Pressure Point → Architecture Test mapping

| Pressure Point | Test | Tool | Fail condition |
|---|---|---|---|
| **PP1** — State transition authority at Orchestrator | `test_no_status_write_outside_orchestrator` | `pytest-importlinter` + AST scan | Any file outside `apps/orchestrator/src/domain/` contains `UPDATE ... SET.*_status` or `.task_status =` |
| **PP2** — Orchestrator outbox flush before accept | `test_orchestrator_startup_order` | Integration test | Orchestrator readiness probe passes before outbox relay is healthy |
| **PP3** — Agent Runtime reconcile after crash | `test_agent_runtime_no_accept_before_reconcile` | Integration test | `StartInvocation` succeeds before reconcile phase completes |
| **PP4** — Sandbox 1-N per AgentInvocation | `test_sandbox_attempt_index_required` | Schema test | `sandbox_attempts` table missing `attempt_index` column |
| **PP5** — Taint write before event emit | `test_taint_db_before_outbox` | Unit test | `artifact.tainted = true` write occurs after outbox insert in the same function |
| **PP6** — `run.timed_out` → `run.cancelled` same transaction | `test_timed_out_emits_cancelled` | Unit test | `run.timed_out` outbox entry has no `run.cancelled` entry in the same transaction |
| **PP7** — Tool idempotency contract | `test_tool_idempotent_flag_required` | Schema/registry test | Tool registration missing `idempotent` field |
| **PP8** — Approval timeout not scheduler-only | `test_approval_timeout_defensive_check` | Unit test | Processing an event does not trigger approval timeout check |
| **PP9** — Model version must not be an alias | `test_model_version_not_alias` | Unit test | `model_gateway` returns `"latest"` or `"claude-3"` (without date suffix) |
| **PP10** — Artifact table isolation | `test_artifact_schema_credentials` | Infra test | `orchestrator` DB user has WRITE permission on `artifact_core` schema |

### 6.2 Import boundary tests (dependency-cruiser)

File `.dependency-cruiser.js` enforces:

```javascript
module.exports = {
  forbidden: [
    // PP1: no service other than orchestrator writes task_status
    {
      name: "no-cross-service-domain-import",
      from: { pathNot: "^apps/orchestrator" },
      to: { path: "^apps/orchestrator/src/domain" },
      severity: "error"
    },
    // Frontend: server-state must not import db-client
    {
      name: "no-frontend-pkg-import-backend-pkg",
      from: { path: "^packages/(server-state|live-state|ui-state|ui-core|charts)" },
      to: { path: "^packages/(db-client|outbox|logger)" },
      severity: "error"
    },
    // Frontend: modules must not cross-import each other
    {
      name: "no-module-cross-import",
      from: { path: "^apps/web/src/modules/([^/]+)" },
      to: { path: "^apps/web/src/modules/(?!\\1)" },
      severity: "error"
    },
    // DNB7: do not create traceId different from correlationId
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
# domain must not import application or infrastructure

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
    """Orchestrator DB user must not have WRITE permission on artifact_core"""
    with orchestrator_db_connection() as conn:
        result = conn.execute("""
            SELECT has_schema_privilege('orchestrator_user', 'artifact_core', 'USAGE')
        """)
        assert result.scalar() == False, "PP10 violation: orchestrator has artifact_core access"
```

---

## 7. PR Checklist

File `.github/PULL_REQUEST_TEMPLATE.md` — mandatory check before merge:

```markdown
## PR Checklist — Architecture Compliance

### Domain & State Machine
- [ ] No file outside `apps/orchestrator/src/domain/` mutates `task_status`, `run_status`, `step_status`
- [ ] If PR adds state transition: follows doc 05 state machine, has unit test for transition
- [ ] `run.timed_out` if present: emits `run.cancelled` in same outbox transaction (PP6)

### Events & Outbox
- [ ] Every domain mutation requiring an event: writes DB state + outbox in same transaction
- [ ] Event type name: `aggregate.past_tense_verb` (not present tense)
- [ ] No duplicate `event_id` possibility — uses UUID v7 or v4

### Artifacts & Lineage
- [ ] Artifact creation: only through `artifact-service` (DNB6) — no direct write
- [ ] Taint: DB write before outbox write in same transaction (PP5, DNB11)
- [ ] Model version is not an alias during artifact registration (PP9, DNB12)

### Permissions & Security
- [ ] No `if (user.role === ...)` in frontend components (FP2)
- [ ] Permission check uses `_capabilities` from backend response
- [ ] No direct WebSocket to sandbox from frontend (FP4)

### Frontend State
- [ ] No local state machine for Task/Run/Step (FP1)
- [ ] SSE handler uses `invalidateQueries()` — does not set cache directly (FP5)
- [ ] No lineage computation on client (FP3)
- [ ] No domain entity in localStorage (FP7)

### Import Boundaries
- [ ] No cross-service Python import (only through HTTP/event)
- [ ] No frontend module cross-import directly (through packages/ only)
- [ ] `packages/server-state|live-state|ui-state` does not import `packages/db-client|outbox`

### Recovery & Startup
- [ ] If PR changes startup behavior: follows startup order doc 13 section 13.22
- [ ] If PR adds service: recovery duty is documented and tested

### Naming
- [ ] No route pattern `/agent-panel`, `/debug-view` — must use domain object names
- [ ] DB field for status: has aggregate prefix (`task_status` not `status`)
- [ ] Event payload fields: semantic names, not `data`, `result`, `response`
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
    (runs in Docker Compose test env)

  build:
    - only runs if all above pass
```

---

## 9. Migrations and Schema Ownership

### 9.1 Each service manages its own schema migrations

```
apps/orchestrator/alembic/    ← orchestrator_core migrations
apps/artifact-service/alembic/ ← artifact_core migrations
apps/auth-service/alembic/    ← identity_core migrations
...
```

There is no global migration runner. Each service runs `alembic upgrade head` for its own schema during the startup sequence.

### 9.2 Cross-schema references are prohibited at the DB level

```sql
-- FORBIDDEN: foreign key cross-schema
ALTER TABLE orchestrator_core.runs
  ADD CONSTRAINT fk_artifact
  FOREIGN KEY (artifact_id) REFERENCES artifact_core.artifacts(id);

-- ALLOWED: reference by UUID value, no foreign key constraint
-- Application-level join via API call or event
```

Rationale: cross-schema FKs create implicit ownership coupling — violating service isolation.

### 9.3 Schema versioning

Each schema must have a `schema_version` table:

```sql
CREATE TABLE orchestrator_core.schema_version (
  version TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

The service readiness probe checks schema version before accepting traffic.

---

## 10. Environment Configuration

### 10.1 Per-service env vars

Each service only receives env vars that belong to it:

```
# orchestrator
ORCHESTRATOR_DB_URL=          ← connects to orchestrator_core schema
ORCHESTRATOR_EVENT_BUS_URL=
ORCHESTRATOR_POLICY_SERVICE_URL=
ORCHESTRATOR_ARTIFACT_SERVICE_URL=
# Does not have: ARTIFACT_DB_URL, MODEL_API_KEY, SECRET_VAULT_URL

# artifact-service
ARTIFACT_DB_URL=              ← connects to artifact_core schema
ARTIFACT_STORAGE_BUCKET=
ARTIFACT_STORAGE_CREDENTIALS= ← separate
# Does not have: ORCHESTRATOR_DB_URL
```

### 10.2 Secret naming convention

```
{SERVICE_NAME}_{RESOURCE_TYPE}_{PURPOSE}
ORCHESTRATOR_DB_URL
ARTIFACT_STORAGE_ACCESS_KEY
MODEL_GATEWAY_ANTHROPIC_KEY
AUTH_JWT_SIGNING_SECRET
```

Provider API keys (`*_API_KEY`, `*_ACCESS_KEY`) must only be present in the owning service — no leaking to other services.

---

## 11. Intentionally Deferred Decisions

| Decision | Reason for deferral |
|---|---|
| Detailed Turborepo pipeline config | Needs real profiling when all services are in place |
| Full `dependency-cruiser` config | The template above is a framework — needs expansion as the codebase grows |
| Pre-commit hooks (husky vs lefthook) | Preference, does not affect architecture |
| Changesets / versioning strategy for packages | Needed when packages begin to be consumed externally |
| Test coverage thresholds | Needs baseline from actual codebase |
| Branch strategy (trunk-based vs gitflow) | Depends on team size and release cadence |

---

## 12. Next Steps

The final document is **17 — Implementation Roadmap**: dividing Phase A/B/C per the locked architecture, vertical slices, milestone criteria, and entry conditions for each phase — ensuring the team starts coding in the right order and does not drift from the architecture.
