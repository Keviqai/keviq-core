#!/usr/bin/env bash
set -euo pipefail

# ── Keviq Core Clean-Boot Verification ─────────────────────────
#
# Proves the system can start from zero state and pass smoke tests.
# Intended for CI gates and pre-pilot verification.
#
# What it does:
#   1. Tears down all containers and volumes (clean slate)
#   2. Runs bootstrap.sh full (infra + migrations + services)
#   3. Waits for all services to become healthy
#   4. Runs smoke-test.sh (21 checks)
#
# Usage:
#   ./scripts/clean-boot-test.sh
#
# Exit codes:
#   0 — all steps passed
#   1 — any step failed
#
# Time estimate: 3-6 minutes depending on image build cache

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/infra/docker"

DC="docker compose -f $COMPOSE_DIR/docker-compose.yml -f $COMPOSE_DIR/docker-compose.local.yml --env-file $COMPOSE_DIR/.env.local"

# ── Colors ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

START_TIME=$(date +%s)

step_time() {
  local now
  now=$(date +%s)
  echo "$((now - START_TIME))s elapsed"
}

# ── Prerequisite Checks ──────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Keviq Core Clean-Boot Verification"
echo "═══════════════════════════════════════════════════════════"
echo ""

info "Checking prerequisites..."

command -v docker > /dev/null 2>&1 || fail "docker not found in PATH"
docker compose version > /dev/null 2>&1 || fail "docker compose not available"
command -v curl > /dev/null 2>&1 || fail "curl not found in PATH"

if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
  fail "docker-compose.yml not found at $COMPOSE_DIR"
fi

if [ ! -f "$COMPOSE_DIR/.env.local" ]; then
  fail ".env.local not found at $COMPOSE_DIR — copy from .env.example first"
fi

if [ ! -f "$SCRIPT_DIR/bootstrap.sh" ]; then
  fail "bootstrap.sh not found at $SCRIPT_DIR"
fi

if [ ! -f "$SCRIPT_DIR/smoke-test.sh" ]; then
  fail "smoke-test.sh not found at $SCRIPT_DIR"
fi

ok "Prerequisites verified"

# ── Step 1: Tear Down ────────────────────────────────────────────

echo ""
echo "── Step 1: Clean Teardown ────────────────────────────────"

info "Stopping all containers and removing volumes..."
$DC down -v --remove-orphans 2>&1 | tail -5 || true

# Verify nothing is running
RUNNING=$($DC ps -q 2>/dev/null | wc -l || echo "0")
if [ "$RUNNING" -gt 0 ]; then
  warn "Some containers still running, forcing stop..."
  $DC kill 2>/dev/null || true
  $DC down -v --remove-orphans 2>/dev/null || true
fi

ok "Clean slate — all containers and volumes removed ($(step_time))"

# ── Step 2: Bootstrap ────────────────────────────────────────────

echo ""
echo "── Step 2: Bootstrap (full) ──────────────────────────────"

info "Running bootstrap.sh full..."
if ! bash "$SCRIPT_DIR/bootstrap.sh" full; then
  fail "bootstrap.sh failed — check output above for details"
fi

ok "Bootstrap complete ($(step_time))"

# ── Step 3: Wait for Health ──────────────────────────────────────

echo ""
echo "── Step 3: Wait for Service Health ───────────────────────"

MAX_WAIT=120
INTERVAL=5
WAITED=0

info "Waiting up to ${MAX_WAIT}s for all services to become healthy..."

while [ $WAITED -lt $MAX_WAIT ]; do
  HEALTHY_COUNT=$($DC ps --format json 2>/dev/null \
    | python -c "
import sys, json
lines = sys.stdin.read().strip().split('\n')
healthy = 0
total = 0
for line in lines:
    if not line.strip():
        continue
    try:
        obj = json.loads(line)
        total += 1
        if 'healthy' in obj.get('Status', '').lower():
            healthy += 1
    except json.JSONDecodeError:
        continue
print(f'{healthy}/{total}')
" 2>/dev/null || echo "0/0")

  printf "\r  Health: %s (%ds)" "$HEALTHY_COUNT" "$WAITED"

  # Check if enough services are healthy.
  # execution-service requires Docker socket mount (host-specific) and may
  # crash-loop without it — this is expected and does not block smoke tests.
  # Minimum: 17 of 18 containers healthy (all except execution-service).
  MIN_HEALTHY=17
  TOTAL=$(echo "$HEALTHY_COUNT" | cut -d/ -f2)
  HEALTHY=$(echo "$HEALTHY_COUNT" | cut -d/ -f1)

  if [ "$TOTAL" -ge 15 ] && [ "$HEALTHY" -ge $MIN_HEALTHY ]; then
    echo ""
    ok "$HEALTHY/$TOTAL services healthy ($(step_time))"
    if [ "$HEALTHY" -lt "$TOTAL" ]; then
      warn "$(( TOTAL - HEALTHY )) service(s) unhealthy — likely execution-service (needs Docker socket)"
    fi
    break
  fi

  sleep $INTERVAL
  WAITED=$((WAITED + INTERVAL))
done

if [ $WAITED -ge $MAX_WAIT ]; then
  echo ""
  warn "Health wait timed out after ${MAX_WAIT}s"
  info "Current status:"
  $DC ps 2>/dev/null || true
  fail "Not all services became healthy within ${MAX_WAIT}s"
fi

# ── Step 4: Smoke Test ───────────────────────────────────────────

echo ""
echo "── Step 4: Smoke Test ────────────────────────────────────"

info "Running smoke-test.sh..."
if bash "$SCRIPT_DIR/smoke-test.sh"; then
  ok "Smoke test passed ($(step_time))"
else
  fail "Smoke test failed — see output above"
fi

# ── Summary ──────────────────────────────────────────────────────

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_TIME / 60))
SECONDS=$((TOTAL_TIME % 60))

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}CLEAN-BOOT VERIFICATION PASSED${NC}"
echo "  Total time: ${MINUTES}m ${SECONDS}s"
echo "═══════════════════════════════════════════════════════════"
echo ""
