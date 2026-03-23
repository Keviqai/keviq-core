# Production Deployment Checklist — Keviq Core

> Operator guide for deploying Keviq Core outside of a dev laptop.
> Covers prerequisites, required configuration, bring-up procedure,
> verification, known limitations, and recovery.
>
> Last updated: 2026-03-23 (CVP-8)

---

## A. Host Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Docker Engine | 24+ | `docker --version` |
| Docker Compose | 2.24+ | `docker compose version` |
| CPU | 4 cores | 18 containers; orchestrator + agent-runtime are heaviest |
| RAM | 8 GB | PostgreSQL 512 MB + Redis 256 MB + 15 services at 256 MB each |
| Disk | 20 GB | Images ~10 GB + PostgreSQL data + artifact storage |
| curl | any | Used by smoke-test.sh and bootstrap.sh |
| Ports available | 3000, 5434, 6379, 8080 | Frontend, PostgreSQL, Redis, API Gateway |

**Execution-service caveat:** If you need agent sandbox execution (UJ-015 Terminal), the execution-service container requires Docker socket access:
```
# Add to docker-compose override for execution-service:
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```
Without this, execution-service crash-loops. The remaining 17 services and 20/21 user journeys work without it.

---

## B. Required Configuration

### B1. Secrets — MUST change from dev defaults

| Variable | Dev Default | Production Action |
|----------|------------|-------------------|
| `POSTGRES_PASSWORD` | `superpassword` | Generate strong password (32+ chars) |
| `REDIS_PASSWORD` | `dev-redis-password` | Generate strong password |
| `AUTH_JWT_SECRET` | `dev-secret-change-in-production` | Generate random 64-char string: `openssl rand -hex 32` |
| `INTERNAL_AUTH_SECRET` | `dev-internal-auth-secret-change-in-production` | Generate random 64-char string: `openssl rand -hex 32` |
| `SECRET_ENCRYPTION_KEY` | Base64 dev key | Generate 32-byte AES key: `openssl rand -base64 32` |

**All secrets above use dev defaults that are visible in the repo. Using them in production is a security vulnerability.**

### B2. Versioned encryption keys (O9 rotation)

For secret rotation support, set versioned keys instead of the single key:
```bash
SECRET_ENCRYPTION_KEY_V1=<base64-32-byte-key>   # Initial key
# When rotating: add V2 and re-encrypt via /internal/v1/workspaces/{wid}/secrets/rotate
```
See [docs/ops/secret-rotation.md](secret-rotation.md) for the full rotation procedure.

### B3. Application configuration

| Variable | Default | Production Recommendation |
|----------|---------|--------------------------|
| `APP_ENV` | `development` | Set to `production` (disables Swagger docs on all services) |
| `LOG_LEVEL` | `INFO` | Keep `INFO`; set `WARNING` if logs are too noisy |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Set to actual frontend URL |
| `SMTP_HOST` | (unset) | Set for email notifications (approval alerts). Unset = notifications skipped silently |
| `SMTP_PORT` | 587 | |
| `SMTP_USERNAME` | (unset) | SMTP auth credentials |
| `SMTP_PASSWORD` | (unset) | |
| `SMTP_FROM_EMAIL` | `noreply@monaos.app` | Set to your domain |
| `SMTP_USE_TLS` | `true` | Keep `true` for production SMTP |

### B4. Rate limiting (O9)

Defaults are reasonable for pilot. Override only if needed:

| Variable | Default | Meaning |
|----------|---------|---------|
| `RATE_LIMIT_WRITE` | `60/60` | 60 write requests per 60 seconds per user |
| `RATE_LIMIT_READ` | `300/60` | 300 read requests per 60 seconds per user |
| `RATE_LIMIT_GLOBAL_IP` | `600/60` | 600 total requests per 60 seconds per IP |

**Limitation:** Rate limiting is in-memory (single gateway instance). Not shared across replicas. See deferred items.

### B5. Configuration file location

All env vars go in `infra/docker/.env.local`. Copy from example:
```bash
cp infra/docker/.env.example infra/docker/.env.local
# Edit .env.local with production values
```

---

## C. Bring-Up Procedure

### C1. First deployment (clean state)

```bash
# 1. Clone and configure
git clone <repo-url> monaos && cd monaos
cp infra/docker/.env.example infra/docker/.env.local
# Edit .env.local with production secrets (section B)

# 2. Bootstrap (builds images, runs migrations, starts services)
./scripts/bootstrap.sh full

# 3. Verify
./scripts/smoke-test.sh
# Expected: ALL 21 CHECKS PASSED
```

### C2. Normal restart (data preserved)

```bash
./scripts/bootstrap.sh up
# Or directly:
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local.yml \
  --env-file infra/docker/.env.local up -d
```

### C3. After code changes (rebuild + restart)

```bash
# Rebuild changed services
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local.yml \
  --env-file infra/docker/.env.local \
  build <service-name>

# Restart
docker compose ... up -d <service-name>

# IMPORTANT: If frontend code changed, rebuild web:
docker compose ... build web && docker compose ... up -d web
```

### C4. Clean-boot verification (destroys all data)

```bash
./scripts/clean-boot-test.sh
# This runs: down -v → bootstrap full → smoke 21/21
# WARNING: Deletes all PostgreSQL data and artifact storage
```

### C5. Observability stack (optional)

```bash
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local.yml \
  -f infra/docker/docker-compose.observability.yml \
  --env-file infra/docker/.env.local up -d

# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3001 (admin/admin)
```

See [docs/ops/observability.md](observability.md) for dashboard details.

---

## D. Post-Deploy Verification

### D1. Health endpoints

All services expose `/healthz/live`. Key ones to check:

```bash
curl -sf http://localhost:8080/healthz/live   # API Gateway
curl -sf http://localhost:8007/healthz/live   # Auth
curl -sf http://localhost:8001/healthz/live   # Orchestrator
curl -sf http://localhost:8003/healthz/live   # Artifact
curl -sf http://localhost:8013/healthz/live   # Event Store
curl -sf http://localhost:8008/healthz/live   # Workspace
```

### D2. Metrics endpoints

All 15 services expose `/metrics` in Prometheus format:

```bash
curl -s http://localhost:8080/metrics | head -5   # API Gateway
curl -s http://localhost:8001/metrics | head -5   # Orchestrator
```

### D3. Smoke test

```bash
./scripts/smoke-test.sh
# Must show: ALL 21 CHECKS PASSED
```

### D4. Browser verification

1. Open `http://localhost:3000`
2. Register a new user
3. Login
4. Create a workspace
5. Navigate to Tasks, Artifacts, Approvals, Activity pages
6. All should load without errors

### D5. Minimum success criteria

| Check | Expected |
|-------|----------|
| `docker compose ps` | 17/18 healthy (execution-service may crash-loop without Docker socket) |
| smoke-test.sh | 21/21 PASS |
| Browser register + login | Works, redirects to workspace |
| No 500 errors in browser console | Only 403 if logged out, 401 on expired session |

---

## E. Known Limitations & Accepted Debt

### E1. Blocking pilot only with workaround

| Item | Impact | Workaround |
|------|--------|-----------|
| execution-service Docker socket | Sandbox execution (UJ-015) unavailable | Mount `/var/run/docker.sock` or accept no terminal/sandbox |
| Stale web container after code changes | Browser shows 404/403 on API calls | Rebuild: `docker compose build web && docker compose up -d web` |

### E2. Non-blocking accepted debt

| Item | Impact | Status |
|------|--------|--------|
| Rate limiting in-memory only | Resets on gateway restart; no sharing across replicas | Single instance OK for pilot |
| No mTLS between services | Inter-service traffic unencrypted on Docker network | Acceptable for single-host; add TLS for multi-host |
| No trigram index on artifact name | ILIKE search degrades above ~1000 artifacts | Add `pg_trgm` GIN index when needed |
| BaseHTTPMiddleware response buffering | Large responses buffered in memory | Acceptable for typical JSON payloads |
| Event/outbox/notification cleanup not scheduled | Tables grow over time | Call cleanup endpoints manually or via cron (see section F) |
| Resume handler tool definitions lost on approval | Agent loses tool access after approval gate resume | Document as pilot limitation; fix in post-CVP |

---

## F. Maintenance & Cleanup

### F1. Event retention

Events grow with every task/run. Clean old events periodically:

```bash
# Delete events older than 90 days (configurable via EVENT_RETENTION_DAYS)
curl -X POST http://localhost:8013/internal/v1/events/cleanup

# Delete published outbox rows older than 7 days
curl -X POST http://localhost:8001/internal/v1/outbox/cleanup

# Delete read notifications older than 30 days
curl -X POST http://localhost:8014/internal/v1/notifications/cleanup
```

Add to cron for automated cleanup:
```bash
0 3 * * * curl -sf -X POST http://localhost:8013/internal/v1/events/cleanup
0 3 * * * curl -sf -X POST http://localhost:8001/internal/v1/outbox/cleanup
0 3 * * 0 curl -sf -X POST http://localhost:8014/internal/v1/notifications/cleanup
```

### F2. Secret key rotation

See [docs/ops/secret-rotation.md](secret-rotation.md) for step-by-step key rotation.

### F3. Log inspection

```bash
# All services
docker compose -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.local.yml \
  --env-file infra/docker/.env.local logs --tail 50

# Specific service
docker compose ... logs orchestrator --tail 100 -f
```

Logs are structured JSON in production (`APP_ENV=production`), human-readable in development.

---

## G. Rollback & Recovery

### G1. Safe restart (preserves data)

```bash
docker compose ... down       # Stop all containers (data preserved in volumes)
docker compose ... up -d      # Restart
./scripts/smoke-test.sh       # Verify
```

### G2. Full reset (destroys all data)

```bash
docker compose ... down -v    # Stop + delete volumes (PostgreSQL data, artifact files)
./scripts/bootstrap.sh full   # Fresh start with clean DB
./scripts/smoke-test.sh       # Verify
```

**WARNING:** `down -v` deletes all user data, tasks, artifacts, approvals, and secrets.

### G3. Single service restart

```bash
docker compose ... restart orchestrator
docker compose ... logs orchestrator --tail 20   # Check it recovered
```

### G4. Migration issues

If a service fails to start after migration:
```bash
# Check migration state
docker compose ... run --rm <service> alembic current

# Rerun migrations
docker compose ... run --rm -e "<DB_URL>=postgresql://superuser:superpassword@postgres/mona_os" <service> alembic upgrade head
```

### G5. When to contact support

- Multiple services crash-looping (not just execution-service)
- PostgreSQL won't start or reports corruption
- Migrations fail after previously succeeding
- 500 errors on all API endpoints
- Data inconsistency (task shows wrong status, artifacts missing)

---

## H. Pilot Operator Quick Reference

### Before handing to pilot users

- [ ] All secrets changed from dev defaults (section B1)
- [ ] `APP_ENV=production` set
- [ ] CORS origin set to actual frontend URL
- [ ] `./scripts/smoke-test.sh` passes 21/21
- [ ] Browser register + login + workspace creation works
- [ ] SMTP configured if approval notifications needed
- [ ] Cleanup cron scheduled (section F1)
- [ ] This checklist reviewed by someone who didn't write it

### First thing to check when something breaks

1. `docker compose ps` — any container restarting or unhealthy?
2. `docker compose logs <service> --tail 50` — look for Python tracebacks
3. `curl http://localhost:8080/healthz/live` — gateway reachable?
4. Browser hard-refresh (Ctrl+Shift+R) — stale JS cache?
5. `./scripts/smoke-test.sh` — which of 21 checks fail?
