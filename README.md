# Keviq Core

AI-native work operating system. Orchestrate tasks, run agents, manage artifacts
with full provenance tracking — all in a multi-tenant, permission-aware platform.

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Docker Compose v2)
- [Node.js 22+](https://nodejs.org/) and [pnpm](https://pnpm.io/) (for frontend dev)
- [curl](https://curl.se/) and [Python 3](https://www.python.org/) (for smoke tests)
- ~8 GB free RAM (16 GB recommended)

### 1. Clone and configure

```bash
git clone https://github.com/Keviqai/keviq-core.git && cd keviq-core
cp infra/docker/.env.example infra/docker/.env.local
```

The default configuration works for local development. For production,
edit `.env.local` — see [Production Deployment Checklist](docs/ops/production-deployment-checklist.md).

### 2. Bootstrap (start infra + run migrations + start services)

```bash
./scripts/bootstrap.sh
```

This will:
- Start PostgreSQL and Redis
- Run database migrations for all 13 services (creates tables in 13 schemas)
- Start all 18 containers (15 backend services + PostgreSQL + Redis + frontend)
- Verify service health

### 3. Create your first user and log in

```bash
# Register
curl -X POST http://localhost:8080/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme123","display_name":"Admin"}'

# Open the frontend
open http://localhost:3000
```

Log in with `admin@example.com` / `changeme123`.

### Verify everything works

```bash
./scripts/smoke-test.sh
```

This runs automated checks against: infrastructure, service health, database
tables, auth flow (register + login), workspace creation, and frontend serving.

### Operations & deployment

- **Production deployment:** See [docs/ops/production-deployment-checklist.md](docs/ops/production-deployment-checklist.md)
- **Clean-boot verification:** `./scripts/clean-boot-test.sh` (tears down everything, reboots from zero, runs smoke)
- **Observability stack:** See [docs/ops/observability.md](docs/ops/observability.md)

## Architecture

Keviq Core is a microservices platform with 15 backend services:

| Layer | Services |
|---|---|
| **API Surface** | api-gateway (auth + routing), sse-gateway |
| **Control** | auth-service, policy-service, workspace-service |
| **Domain** | orchestrator, agent-runtime, artifact-service, execution-service |
| **Infrastructure** | event-store, model-gateway, audit-service, notification-service, secret-broker, telemetry-service |
| **Frontend** | Next.js 15 + React 19 |

Each service owns its own PostgreSQL schema and communicates via the outbox
pattern + Redis Streams event bus.

See [docs/docs-index.md](docs/docs-index.md) for the full architecture
documentation (18 specification documents).

## Development

### Service ports (local dev)

| Service | Port |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| API Gateway | http://localhost:8080 |
| PostgreSQL | localhost:5434 |
| Redis | localhost:6379 |

Individual services are accessible on ports 8001-8015. See
`infra/docker/docker-compose.local.yml` for the full port map.

### Common commands

```bash
# Full bootstrap (first time or after migration changes)
./scripts/bootstrap.sh

# Run migrations only (infra must be up)
./scripts/bootstrap.sh migrate

# Start services only (migrations must have run)
./scripts/bootstrap.sh up

# Run smoke tests
./scripts/smoke-test.sh

# View logs
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  --env-file .env.local logs -f <service-name>

# Stop everything
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  --env-file .env.local down

# Run architecture tests
python -m pytest tools/arch-test/ -v
```

### Frontend development

```bash
cd apps/web
pnpm install
pnpm dev   # starts Next.js dev server on port 3000
```

### Project structure

```
keviq-core/
  apps/              # 15 backend services + 1 frontend
  packages/          # 14 shared packages (api-client, domain-types, etc.)
  tools/             # arch-test, codegen, db-migrate
  infra/docker/      # Docker Compose, env files, init SQL
  scripts/           # bootstrap.sh, smoke-test.sh
  docs/              # 18 architecture docs + governance
```

## Current Status

| Aspect | Status |
|---|---|
| Core platform (14/15 services domain-functional) | Stable |
| User journeys (21/21 verified) | Complete |
| Frontend (21 pages, data-driven) | Complete |
| Test coverage (636 unit + 910 arch tests) | Passing |

14 of 15 backend services are domain-functional. sse-gateway serves health
and metrics only (SSE is served by event-store). All services expose `/metrics`
endpoints for Prometheus scraping.

## External Dependencies

- **LLM API**: Any OpenAI-compatible endpoint (OpenAI, Azure, vLLM, Ollama).
  Configure via `MODEL_GW_PROVIDER_*` env vars. Not required for basic
  task/artifact management.
- **No GPU required** — model-gateway is a proxy, not an inference engine.
- **No cloud services required** — runs fully local with Docker Compose.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development standards and pull request process.

## License

MIT — see [LICENSE](LICENSE).
