#!/usr/bin/env bash
# ═══════════════════════════════════════════════
# PRE-COMMIT GATE
# Blocks commit if smoke test hasn't passed recently.
# Called by Claude Code hook (PreToolUse).
# ═══════════════════════════════════════════════

GATE_FILE=/tmp/keviq-pre-commit-pass
MAX_AGE=600  # 10 minutes

# Check gate file exists
if [ ! -f "$GATE_FILE" ]; then
  echo "═══════════════════════════════════════════════"
  echo "BLOCKED: Smoke tests have not been run."
  echo ""
  echo "Run: ./scripts/smoke-test.sh"
  echo "Or:  python -m pytest tools/arch-test/ -v"
  echo "Then try commit again."
  echo "═══════════════════════════════════════════════"
  exit 1
fi

# Check gate file is fresh
if [ "$(uname)" = "Darwin" ]; then
  GATE_AGE=$(( $(date +%s) - $(stat -f %m "$GATE_FILE") ))
else
  GATE_AGE=$(( $(date +%s) - $(stat -c %Y "$GATE_FILE" 2>/dev/null || echo 0) ))
fi

if [ "$GATE_AGE" -gt "$MAX_AGE" ]; then
  echo "═══════════════════════════════════════════════"
  echo "BLOCKED: Test results too old (${GATE_AGE}s > ${MAX_AGE}s)."
  echo ""
  echo "Run again: ./scripts/smoke-test.sh"
  echo "═══════════════════════════════════════════════"
  rm -f "$GATE_FILE"
  exit 1
fi

echo "PASS: Tests recent (${GATE_AGE}s ago). Commit allowed."
rm -f "$GATE_FILE"  # single-use
exit 0
