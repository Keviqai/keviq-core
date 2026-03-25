# Your First Contribution

Welcome! This guide walks you through making your first contribution — whether
that's documentation, frontend code, or backend services.

---

## Step 1: Choose an Issue

Browse issues labeled **[good first issue](https://github.com/Keviqai/keviq-core/labels/good%20first%20issue)**.
These are scoped, have clear acceptance criteria, and don't require deep architecture knowledge.

Comment on the issue to let others know you're working on it.

---

## Step 2: Pick a Setup Path

### Path A: Docs only (no setup needed)

For markdown changes — no Docker, no Node, no Python.

```bash
git clone https://github.com/<your-username>/keviq-core.git
cd keviq-core
git checkout -b docs/my-change
# Edit files in docs/, README.md, or CONTRIBUTING.md
git add docs/my-file.md
git commit -m "docs(guide): add example for X"
git push -u origin docs/my-change
# Open a PR on GitHub
```

### Path B: Frontend only (Node + pnpm)

For React component changes — no Docker needed. The frontend dev server runs
standalone, but API calls require either the backend stack or setting a gateway URL.

```bash
git clone https://github.com/<your-username>/keviq-core.git
cd keviq-core
pnpm install
cd apps/web && pnpm dev          # http://localhost:3000
# Edit components in apps/web/src/
pnpm typecheck                   # Verify types
pnpm build                       # Verify build
```

> **Note:** Without Docker, API calls will fail (the frontend proxies to the API
> gateway). For pure UI/component work this is fine — just ignore network errors.
> If you need a working API, start the full stack with Path C instead.

### Path C: Full stack (Docker required)

For backend service changes — requires Docker, Python 3.12, Node 22, pnpm.

```bash
git clone https://github.com/<your-username>/keviq-core.git
cd keviq-core
cp infra/docker/.env.example infra/docker/.env.local
./scripts/bootstrap.sh           # ~60 seconds: Postgres, Redis, 15 services
python -m pytest tools/arch-test/ -v   # Architecture tests
./scripts/smoke-test.sh                # 21 end-to-end checks
```

---

## Step 3: Verify Before Opening a PR

Run only what applies to your change:

| Change type | Run this | Docker needed? |
|-------------|----------|----------------|
| Docs only | Nothing — markdown is reviewed by eye | No |
| Frontend | `pnpm typecheck && pnpm build` | No |
| Backend service | `python -m pytest tools/arch-test/ -v` | No |
| Backend + DB schema | `./scripts/bootstrap.sh && ./scripts/smoke-test.sh` | Yes |

---

## Step 4: Keep Scope Small

Good first PRs:
- Address **one issue**, not multiple
- Change fewer than **200 lines**
- Include tests for code changes (not needed for docs)

If an issue looks too large, split it — open follow-up issues for remaining work.

---

## Step 5: Commit and Open a PR

### Commit message format

```
<type>(scope): <summary>
```

| Type | When |
|------|------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Restructuring, no behavior change |
| `infra` | CI, Docker, tooling |

**Scope** examples: `auth`, `orchestrator`, `artifact`, `frontend`, `global`.

### PR expectations

When you open a PR, fill in the template:
- What changed and why
- Link to the issue (`Closes #N`)
- How you tested it
- Check the boxes that apply

Maintainers aim to review within **one week**.

---

## Where to Start in the Codebase

### Easiest areas (start here)

| Area | What to work on | Path |
|------|----------------|------|
| Documentation | Fix typos, add guides, improve examples | `docs/`, `README.md` |
| Health endpoints | Add type hints, improve responses | `apps/*/src/api/routes.py` |
| Frontend pages | UI components, layout fixes | `apps/web/src/app/` |

### Medium difficulty

| Area | What to work on | Path |
|------|----------------|------|
| Workspace service | Membership, isolation | `apps/workspace-service/` |
| Auth service | JWT, registration | `apps/auth-service/` |
| Notification service | Delivery tracking, retry logic | `apps/notification-service/` |

### Harder (avoid for first contribution)

| Area | Why it's complex |
|------|-----------------|
| Orchestrator | State machines with retries, timeouts, cancellation |
| Agent runtime | Model-call / tool-call loop with guardrails |
| Event store | Append-only log, SSE streaming |
| Artifact service | Provenance chains, lineage cycle detection, taint propagation |
| Schema migrations | Per-service Alembic migrations; each must be reversible (up + down) |

---

## Getting Help

| Need | Where |
|------|-------|
| Architecture overview | [architecture-overview.md](../architecture-overview.md) |
| Coding standards | [CODING-RULES.md](../CODING-RULES.md) |
| Testing standards | [TESTING-RULES.md](../TESTING-RULES.md) |
| API contracts | [07-api-contracts.md](../07-api-contracts.md) |
| Blocked or confused | [Open an issue](https://github.com/Keviqai/keviq-core/issues) describing where you're stuck |

---

## After Your First PR

Once merged:
1. Read the [Architecture Overview](../architecture-overview.md) to understand all 15 services
2. Browse issues labeled **[help wanted](https://github.com/Keviqai/keviq-core/labels/help%20wanted)** for larger tasks
3. Check the [Roadmap](../../ROADMAP.md) to see what's coming next
