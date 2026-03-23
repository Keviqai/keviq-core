# SYSTEM REGISTRY — Keviq Core

> Single source of truth for all system parameters.
> UPDATE this file EVERY TIME any config/infra changes.

## 1. Services & Ports

| Service | Internal | External | Health Check | Status |
|---------|----------|----------|-------------|--------|
| api-gateway | 8000 | 8080 | `/healthz/live` | COMPLETE |
| auth-service | 8000 | 8007 | `/healthz/live` | COMPLETE |
| workspace-service | 8000 | 8008 | `/healthz/live` | COMPLETE |
| policy-service | 8000 | 8009 | `/healthz/live` | COMPLETE |
| orchestrator | 8000 | 8001 | `/healthz/live` | COMPLETE |
| agent-runtime | 8000 | 8002 | `/healthz/live` | COMPLETE |
| artifact-service | 8000 | 8003 | `/healthz/live` | COMPLETE |
| execution-service | 8000 | 8004 | `/healthz/live` | COMPLETE |
| event-store | 8000 | 8013 | `/healthz/live` | COMPLETE |
| model-gateway | 8000 | 8011 | `/healthz/live` | COMPLETE |
| sse-gateway | 8000 | 8006 | `/healthz/live` | STUB |
| audit-service | 8000 | 8012 | `/healthz/live` | FUNCTIONAL |
| notification-service | 8000 | 8014 | `/healthz/live` | FUNCTIONAL |
| secret-broker | 8000 | 8010 | `/healthz/live` | FUNCTIONAL |
| telemetry-service | 8000 | 8015 | `/healthz/live` | FUNCTIONAL |
| claude-bridge | 8000 | 8016 | `/healthz/live` | LOCAL-ONLY |
| web (Next.js) | 3000 | 3000 | GET / | PARTIAL |
| postgres | 5432 | 5434 | pg_isready | INFRA |
| redis | 6379 | 6379 | redis-cli ping | INFRA |

## 2. Database

| Param | Value |
|-------|-------|
| Engine | PostgreSQL 16 |
| Host (internal) | postgres |
| Host (external) | localhost |
| Port | 5432 (internal) / 5434 (external) |
| Database | mona_os |
| Superuser | superuser / superpassword |
| Migration tool | Alembic (per service) |
| Migration cmd | `./scripts/bootstrap.sh migrate` |
| Schema strategy | 1 schema per service (S1 invariant) |

### Schemas & Users

| Service | Schema | DB User | Password |
|---------|--------|---------|----------|
| auth-service | identity_core | auth_user | auth_pass |
| workspace-service | workspace_core | workspace_user | workspace_pass |
| policy-service | policy_core | policy_user | policy_pass |
| orchestrator | orchestrator_core | orchestrator_user | orch_pass |
| agent-runtime | agent_runtime | agent_runtime_user | agent_pass |
| artifact-service | artifact_core | artifact_user | artifact_pass |
| execution-service | execution_core | execution_user | exec_pass |
| event-store | event_core | event_store_user | event_pass |
| model-gateway | model_gateway_core | model_gw_user | model_gw_pass |
| audit-service | audit_core | audit_user | audit_pass |
| secret-broker | secret_core | secret_user | secret_pass |
| notification-service | notification_core | notification_user | notif_pass |
| telemetry-service | telemetry_core | telemetry_user | telemetry_pass |

### Migration Paths

| Service | Alembic Dir | Env Var for DB URL |
|---------|------------|-------------------|
| auth-service | apps/auth-service/alembic | AUTH_DB_URL |
| workspace-service | apps/workspace-service/alembic | WORKSPACE_DB_URL |
| policy-service | apps/policy-service/alembic | POLICY_DB_URL |
| orchestrator | apps/orchestrator/alembic | ORCHESTRATOR_DB_URL |
| agent-runtime | apps/agent-runtime/alembic | AGENT_RUNTIME_DB_URL |
| artifact-service | apps/artifact-service/alembic | ARTIFACT_DB_URL |
| execution-service | apps/execution-service/alembic | EXECUTION_DB_URL |
| event-store | apps/event-store/alembic | EVENT_STORE_DB_URL |
| model-gateway | apps/model-gateway/alembic | MODEL_GW_DB_URL |
| audit-service | apps/audit-service/alembic | AUDIT_DB_URL |

## 3. Cache / Message Broker

| Param | Value |
|-------|-------|
| Engine | Redis 7 |
| Host (internal) | redis |
| Port | 6379 |
| Password | dev-redis-password |
| Usage | Event bus (Redis Streams) + cache |

Services using Redis Streams: orchestrator, agent-runtime, event-store, notification-service, telemetry-service

## 4. API Contracts (Gateway Routes)

| Gateway Path | Method | Routes To | Auth |
|-------------|--------|-----------|------|
| /v1/auth/register | POST | auth-service | No |
| /v1/auth/login | POST | auth-service | No |
| /v1/auth/refresh | POST | auth-service | No |
| /v1/auth/me | GET | auth-service | JWT |
| /v1/workspaces | GET, POST | workspace-service | JWT |
| /v1/workspaces/{id} | GET, PATCH, DELETE | workspace-service | JWT + membership |
| /v1/workspaces/{id}/members | GET, POST | workspace-service | JWT + membership |
| /v1/workspaces/{id}/artifacts | GET | artifact-service | JWT + membership |
| /v1/workspaces/{id}/artifacts/upload | POST | artifact-service | JWT + membership |
| /v1/workspaces/{id}/policies | GET, POST | policy-service | JWT + membership |
| /v1/task-templates | GET | orchestrator | JWT |
| /v1/task-templates/{id} | GET | orchestrator | JWT |
| /v1/agent-templates | GET | orchestrator | JWT |
| /v1/agent-templates/{id} | GET | orchestrator | JWT |
| /v1/tasks | GET, POST | orchestrator | JWT |
| /v1/tasks/draft | POST | orchestrator | JWT + task:create |
| /v1/tasks/{id} | GET, PATCH | orchestrator | JWT + task:view/create |
| /v1/tasks/{id}/launch | POST | orchestrator | JWT + task:create |
| /v1/tasks/{id}/cancel | POST | orchestrator | JWT |
| /v1/tasks/{id}/retry | POST | orchestrator | JWT + task:create |
| /v1/tasks/{id}/timeline | GET | event-store | JWT |
| /v1/runs/{id} | GET | orchestrator | JWT |
| /v1/runs/{id}/steps | GET | orchestrator | JWT |
| /v1/runs/{id}/timeline | GET | event-store | JWT |
| /v1/runs/{id}/events/stream | GET (SSE) | event-store | JWT |
| /v1/workspaces/{id}/approvals | GET | orchestrator | JWT + workspace:view |
| /v1/workspaces/{id}/approvals | POST | orchestrator | JWT + workspace:view |
| /v1/workspaces/{id}/approvals/count | GET | orchestrator | JWT + workspace:view |
| /v1/workspaces/{id}/approvals/{aid} | GET | orchestrator | JWT + workspace:view |
| /v1/workspaces/{id}/approvals/{aid}/decide | POST | orchestrator | JWT + approval:decide |
| /v1/workspaces/{id}/secrets | GET | secret-broker | JWT + workspace:manage_secrets |
| /v1/workspaces/{id}/secrets | POST | secret-broker | JWT + workspace:manage_secrets |
| /v1/workspaces/{id}/secrets/{sid} | DELETE | secret-broker | JWT + workspace:manage_secrets |
| /v1/workspaces/{id}/secrets/{sid} | PATCH | secret-broker | JWT + workspace:manage_secrets |
| /internal/v1/artifacts/{aid} | GET | artifact-service | Internal (api-gateway, agent-runtime, orchestrator); requires `?workspace_id=` param |
| /internal/v1/artifacts/{aid}/annotations | GET | artifact-service | Internal (api-gateway, orchestrator); requires `?workspace_id=` param |
| /internal/v1/secrets/{sid}/value | GET | secret-broker | Internal (model-gateway only) |
| /internal/v1/users/lookup?ids=... | GET | auth-service | Internal (workspace-service only) |
| /v1/workspaces/{id}/activity | GET | event-store | JWT + workspace:view |
| /v1/workspaces/{id}/notifications | GET | notification-service | JWT + workspace:view |
| /v1/workspaces/{id}/notifications/count | GET | notification-service | JWT + workspace:view |
| /v1/workspaces/{id}/notifications/{nid}/read | POST | notification-service | JWT + workspace:view |
| /v1/workspaces/{id}/notifications/read-all | POST | notification-service | JWT + workspace:view |
| /v1/workspaces/{id}/integrations | GET, POST | model-gateway | JWT + workspace:manage_integrations |
| /v1/workspaces/{id}/integrations/{iid} | GET, PATCH, DELETE | model-gateway | JWT + workspace:manage_integrations |
| /v1/workspaces/{id}/integrations/{iid}/toggle | POST | model-gateway | JWT + workspace:manage_integrations |
| /v1/terminal/sessions | POST | execution-service | JWT + run:terminal |
| /v1/terminal/sessions/{id} | GET | execution-service | JWT + ownership |
| /v1/terminal/sessions/{id}/exec | POST | execution-service | JWT + ownership |
| /v1/terminal/sessions/{id}/history | GET | execution-service | JWT + ownership |
| /v1/terminal/sessions/{id}/close | POST | execution-service | JWT + ownership |
| /internal/v1/tool-approvals | POST | orchestrator | Internal (agent-runtime only) — creates tool approval request when policy gates a tool call |
| /internal/v1/invocations/{id}/resume | POST | agent-runtime | Internal (orchestrator only) — resumes WAITING_HUMAN invocation after tool approval decision (approved/rejected) |
| /v1/tool-executions/{id} | GET | execution-service | JWT (auth-only, workspace validated by execution-service via sandbox) — tool execution detail with stdout/stderr/input |
| /v1/sandboxes/{id} | GET | execution-service | JWT (auth-only, workspace validated by execution-service) — sandbox metadata with status/type/policies |
| /v1/workspaces/{id}/tasks/{tid}/comments | GET, POST | orchestrator | JWT + workspace:view — list/create task comments |
| /internal/v1/scrape | POST | telemetry-service | Internal — triggers scrape of /metrics from all 15 services |
| /internal/v1/metrics | GET | telemetry-service | Internal — query latest scraped metric samples, optional ?service= filter |
| /v1/workspaces/{id}/artifacts/{aid}/tags | GET, POST | artifact-service | JWT + workspace:view — list/add artifact tags (O9) |
| /v1/workspaces/{id}/artifacts/{aid}/tags/{tag} | DELETE | artifact-service | JWT + workspace:view — remove artifact tag (O9) |
| /internal/v1/workspaces/{wid}/secrets/rotate | POST | secret-broker | Internal — re-encrypts all workspace secrets to latest key version (O9) |
| /internal/v1/workspaces/{wid}/secrets/rotation-status | GET | secret-broker | Internal — reports secret counts per key version (O9) |

## 5. Auth & Security

| Param | Value |
|-------|-------|
| Auth method | JWT (access + refresh) |
| JWT secret | AUTH_JWT_SECRET (env var) |
| Access token lifetime | 30 minutes |
| Refresh token lifetime | 7 days |
| Password hashing | bcrypt |
| Inter-service auth | INTERNAL_AUTH_SECRET header |
| CORS origins (dev) | http://localhost:3000 |

## 6. Environment Variables

| Variable | Default (dev) | Required | Used By |
|----------|--------------|----------|---------|
| POSTGRES_USER | superuser | Yes | postgres |
| POSTGRES_PASSWORD | superpassword | Yes | postgres |
| POSTGRES_DB | mona_os | Yes | postgres |
| REDIS_PASSWORD | dev-redis-password | Yes | redis, all event-bus services |
| AUTH_JWT_SECRET | dev-secret-change-in-production | Yes | api-gateway, auth-service |
| INTERNAL_AUTH_SECRET | dev-internal-auth-secret-change-in-production | Yes | all services |
| SECRET_ENCRYPTION_KEY | (base64, 32-byte AES key) | Yes | secret-broker — fallback key (maps to version 1) |
| SECRET_ENCRYPTION_KEY_V1 | (base64, 32-byte AES key) | No | secret-broker — versioned key v1 (O9 rotation) |
| SECRET_ENCRYPTION_KEY_V2 | (base64, 32-byte AES key) | No | secret-broker — versioned key v2; add _V3, _V4, etc. as needed |
| RATE_LIMIT_WRITE | 60/60 | No | api-gateway — write endpoint rate limit (requests/window_seconds) |
| RATE_LIMIT_READ | 300/60 | No | api-gateway — read endpoint rate limit |
| RATE_LIMIT_GLOBAL_IP | 600/60 | No | api-gateway — global per-IP rate limit |
| CORS_ALLOWED_ORIGINS | http://localhost:3000 | No | api-gateway |
| APP_ENV | development | No | all services |
| SERVICE_NAME | (service identifier) | No | all services — used by mona_os_logger |
| LOG_LEVEL | INFO | No | all services — mona_os_logger verbosity (DEBUG/INFO/WARNING/ERROR) |
| DEPLOYMENT_PROFILE | local | No | all services |
| EXECUTION_SERVICE_URL | http://execution-service:8000 | No | api-gateway |
| SECRET_BROKER_URL | http://secret-broker:8000 | No | api-gateway |
| NOTIFICATION_SERVICE_URL | http://notification-service:8000 | No | orchestrator, api-gateway |
| NOTIFICATION_DB_URL | postgresql://... | Yes | notification-service |
| SMTP_HOST | (unset) | No | notification-service — email delivery disabled if unset |
| SMTP_PORT | 587 | No | notification-service |
| SMTP_USERNAME | (unset) | No | notification-service |
| SMTP_PASSWORD | (unset) | No | notification-service |
| SMTP_FROM_EMAIL | noreply@monaos.app | No | notification-service |
| SMTP_USE_TLS | true | No | notification-service — set false only for local dev SMTP (mailpit/mailhog) |
| MODEL_GATEWAY_URL | http://model-gateway:8000 | No | api-gateway |
| AUDIT_SERVICE_URL | http://audit-service:8000 | No | orchestrator, api-gateway — audit events; fail-open if unset |
| ARTIFACT_SERVICE_URL | http://artifact-service:8000 | No (skip validation if unset) | orchestrator |
| WORKSPACE_SERVICE_URL | http://workspace-service:8000 | No (skip validation if unset) | orchestrator |
| AUTH_SERVICE_URL | http://auth-service:8000 | No (skip name enrichment if unset) | workspace-service |
| EVENT_RETENTION_DAYS | 90 | No | event-store — events older than N days deleted on cleanup |
| OUTBOX_RETENTION_DAYS | 7 | No | orchestrator — published outbox rows older than N days deleted on cleanup |
| NOTIFICATION_RETENTION_DAYS | 30 | No | notification-service — read notifications older than N days deleted on cleanup |
| CLEANUP_BATCH_SIZE | 1000 | No | all cleanup endpoints — max rows deleted per call (hard cap 5000) |
| EXECUTION_SERVICE_URL | http://execution-service:8000 | No | agent-runtime — tool execution dispatch; tool loop disabled if unset |
| MAX_TOOL_TURNS | 5 | No | agent-runtime — max model→tool→model loops per invocation (prevents runaway) |
| INVOCATION_BUDGET_MS | 120000 | No | agent-runtime — total wall-clock budget per invocation (model + tool calls combined) |
| AGENT_DISPATCH_TIMEOUT_MS | 120000 | No | orchestrator — HTTP timeout for agent-runtime dispatch; must be ≥ INVOCATION_BUDGET_MS |
| INVOCATION_STUCK_TIMEOUT_S | 300 | No | agent-runtime — invocations in non-terminal state older than this are recovered to FAILED |
| ORCHESTRATOR_URL | http://orchestrator:8000 | No | agent-runtime — orchestrator URL for tool approval requests; approval gate disabled if unset |
| TOOL_APPROVAL_MODE | gate | No | agent-runtime — tool approval policy mode: `none` (O4 behavior), `warn` (log only), `gate` (require human approval for risky tools) |

## 7. File & Directory Structure

| Path | Purpose |
|------|---------|
| apps/ | 15 backend services + 1 frontend |
| apps/*/src/ | Service source code (hexagonal: api/, application/, domain/, infrastructure/) |
| apps/*/alembic/ | Service-specific Alembic migrations |
| packages/ | 14 shared packages (api-client, domain-types, ui-core, etc.) |
| tools/arch-test/ | 945+ architecture gate tests |
| infra/docker/ | Docker Compose files, .env.local, init-schemas.sql |
| infra/docker/docker-compose.observability.yml | Optional Prometheus (9090) + Grafana (3001) stack |
| infra/prometheus/ | Prometheus scrape config for all 15 services |
| infra/grafana/ | Grafana dashboards + provisioning config |
| docs/ops/ | Operational docs: observability, rate-limiting, secret-rotation, artifact-search, production-deployment-checklist |
| scripts/ | bootstrap.sh, smoke-test.sh, clean-boot-test.sh, pre-commit-gate.sh |
| docs/ | 18 architecture specs + governance docs |

## 8. Seed Data (dev)

| Entity | Details |
|--------|---------|
| Smoke test user | Email: `smoke-TIMESTAMP@test.com`, Password: `SmokeTest1234!` (created by smoke-test.sh, ephemeral) |
| DB schemas | 12 schemas auto-created by `infra/docker/init-schemas.sql` on first boot |
| System task templates | 3 seeded via migration a007: Research Brief, Ops Case Prep, Data Analysis |
| System agent templates | 3 seeded via migration a007: Research Analyst, Ops Assistant, General Agent |

> Note: Keviq Core does not have a persistent seed script. Test data is created by smoke-test.sh and cleaned on `docker compose down -v`.

## 9. Docker Health Checks & Startup

All 18 services (16 app + 2 infra) have `healthcheck` blocks in docker-compose.yml.

| Service Type | Health Check Command | Interval | Timeout | Retries | Start Period |
|-------------|---------------------|----------|---------|---------|-------------|
| Python services (15) | `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"` | 10s | 5s | 3 | 30s |
| web (Next.js) | `node -e "require('http').get('http://localhost:3000', ...)"` | 10s | 5s | 3 | 45s |
| postgres | `pg_isready -U superuser -d mona_os` | 5s | 5s | 5 | — |
| redis | `redis-cli -a $REDIS_PASSWORD ping` | 5s | 5s | 5 | — |

**Startup order (via `depends_on: { condition: service_healthy }`):**
1. postgres + redis (infra, parallel)
2. auth-service, policy-service (control, depend on postgres)
3. workspace-service (depends on auth-service)
4. artifact-service, execution-service, model-gateway, secret-broker, event-store, notification-service, audit-service, telemetry-service (domain, depend on postgres/redis)
5. orchestrator (depends on policy-service, notification-service, audit-service)
6. agent-runtime (depends on postgres, redis)
7. api-gateway (depends on auth-service, policy-service, workspace-service)
8. sse-gateway (depends on redis, auth-service)
9. web (depends on api-gateway)

All `depends_on` conditions use `service_healthy` — Docker Compose waits for the health check to pass before starting dependent services.

## 10. Dependencies & Versions

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12 | Backend runtime |
| FastAPI | 0.115+ | API framework |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.13+ | Migration |
| Node.js | 22+ | Frontend runtime |
| Next.js | 15 | Frontend framework |
| React | 19 | UI library |
| TypeScript | 5.4+ | Type safety |
| pnpm | 9+ | Package manager |
| Docker | 24+ | Containerization |
| Docker Compose | 2.24+ | Orchestration |
| PostgreSQL | 16 | Database |
| Redis | 7 | Event bus + cache |
