# Contributing to Keviq Core

Thank you for your interest in contributing! This guide covers everything you need
to submit a high-quality pull request.

## Your First Contribution

New to the project? Start with the **[Your First Contribution Guide](docs/community/your-first-contribution.md)**.

It covers three setup paths (docs-only, frontend, full stack), how to choose an
issue, and what maintainers expect in a PR. Browse issues labeled
**[good first issue](https://github.com/Keviqai/keviq-core/labels/good%20first%20issue)**
to find beginner-friendly work.

## Before You Start

- **Check existing issues** — someone may already be working on the same thing.
- **Open an issue first** for large changes (new services, schema changes,
  architectural shifts). Small bug fixes and docs improvements can go straight to PR.
- Read the [Architecture Invariants](docs/02-architectural-invariants.md) so you
  understand the boundaries you must not break.

## Development Setup

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js | 22+ |
| pnpm | 9+ |
| Docker & Docker Compose | Latest stable |

### Clone and Bootstrap

```bash
git clone https://github.com/<your-username>/keviq-core.git
cd keviq-core
./scripts/bootstrap.sh        # installs deps, builds packages, starts Docker
```

### Verify Everything Works

```bash
python -m pytest tools/arch-test/ -v   # architecture tests (no Docker needed)
./scripts/smoke-test.sh                # smoke tests (requires Docker)
```

If both pass, your environment is ready.

## Code Style

### Python

- `snake_case` for functions and variables
- Type hints on every function signature
- Each function < 50 lines; each file < 300 lines
- API route handlers < 80 lines — put business logic in the service layer
- See [docs/CODING-RULES.md](docs/CODING-RULES.md) for full details

### TypeScript

- `camelCase` for functions and variables
- Strict mode enabled (`strict: true` in tsconfig)
- Each component < 150 lines; each file < 300 lines
- Frontend calls real API endpoints — no mock data in production code

## Testing

We use a four-level test pyramid. **All new code must include tests.**

### 1. Architecture Tests (910 tests, no Docker)

Enforce import boundaries, schema ownership, and structural invariants.

```bash
python -m pytest tools/arch-test/ -v
```

### 2. Unit Tests (636 tests, no Docker)

Located in `apps/*/tests/unit/`. Run a single service:

```bash
python -m pytest apps/orchestrator/tests/unit/ -v
```

### 3. Smoke Tests (21 checks, requires Docker)

End-to-end health and basic flow verification:

```bash
./scripts/smoke-test.sh
```

### 4. E2E Tests (requires running services)

Browser-level tests via Playwright:

```bash
npx playwright test
```

> **Note:** Integration tests for Slice 5 and Slice 6 features are expected to
> fail — those features are actively in development.

See [docs/TESTING-RULES.md](docs/TESTING-RULES.md) for testing standards.

## Commit Conventions

```
<type>(scope): <summary>
```

| Type | Use for |
|------|---------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `infra` | Docker, CI, migrations |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `refactor` | Code restructuring with no behavior change |

**Scope** examples: `auth`, `orchestrator`, `artifact`, `frontend`, `global`.

Keep the summary under 72 characters. Use the imperative mood ("add X", not "added X").

## Pull Request Process

1. **Branch from `master`**: `git checkout -b feat/my-feature`
2. **Make focused changes** — one feature or fix per PR.
3. **Run tests locally** — at minimum, architecture tests and relevant unit tests.
4. **Push and open a PR** against `master`.
5. **Fill in the PR template** — describe what changed, why, and how to test.
6. **Review turnaround** — maintainers aim to review within one week.

### PR Checklist (auto-included in template)

- [ ] Tests added/updated for new code
- [ ] Architecture tests pass (`python -m pytest tools/arch-test/ -v`)
- [ ] Documentation updated if APIs, config, or architecture changed
- [ ] Commit messages follow the convention above

## Architecture Constraints

This is a microservices monorepo with 15 backend services. Key rules:

- **Schema ownership** — each service owns exactly one PostgreSQL schema.
  Do not read or write another service's tables.
- **No cross-service imports** — services communicate via APIs and the
  outbox pattern (Redis Streams). Never import from another service's code.
- **No new services** without prior discussion and approval.
- **Architecture tests are gates** — PRs with architecture test failures
  will not be merged.

See [docs/02-architectural-invariants.md](docs/02-architectural-invariants.md)
for the full set of invariants.

## Getting Help

- **Questions or bugs?** [Open an issue](../../issues).
- **Architecture docs** are in `docs/` — start with `docs/00-product-vision.md`.
- Please follow our [Code of Conduct](CODE_OF_CONDUCT.md).
