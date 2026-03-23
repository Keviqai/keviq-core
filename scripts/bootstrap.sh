#!/usr/bin/env bash
set -euo pipefail

# ── Keviq Core Bootstrap Script ──────────────────────────────────
#
# Brings up infrastructure, runs all database migrations, then
# starts application services. Run this once after cloning, or
# whenever migrations are added.
#
# Usage:
#   ./scripts/bootstrap.sh          # full bootstrap
#   ./scripts/bootstrap.sh migrate  # run migrations only (infra must be up)
#   ./scripts/bootstrap.sh up       # start services only (migrations must have run)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/infra/docker"

# Check .env.local exists (new clones need to copy from .env.example)
if [ ! -f "$COMPOSE_DIR/.env.local" ]; then
  if [ -f "$COMPOSE_DIR/.env.example" ]; then
    echo "[WARN]  .env.local not found — copying from .env.example"
    cp "$COMPOSE_DIR/.env.example" "$COMPOSE_DIR/.env.local"
  else
    echo "[FAIL]  $COMPOSE_DIR/.env.local not found and no .env.example to copy."
    echo "        Create .env.local with required env vars. See README.md."
    exit 1
  fi
fi

# Compose command with project files
DC="docker compose -f $COMPOSE_DIR/docker-compose.yml -f $COMPOSE_DIR/docker-compose.local.yml --env-file $COMPOSE_DIR/.env.local"

# Superuser DB URL for running migrations (needs CREATE privilege)
SUPERUSER_DB_URL="postgresql://superuser:superpassword@postgres/mona_os"

# ── Colors ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ── Step 1: Start Infrastructure ─────────────────────────────────
start_infra() {
  info "Starting PostgreSQL and Redis..."
  $DC up -d postgres redis

  info "Waiting for PostgreSQL to be healthy..."
  local retries=30
  while [ $retries -gt 0 ]; do
    if $DC exec -T postgres pg_isready -U superuser -d mona_os > /dev/null 2>&1; then
      ok "PostgreSQL is ready"
      return
    fi
    retries=$((retries - 1))
    sleep 1
  done
  fail "PostgreSQL did not become ready in 30 seconds"
}

# ── Step 2: Run Migrations ───────────────────────────────────────
#
# Each service has its own Alembic setup targeting its own schema.
# We run migrations using superuser credentials (via env var override)
# to ensure CREATE TABLE permissions work for all schemas.

# Service → env var name for DB URL
declare -A MIGRATION_SERVICES=(
  ["auth-service"]="AUTH_DB_URL"
  ["workspace-service"]="WORKSPACE_DB_URL"
  ["policy-service"]="POLICY_DB_URL"
  ["orchestrator"]="ORCHESTRATOR_DB_URL"
  ["agent-runtime"]="AGENT_RUNTIME_DB_URL"
  ["artifact-service"]="ARTIFACT_DB_URL"
  ["execution-service"]="EXECUTION_DB_URL"
  ["event-store"]="EVENT_STORE_DB_URL"
  ["model-gateway"]="MODEL_GW_DB_URL"
  ["audit-service"]="AUDIT_DB_URL"
  ["notification-service"]="NOTIFICATION_DB_URL"
  ["secret-broker"]="SECRET_DB_URL"
  ["telemetry-service"]="TELEMETRY_DB_URL"
)

# Order matters: control services first, then domain services
MIGRATION_ORDER=(
  "auth-service"
  "workspace-service"
  "policy-service"
  "orchestrator"
  "agent-runtime"
  "artifact-service"
  "execution-service"
  "event-store"
  "model-gateway"
  "audit-service"
  "notification-service"
  "secret-broker"
  "telemetry-service"
)

run_migrations() {
  info "Running database migrations for ${#MIGRATION_ORDER[@]} services..."
  echo ""

  local failed=0
  for svc in "${MIGRATION_ORDER[@]}"; do
    local env_var="${MIGRATION_SERVICES[$svc]}"
    printf "  %-25s" "$svc"

    if $DC run --rm --no-deps \
      -e "${env_var}=${SUPERUSER_DB_URL}" \
      "$svc" \
      alembic upgrade head > /dev/null 2>&1; then
      echo -e "${GREEN}OK${NC}"
    else
      echo -e "${RED}FAILED${NC}"
      # Show error details
      $DC run --rm --no-deps \
        -e "${env_var}=${SUPERUSER_DB_URL}" \
        "$svc" \
        alembic upgrade head 2>&1 | tail -5 || true
      failed=$((failed + 1))
    fi
  done

  echo ""
  if [ $failed -gt 0 ]; then
    fail "$failed migration(s) failed"
  fi
  ok "All migrations complete"
}

# ── Step 3: Start Application Services ───────────────────────────
start_services() {
  info "Starting all application services..."
  $DC up -d
  ok "All services started"
}

# ── Step 4: Health Check ─────────────────────────────────────────
check_health() {
  info "Checking service health..."
  echo ""

  local healthy=0
  local unhealthy=0

  # Key services to check (host ports from docker-compose.local.yml)
  declare -A HEALTH_ENDPOINTS=(
    ["api-gateway"]="http://localhost:8080/healthz/live"
    ["auth-service"]="http://localhost:8007/healthz/live"
    ["workspace-service"]="http://localhost:8008/healthz/live"
    ["orchestrator"]="http://localhost:8001/healthz/live"
    ["artifact-service"]="http://localhost:8003/healthz/live"
    ["event-store"]="http://localhost:8013/healthz/live"
  )

  # Wait a few seconds for services to start
  sleep 5

  for svc in "${!HEALTH_ENDPOINTS[@]}"; do
    local url="${HEALTH_ENDPOINTS[$svc]}"
    printf "  %-25s" "$svc"

    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
      echo -e "${GREEN}HEALTHY${NC}"
      healthy=$((healthy + 1))
    else
      echo -e "${RED}UNHEALTHY${NC}"
      unhealthy=$((unhealthy + 1))
    fi
  done

  echo ""
  info "$healthy healthy, $unhealthy unhealthy"

  if [ $unhealthy -gt 0 ]; then
    warn "Some services are unhealthy. Check logs with: docker compose logs <service>"
    return 1
  fi
  ok "All key services are healthy"
}

# ── Main ─────────────────────────────────────────────────────────
main() {
  local mode="${1:-full}"

  echo ""
  echo "═══════════════════════════════════════════════════════════"
  echo "  Keviq Core Bootstrap"
  echo "═══════════════════════════════════════════════════════════"
  echo ""

  case "$mode" in
    full)
      start_infra
      run_migrations
      start_services
      check_health || true
      ;;
    migrate)
      run_migrations
      ;;
    up)
      start_services
      check_health || true
      ;;
    *)
      echo "Usage: $0 [full|migrate|up]"
      echo ""
      echo "  full     Full bootstrap: infra + migrations + services (default)"
      echo "  migrate  Run migrations only (infra must be up)"
      echo "  up       Start services only (migrations must have run)"
      exit 1
      ;;
  esac

  echo ""
  echo "═══════════════════════════════════════════════════════════"
  ok "Bootstrap complete"
  echo ""
  echo "  Frontend:    http://localhost:3000"
  echo "  API Gateway: http://localhost:8080"
  echo "  PostgreSQL:  localhost:5434"
  echo ""
  echo "  Next steps:"
  echo "    1. Register: curl -X POST http://localhost:8080/v1/auth/register \\"
  echo "         -H 'Content-Type: application/json' \\"
  echo "         -d '{\"email\":\"admin@example.com\",\"password\":\"changeme123\",\"display_name\":\"Admin\"}'"
  echo "    2. Open http://localhost:3000 and log in"
  echo "    3. Run smoke tests: ./scripts/smoke-test.sh"
  echo ""
}

main "$@"
