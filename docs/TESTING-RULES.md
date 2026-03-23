# Testing Rules — Keviq Core

> Referenced from CLAUDE.md. Claude Code reads when testing details are needed.

## Test Pyramid — 7 Layers

| Layer | Type | Tool | Minimum | When |
|-------|------|------|---------|------|
| 1 | Unit Test | pytest / vitest | 5-10/module | Every commit |
| 2 | Integration Test | pytest + httpx | 2-3/endpoint | Every commit |
| 3 | Architecture Test | pytest (tools/arch-test/) | Per invariant | Every PR |
| 4 | Smoke Test (API) | curl (scripts/smoke-test.sh) | 1/user flow | Every PR |
| 5 | UI Test (automated) | Playwright | 1/user journey | Every PR with UI changes |
| 6 | Concurrent Test | k6 | 1/write endpoint | Every PR with write endpoints |
| 7 | Manual Test | Browser | 1/user journey | Every slice |

## Architecture Tests (Keviq Core-specific)

Keviq Core has 945+ architecture tests in `tools/arch-test/` that enforce:
- Service boundary invariants (S1-S5)
- Protection points (PP1-PP10)
- Slice contracts and guard tests
- Container hardening rules

**Run:** `python -m pytest tools/arch-test/ -v`

These are mandatory gates — no PR merges with architecture test failures.

## Writing Tests
- Test behavior, not implementation
- Each test independent — no shared state, no order dependency
- 60% happy path, 40% error path
- Max 3 mocks per test — more means code is too coupled
- Test data with meaningful names (no "test1", "abc123")
- Each test function < 30 lines

## ABSOLUTE RULE: NO BYPASSING TESTS
1. Do NOT skip tests because "they take too long"
2. Do NOT write fake tests (assert True, empty body)
3. Do NOT comment out failing tests
4. Do NOT use @skip without a tracked ticket
5. Do NOT report "done" if tests haven't run and passed

**When bypass needed:** STOP -> REPORT (which test, why, proposed fix) -> WAIT for user decision.

## Smoke Test
- Located at `scripts/smoke-test.sh`
- Checks: infrastructure, service health, DB tables, auth flow, workspace flow, frontend
- Must pass before any commit (enforced by pre-commit gate)
- Should support selective running: `./smoke-test.sh boot`, `./smoke-test.sh auth`, `./smoke-test.sh all`

## UI Tests — Playwright (mandatory for UI changes)

### Setup
```bash
cd apps/web
pnpm add -D @playwright/test
npx playwright install --with-deps chromium
```

### Structure
```
e2e/
  playwright.config.ts
  tests/
    auth.spec.ts          # register + login flow
    workspace.spec.ts     # workspace creation
    task-brief.spec.ts    # Q1: task creation via brief
```

### Cases MUST test via browser
- Form submission + validation display
- Navigation flow (register → login → dashboard)
- Auth state persist after page refresh
- Error display (API error → user-friendly message)
- CRUD basics (create → see in list → click → detail)
- Loading states (click → loading indicator → result)

### Integration with smoke-test.sh
```bash
test_ui() {
  cd e2e && npx playwright test --reporter=line
  [ $? -ne 0 ] && fail 'UI tests'
  pass 'UI tests'
}
```

## Concurrent Tests — k6 (mandatory for write endpoints)

### Risk-based tiers

| Tier | Type | When | Required? |
|------|------|------|-----------|
| 1 | Race condition (5-10 VUs) | PR has write endpoint with unique constraint | Yes |
| 2 | Concurrent CRUD (5-10 VUs) | Slice with multi-user write | Yes |
| 3 | Load test (ramp to 50 VUs) | Gate Review or performance-sensitive area | Recommended |
| 4 | Stress test (100+ VUs) | Before release | Project-dependent |

### Structure
```
e2e/concurrent/
  register-race.k6.js      # race condition: same email
  update-race.k6.js         # concurrent update same resource
  load-basic.k6.js          # ramp 10→50 VUs
```

### Example: Race condition test
```javascript
// e2e/concurrent/register-race.k6.js
import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 10, iterations: 10 };

export default function () {
  const res = http.post('http://localhost:8080/v1/auth/register',
    JSON.stringify({ email: 'race@test.com', password: 'Test1234!' }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(res, {
    'status is 201 or 409': (r) => r.status === 201 || r.status === 409,
    'no 500 errors': (r) => r.status !== 500,
  });
}
// Expected: 1x 201 + 9x 409. If 2x 201 = DUPLICATE BUG.
```

### Thresholds
```javascript
thresholds: {
  http_req_duration: ['p(95)<500'],  // 95% requests < 500ms
  http_req_failed: ['rate<0.01'],    // < 1% errors
}
```

## Multi-Agent Review (Keviq Core-specific)
After every coding task, run 4 review agents in parallel:
1. **Security Review** — injection, XSS, CSRF, secrets, OWASP top 10
2. **Code Quality** — naming, SOLID, DRY, readability
3. **Bug Detection** — edge cases, null/undefined, race conditions
4. **Performance** — N+1 queries, memory leaks, bundle size

Fix HIGH/CRITICAL findings before reporting done.
