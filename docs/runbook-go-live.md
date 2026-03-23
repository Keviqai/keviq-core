# Keviq Core — Go-Live Runbook

Operational playbook for deploying and running Keviq Core.
Covers pre-launch checklist, deployment profiles, startup procedures,
monitoring, recovery, rollback, and scaling guidance.

---

## 1. Pre-Launch Prerequisites

### 1.1 Infrastructure

- [ ] PostgreSQL 16 instance provisioned (or managed RDS/Cloud SQL)
- [ ] Redis 7 instance provisioned (or managed ElastiCache/Memorystore)
- [ ] Container runtime: Docker Compose v2.24.6+ (local/hardened) or Kubernetes (cloud)
- [ ] DNS and TLS configured for public endpoints (api-gateway, sse-gateway, web)
- [ ] Network policies: backend services accessible only within internal network

### 1.2 Database Setup

- [ ] Run `infra/docker/init-schemas.sql` to create per-service schemas and users
- [ ] Each service has its own DB user with access restricted to its own schema:
  - `auth_user` → `auth` schema
  - `orchestrator_user` → `orchestrator` schema
  - `event_store_user` → `event_store` schema
  - `execution_user` → `execution` schema
  - `artifact_user` → `artifact` schema
  - `workspace_user` → `workspace` schema
  - `agent_runtime_user` → `agent_runtime` schema
  - `model_gw_user` → `model_gateway` schema
  - `audit_user` → `audit` schema
  - `notification_user` → `notification` schema
  - `secret_user` → `secret` schema
  - `policy_user` → `policy` schema
- [ ] Run Alembic migrations for each service (order does not matter — schemas are independent)
- [ ] Verify migrations: `alembic current` should show `head` for each service

### 1.3 Secrets and Credentials

- [ ] Generate unique `AUTH_JWT_SECRET` (min 32 bytes, random)
- [ ] Generate unique `INTERNAL_AUTH_SECRET` (min 32 bytes, random)
- [ ] Generate unique `REDIS_PASSWORD`
- [ ] Set per-service DB passwords (avoid reusing the dev defaults)
- [ ] Store secrets in a secret manager (Vault, AWS Secrets Manager, etc.)
- [ ] Never commit secrets to the repository — use `.env` files or secret injection

### 1.4 Configuration

- [ ] Copy `.env.cloud.example` → `.env.cloud` and fill in all values
- [ ] Verify all required env vars are set (see `.env.cloud.example` for the full list)
- [ ] Set `CORS_ALLOWED_ORIGINS` to production frontend URL(s)
- [ ] Set `EXECUTION_BACKEND` to appropriate value:
  - `docker-local` for local development
  - `noop` for hardened/staging (no real sandbox execution)
  - `k8s-job` for cloud (future)
- [ ] Set `ARTIFACT_STORAGE_BACKEND`:
  - `local` for local/hardened
  - `s3` for cloud (requires `ARTIFACT_S3_BUCKET`, `ARTIFACT_S3_REGION`)

---

## 2. Deployment Profiles

Keviq Core supports 3 deployment profiles. Each profile is a Docker Compose overlay
applied on top of the base `docker-compose.yml`.

### 2.1 Local (Development)

```bash
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  --env-file .env.local up
```

Characteristics:
- `APP_ENV=development`, `DEPLOYMENT_PROFILE=local`
- All internal service ports exposed to host (debugging)
- Docker socket mounted for execution-service (real sandbox execution)
- Postgres and Redis ports accessible from host
- Dev secrets (acceptable for local only)

### 2.2 Hardened (Staging / CI)

```bash
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.hardened.yml \
  --env-file .env.hardened up
```

Characteristics:
- `APP_ENV=production`, `DEPLOYMENT_PROFILE=hardened`
- Internal service ports stripped (only api-gateway:8080, sse-gateway:8006, web:3000 exposed)
- Read-only root filesystem on all containers
- `no-new-privileges` security option on all containers
- Docker socket NOT mounted (`EXECUTION_BACKEND=noop`)
- Postgres/Redis not accessible from host

### 2.3 Cloud (Production)

```bash
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.cloud.yml \
  --env-file .env.cloud up
```

Characteristics:
- `APP_ENV=production`, `DEPLOYMENT_PROFILE=cloud`
- All config externalized via env vars (no dev defaults)
- DB URLs, secrets, bus URLs must all be provided
- S3 storage backend support
- Same security hardening as hardened profile

---

## 3. Service Startup Order

Services declare `depends_on` with health checks. Docker Compose handles ordering,
but the logical dependency graph is:

```
Layer 0 (Infrastructure):  postgres, redis
Layer 1 (Control):         auth-service, policy-service
Layer 2 (Domain):          workspace-service, orchestrator, agent-runtime,
                           artifact-service, execution-service, event-store,
                           model-gateway, secret-broker, audit-service,
                           notification-service, telemetry-service
Layer 3 (API Surface):     api-gateway, sse-gateway
Layer 4 (Frontend):        web
```

Critical dependency: `postgres` must be `healthy` before any service starts.
Redis must be `healthy` before event-bus consumers (orchestrator, agent-runtime,
event-store, notification-service, telemetry-service).

---

## 4. Health Check Verification

All 15 backend services expose 3 health endpoints:

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /healthz/live` | Liveness probe | `{"status": "live"}` |
| `GET /healthz/ready` | Readiness probe | `{"status": "ready"}` |
| `GET /healthz/info` | Deployment metadata | `{"service": "...", "app_env": "...", "deployment_profile": "..."}` |

### Quick health check script (all services)

```bash
SERVICES=(
  "auth-service:8007" "policy-service:8009" "orchestrator:8001"
  "agent-runtime:8002" "artifact-service:8003" "execution-service:8004"
  "workspace-service:8008" "secret-broker:8010" "model-gateway:8011"
  "audit-service:8012" "event-store:8013" "notification-service:8014"
  "telemetry-service:8015" "api-gateway:8080" "sse-gateway:8006"
)

for svc in "${SERVICES[@]}"; do
  name="${svc%%:*}"
  port="${svc##*:}"
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/healthz/ready")
  echo "${name}: ${status}"
done
```

### Profile verification

After startup, verify each service reports the correct profile:

```bash
curl -s http://localhost:8080/healthz/info | jq .deployment_profile
# Should match: "local", "hardened", or "cloud"
```

---

## 5. Background Tasks and Recovery

### 5.1 Orchestrator Background Tasks

The orchestrator runs two critical background loops:

| Task | Default Interval | Env Var | Purpose |
|------|-----------------|---------|---------|
| Recovery sweep | 60s | `RECOVERY_INTERVAL_SECONDS` | Finds stuck runs/steps/tasks and recovers them |
| Outbox relay | 5s | `OUTBOX_RELAY_INTERVAL_SECONDS` | Forwards outbox events to event-store |

Recovery thresholds (configurable):
- Runs stuck in PREPARING: 5 minutes
- Runs stuck in RUNNING: 30 minutes
- Runs stuck in COMPLETING: 5 minutes
- Steps stuck in RUNNING: 30 minutes

Both tasks are started in the lifespan context and gracefully cancelled on shutdown.

### 5.2 Execution-Service Recovery

The execution-service has its own recovery for stuck sandboxes:
- Sandboxes stuck in PROVISIONING: 10 minutes
- Sandboxes stuck in EXECUTING: 15 minutes

### 5.3 Outbox Relay Details

- Batch size: 50 events (configurable via `RELAY_BATCH_SIZE`)
- Timeout: 5s per batch (configurable via `RELAY_TIMEOUT`)
- Retry: 2 attempts with 0.5-3.0s backoff
- Poison pill protection: events exceeding 10 attempts are skipped

### 5.4 Verifying Recovery Is Running

Check orchestrator logs for periodic sweep messages:

```bash
docker compose logs orchestrator | grep -i "recovery sweep"
# Expected: "Recovery sweep scheduled every 60s"
# After time: "Recovery sweep completed: N actions (M failed)"
```

---

## 6. Monitoring and Observability

### 6.1 Key Metrics to Watch

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Service liveness | `/healthz/live` on each service | Any non-200 |
| Service readiness | `/healthz/ready` on each service | Any non-200 for > 30s |
| Recovery sweep failures | Orchestrator logs | Any failed recovery action |
| Outbox relay lag | Orchestrator logs | > 100 unrelayed events |
| DB connection pool exhaustion | SQLAlchemy logs | Pool overflow warnings |
| SSE client count | Event-store connection count | > 1000 concurrent |
| Container restarts | Docker/K8s metrics | > 3 restarts in 5 min |

### 6.2 Log Locations

All services log to stdout (Docker captures via log driver). Key log patterns:

```
# Recovery sweep results
"Recovery sweep completed: %d actions (%d failed)"

# Outbox relay activity
"Outbox relay: forwarded %d events"
"Batch relay failed after retries: ..."

# Internal auth failures
"Service auth failed: ..."

# SSE disconnections
"Client disconnected from SSE stream"
```

### 6.3 Database Monitoring

```sql
-- Check active connections per schema user
SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename;

-- Check for long-running queries (> 60s)
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle' AND now() - pg_stat_activity.query_start > interval '60 seconds';

-- Check outbox backlog
SELECT count(*) FROM orchestrator.outbox WHERE published_at IS NULL;
```

---

## 7. Backup and Data Safety

### 7.1 Database Backup

```bash
# Full backup (all schemas)
pg_dump -U <BACKUP_USER> -d mona_os -F c -f mona_os_backup_$(date +%Y%m%d).dump

# Per-schema backup (example: orchestrator)
pg_dump -U <BACKUP_USER> -d mona_os -n orchestrator -F c -f orchestrator_$(date +%Y%m%d).dump
```

**Important:** Use a dedicated backup role with read-only privileges — never
use the superuser account for automated backups in production.

Recommended schedule:
- Full backup: daily
- WAL archiving: continuous (for point-in-time recovery)
- Backup retention: 30 days minimum

### 7.2 Critical Data

| Schema | Contains | Backup Priority |
|--------|----------|----------------|
| `orchestrator` | Tasks, Runs, Steps, Outbox | HIGH |
| `event_store` | All domain events | HIGH |
| `workspace` | Workspace definitions, memberships | HIGH |
| `artifact` | Artifact metadata | MEDIUM |
| `auth` | Users, sessions | HIGH |
| `secret` | Encrypted secrets | CRITICAL |
| `execution` | Sandbox records | LOW (ephemeral) |

### 7.3 Redis Data

Redis stores the event bus streams. Data is transient and replayed from outbox on restart.
Redis backup is optional but recommended for reducing replay lag after restart.

---

## 8. Rollback Procedures

### 8.1 Service Rollback

```bash
# Roll back a single service to previous image
docker compose -f docker-compose.yml -f docker-compose.<profile>.yml \
  up -d --no-deps <service-name>

# Roll back all services
docker compose -f docker-compose.yml -f docker-compose.<profile>.yml \
  down && git checkout <previous-tag> && \
  docker compose -f docker-compose.yml -f docker-compose.<profile>.yml up -d
```

### 8.2 Database Rollback

```bash
# Downgrade a specific service's schema
cd apps/<service-name>
alembic downgrade -1

# Restore from backup
pg_restore -U <BACKUP_USER> -d mona_os -c mona_os_backup_YYYYMMDD.dump
```

### 8.3 Rollback Decision Matrix

| Scenario | Action |
|----------|--------|
| Single service failing | Rollback that service only, keep others |
| Migration broke schema | `alembic downgrade`, then rollback service |
| Multiple services failing | Full rollback to last known-good tag |
| Data corruption | Stop services, restore from backup, replay outbox |

---

## 9. Scaling Guidance

### 9.1 Horizontal Scaling

Services that can be scaled horizontally (stateless):
- `api-gateway` — scale behind load balancer
- `sse-gateway` — scale with sticky sessions (SSE connections are long-lived)
- `agent-runtime` — scale based on invocation throughput
- `model-gateway` — scale based on LLM request volume

Services that can scale but benefit from fewer instances:
- `orchestrator` — recovery sweep uses SKIP LOCKED (safe with multiple instances, but adds wasted work)
- `event-store` — ingest is idempotent, safe to scale horizontally

### 9.2 Resource Tuning

| Service | Default Memory | High-Load Memory | Default CPU | High-Load CPU |
|---------|---------------|-------------------|-------------|---------------|
| postgres | 512M | 2G+ | 1.0 | 4.0 |
| redis | 256M | 1G | 0.5 | 2.0 |
| orchestrator | 512M | 1G | 1.0 | 2.0 |
| api-gateway | 256M | 512M | 0.5 | 2.0 |
| agent-runtime | 512M | 1G | 1.0 | 2.0 |
| Other services | 256M | 512M | 0.5 | 1.0 |

### 9.3 Connection Pool Tuning

The orchestrator configures SQLAlchemy pool with:
- `pool_size=15` — base connections
- `max_overflow=5` — burst capacity
- `pool_recycle=3600` — recycle stale connections

For high load, increase `pool_size` and **you must increase** PostgreSQL
`max_connections` to accommodate all service pools combined. The default of
100 is insufficient — with 12 DB services at `pool_size=15`, you need at
least 200. Set this before go-live.

### 9.4 Relay and SSE Tuning

| Parameter | Default | High-Load | Env Var |
|-----------|---------|-----------|---------|
| Relay batch size | 50 | 200 | `RELAY_BATCH_SIZE` |
| Relay interval | 5s | 1s | `OUTBOX_RELAY_INTERVAL_SECONDS` |
| Relay timeout | 5s | 10s | `RELAY_TIMEOUT` |
| SSE heartbeat | 15s | 15s | (code constant) |
| SSE poll interval | 1s | 1s | (code constant) |
| Max batch ingest | 500 | 500 | (code constant) |

---

## 10. Troubleshooting

### 10.1 Service Won't Start

1. Check `docker compose logs <service>` for error messages
2. Verify DB URL is correct and DB is reachable
3. Verify required env vars are set (service will log `RuntimeError` if missing)
4. Check `docker compose ps` for restart loops

### 10.2 Events Not Flowing

1. Check orchestrator logs for relay activity: `grep "relay" orchestrator.log`
2. Check outbox backlog: `SELECT count(*) FROM orchestrator.outbox WHERE published_at IS NULL`
3. Check event-store health: `curl /healthz/ready`
4. Check internal auth: verify `INTERNAL_AUTH_SECRET` matches between services

### 10.3 Recovery Sweep Not Working

1. Check orchestrator logs: `grep "Recovery sweep" orchestrator.log`
2. Verify `RECOVERY_INTERVAL_SECONDS` env var
3. Check for stuck entities manually:
   ```sql
   SELECT id, run_status, created_at FROM orchestrator.runs
   WHERE run_status IN ('preparing', 'running', 'completing')
   AND created_at < NOW() - INTERVAL '30 minutes';
   ```

### 10.4 SSE Stream Disconnecting

1. Check for proxy buffering (nginx: set `X-Accel-Buffering: no`)
2. Check for idle timeout on load balancer (increase to > 60s)
3. Verify `Cache-Control: no-cache` and `Connection: keep-alive` headers
4. Client should implement reconnection with `Last-Event-ID`

---

## 11. Operational Checklist (Go-Live Day)

### Before Go-Live

- [ ] All migrations applied and verified (`alembic current` = head)
- [ ] All secrets rotated from dev defaults
- [ ] `.env.cloud` (or secret manager) fully populated
- [ ] Backup strategy configured and tested
- [ ] Monitoring dashboards set up
- [ ] Alerting configured for health check failures
- [ ] Load test completed (if applicable)
- [ ] Rollback procedure tested

### During Go-Live

- [ ] Start infrastructure (postgres, redis) — wait for healthy
- [ ] Start control services (auth, policy) — verify `/healthz/ready`
- [ ] Start domain services — verify all `/healthz/ready`
- [ ] Start api-gateway and sse-gateway — verify `/healthz/ready`
- [ ] Start web frontend
- [ ] Verify `/healthz/info` shows correct profile on all services
- [ ] Verify recovery sweep is running (orchestrator logs)
- [ ] Verify outbox relay is active (orchestrator logs)
- [ ] Create test workspace via API — verify end-to-end

### After Go-Live

- [ ] Monitor logs for first 30 minutes
- [ ] Verify no container restart loops
- [ ] Verify no DB connection pool warnings
- [ ] Verify SSE streams are working (create task, observe timeline)
- [ ] Take first production backup
