# Coding Rules — Keviq Core

> Referenced from CLAUDE.md. Claude Code reads when coding details are needed.

## Architecture: Microservices (not monolith)

Keviq Core uses 15 backend services, each owning its own PostgreSQL schema.
This is an established architecture — do NOT merge services or create new ones
without explicit approval.

**Service boundary rules:**
- Each service owns exactly one schema (S1 invariant)
- Services communicate via outbox pattern + Redis Streams
- No direct DB queries across schemas
- Use `packages/internal-auth` for service-to-service auth

## File Length Limits

| Type | Max | Recommended | When exceeded |
|------|-----|-------------|---------------|
| Python .py | 300 lines | 150-200 | Split into sub-modules |
| React .tsx | 300 lines | 150-200 | Split into component/hook/utils |
| Test file | 400 lines | 200-300 | Split by feature group |
| Config | 150 lines | 100 | Split include/extend |

**Rules:**
- Writing new file exceeding 200 lines -> STOP, split immediately
- File already > 250 lines needs new logic -> CREATE new file, import
- File > 300 lines -> tech debt, split in separate refactor session

## Function/Component Limits
- 1 function: max 50 lines
- 1 React component: max 150 lines (including JSX)
- 1 API route handler: max 80 lines -> business logic in service layer
- 1 test function: max 30 lines

## Error Handling Patterns

Every endpoint must handle at minimum these 4 error types:

| Error Type | HTTP Status | When |
|-----------|-------------|------|
| Validation error | 400 | Invalid input, missing required fields |
| Auth error | 401 / 403 | Missing token, expired token, insufficient permissions |
| Not found | 404 | Entity doesn't exist or wrong workspace scope |
| Internal error | 500 | Unexpected failures (logged, never leaked to client) |

**Backend pattern:**
```python
@router.post("/internal/v1/entities")
async def create_entity(body: CreateRequest, db=Depends(_get_db)):
    try:
        result = service.create(db, body)
    except DomainValidationError as e:
        raise HTTPException(400, str(e))
    except DomainError as e:
        raise HTTPException(404, str(e))
    return result
```

**Frontend pattern:**
- Show user-friendly error message, never raw "500 Internal Server Error"
- Use error boundaries for unexpected failures
- Use `isError` + `error` from TanStack Query hooks

## Python Standards (Backend)
- snake_case for functions, variables, modules
- Type hints mandatory on all function signatures
- Each service follows hexagonal architecture: `api/`, `application/`, `domain/`, `infrastructure/`
- Business logic in `application/services.py`, not in route handlers
- Use `from __future__ import annotations` for forward references
- Structured logging (no `print()` debugging)

## TypeScript Standards (Frontend)
- camelCase for variables/functions, PascalCase for components/types
- Strict mode enabled
- TanStack Query for server state, Zustand for UI state
- No mock data on frontend — must call real API
- Components in `src/app/` follow Next.js App Router conventions

## Migration-Driven Development
- Every DB change must have an Alembic migration (up + down)
- Migrations run via `scripts/bootstrap.sh migrate`
- Each service has its own `alembic/` directory and `alembic.ini`
- Test: `docker compose down -v` -> `docker compose up` -> clean boot

## Commit Convention
```
<type>(scope): <summary>

Rationale: <1 line why>
Constraints: <key limits>
Rejected: <alternative and why>
Confidence: <high|medium|low>
Tested: <not run|partial|full>

Types: feat, fix, infra, test, docs, refactor, style, chore
Scope: slice-N, auth, workspace, orchestrator, artifact, frontend, ci, global

Lore trailers REQUIRED for: feat, fix, refactor, perf
Skip Lore for: docs, chore, style, test, ci
See docs/lore.md for full guide.
```

## Split Patterns

### Python — split by responsibility
```
# WRONG: 1 file 500+ lines
apps/service/src/api/routes.py

# RIGHT: split by resource
apps/service/src/api/
  routes.py              # 30 lines: mount sub-routers
  routes_tasks.py        # 80 lines
  routes_runs.py         # 70 lines
  schemas.py             # 50 lines
```

### React — split by component
```
# WRONG: 1 component 600 lines
apps/web/src/app/.../page.tsx

# RIGHT: extract components + hooks
apps/web/src/app/.../
  page.tsx               # 50 lines: layout
  _components/
    TaskTable.tsx         # 100 lines
    StatsCards.tsx        # 60 lines
  _hooks/
    usePageData.ts        # 50 lines
```
