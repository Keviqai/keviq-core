#!/usr/bin/env bash
set -euo pipefail

# ── Keviq Core Smoke Test ────────────────────────────────────────
#
# Verifies that the system is bootable and core user journeys work.
# Run after bootstrap.sh to confirm the system is operational.
#
# Usage:
#   ./scripts/smoke-test.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/infra/docker"

# Compose command prefix
DC="docker compose -f $COMPOSE_DIR/docker-compose.yml -f $COMPOSE_DIR/docker-compose.local.yml --env-file $COMPOSE_DIR/.env.local"

API="http://localhost:8080"
PASSED=0
FAILED=0
TOTAL=0

# ── Colors ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

check() {
  local name="$1"
  shift
  TOTAL=$((TOTAL + 1))
  printf "  %-50s" "$name"
  if "$@" > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}FAIL${NC}"
    FAILED=$((FAILED + 1))
  fi
}

check_status() {
  local name="$1"
  local expected_status="$2"
  local url="$3"
  shift 3
  TOTAL=$((TOTAL + 1))
  printf "  %-50s" "$name"
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "$expected_status" ]; then
    echo -e "${GREEN}PASS${NC} (${status})"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}FAIL${NC} (got ${status}, expected ${expected_status})"
    FAILED=$((FAILED + 1))
  fi
}

# ── Infrastructure Checks ───────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Keviq Core Smoke Test"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "── Infrastructure ──────────────────────────────────────"

check "PostgreSQL accepting connections" \
  $DC exec -T postgres pg_isready -U superuser -d mona_os

check "Redis accepting connections" \
  $DC exec -T redis redis-cli ping

# ── Service Health Checks ────────────────────────────────────

echo ""
echo "── Service Health ──────────────────────────────────────"

check_status "api-gateway /healthz/live" "200" "$API/healthz/live"
check_status "auth-service (via gateway info)" "200" "http://localhost:8007/healthz/live"
check_status "orchestrator health" "200" "http://localhost:8001/healthz/live"
check_status "artifact-service health" "200" "http://localhost:8003/healthz/live"
check_status "event-store health" "200" "http://localhost:8013/healthz/live"
check_status "workspace-service health" "200" "http://localhost:8008/healthz/live"

# ── Database Tables Exist ────────────────────────────────────

echo ""
echo "── Database Tables ─────────────────────────────────────"

db_table_exists() {
  # NOTE: $schema and $table are trusted hardcoded literals from call sites below
  local schema="$1"
  local table="$2"
  $DC exec -T postgres psql -U superuser -d mona_os -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_schema='$schema' AND table_name='$table'" \
    2>/dev/null | grep -q "1"
}

check "identity_core.users table exists" db_table_exists identity_core users
check "workspace_core.workspaces table exists" db_table_exists workspace_core workspaces
check "orchestrator_core.tasks table exists" db_table_exists orchestrator_core tasks
check "artifact_core.artifacts table exists" db_table_exists artifact_core artifacts
check "event_core.events table exists" db_table_exists event_core events
check "execution_core.sandboxes table exists" db_table_exists execution_core sandboxes

# ── Auth Flow ────────────────────────────────────────────────

echo ""
echo "── Auth Journey ────────────────────────────────────────"

# Generate unique email to avoid conflicts on re-runs
SMOKE_EMAIL="smoke-$(date +%s)@example.com"
SMOKE_PASS="smoketest1234"

# Register
REGISTER_RESP=$(curl -s --max-time 10 \
  -X POST "$API/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${SMOKE_EMAIL}\",\"password\":\"${SMOKE_PASS}\",\"display_name\":\"Smoke Test\"}" \
  2>/dev/null || echo "{}")

SMOKE_TOKEN=$(echo "$REGISTER_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

TOTAL=$((TOTAL + 1))
printf "  %-50s" "Register new user"
if [ -n "$SMOKE_TOKEN" ]; then
  echo -e "${GREEN}PASS${NC}"
  PASSED=$((PASSED + 1))
else
  echo -e "${RED}FAIL${NC}"
  FAILED=$((FAILED + 1))
fi

# Login
LOGIN_RESP=$(curl -s --max-time 10 \
  -X POST "$API/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${SMOKE_EMAIL}\",\"password\":\"${SMOKE_PASS}\"}" \
  2>/dev/null || echo "{}")

LOGIN_TOKEN=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")

TOTAL=$((TOTAL + 1))
printf "  %-50s" "Login with registered user"
if [ -n "$LOGIN_TOKEN" ]; then
  echo -e "${GREEN}PASS${NC}"
  PASSED=$((PASSED + 1))
  SMOKE_TOKEN="$LOGIN_TOKEN"  # use fresh token
else
  echo -e "${RED}FAIL${NC}"
  FAILED=$((FAILED + 1))
fi

# Get profile
check_status "GET /v1/auth/me returns 200" "200" "$API/v1/auth/me" \
  -H "Authorization: Bearer $SMOKE_TOKEN"

# ── Workspace Flow (if auth passed) ─────────────────────────

echo ""
echo "── Workspace Journey ───────────────────────────────────"

if [ -n "$SMOKE_TOKEN" ]; then
  WS_SLUG="smoke-ws-$(date +%s)"
  WS_RESP=$(curl -s --max-time 10 \
    -X POST "$API/v1/workspaces" \
    -H "Authorization: Bearer $SMOKE_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"display_name\":\"Smoke Workspace\",\"slug\":\"${WS_SLUG}\"}" \
    2>/dev/null || echo "{}")

  WS_ID=$(echo "$WS_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

  TOTAL=$((TOTAL + 1))
  printf "  %-50s" "Create workspace"
  if [ -n "$WS_ID" ]; then
    echo -e "${GREEN}PASS${NC}"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}FAIL${NC}"
    FAILED=$((FAILED + 1))
  fi

  if [ -n "$WS_ID" ]; then
    check_status "List workspace artifacts" "200" \
      "$API/v1/workspaces/$WS_ID/artifacts" \
      -H "Authorization: Bearer $SMOKE_TOKEN"

    check_status "List workspace tasks" "200" \
      "$API/v1/tasks?workspace_id=$WS_ID" \
      -H "Authorization: Bearer $SMOKE_TOKEN"
  else
    warn "Skipping workspace-dependent checks (workspace creation failed)"
  fi
else
  warn "Skipping workspace checks (auth failed)"
fi

# ── Frontend ─────────────────────────────────────────────────

echo ""
echo "── Frontend ────────────────────────────────────────────"

check_status "Next.js frontend serves login page" "200" "http://localhost:3000/login"

# ── Summary ──────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
if [ $FAILED -eq 0 ]; then
  echo -e "  ${GREEN}ALL $TOTAL CHECKS PASSED${NC}"
else
  echo -e "  ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC} (of $TOTAL)"
fi
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ $FAILED -gt 0 ]; then
  exit 1
fi
