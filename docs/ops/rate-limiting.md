# Rate Limiting

> How Keviq Core protects services from overload via per-route, per-user, and
> per-IP rate limits.

## Overview

Rate limiting is enforced at the api-gateway using `slowapi` (a
Starlette/FastAPI wrapper around `limits`). Limits are applied before requests
are proxied to downstream services. Internal service-to-service calls bypass
rate limiting entirely.

## Rate Limit Tiers

### Authentication Routes

| Route | Limit | Scope | Rationale |
|-------|-------|-------|-----------|
| `POST /api/v1/auth/login` | 10/min | per IP | Brute-force protection |
| `POST /api/v1/auth/register` | 5/min | per IP | Abuse prevention |
| `POST /api/v1/auth/refresh` | 20/min | per IP | Token refresh headroom |

### Write Endpoints

All state-mutating endpoints (POST, PUT, PATCH, DELETE) that are not in the
auth tier:

| Limit | Scope | Examples |
|-------|-------|---------|
| 60/min | per user (JWT sub) | Create task, submit artifact, approve request |

### Read Endpoints

All GET requests to API routes:

| Limit | Scope | Examples |
|-------|-------|---------|
| 300/min | per user (JWT sub) | List tasks, get artifact, fetch timeline |

### Global Fallback

| Limit | Scope | Description |
|-------|-------|-------------|
| 600/min | per IP | Catch-all for any request not matched above |

## Exempt Routes

The following routes are never rate-limited:

| Route Pattern | Reason |
|---------------|--------|
| `/healthz/*` | Health checks must always respond |
| `/metrics` | Prometheus scraping |
| `/internal/*` | Service-to-service communication |

### Service-to-Service Exemption

Requests that include a valid `X-Internal-Auth` header matching the
`INTERNAL_AUTH_SECRET` environment variable bypass all rate limits. This
header is set automatically by service proxy clients.

## Response Headers

Every rate-limited response includes standard headers:

| Header | Description | Example |
|--------|-------------|---------|
| `X-RateLimit-Limit` | Maximum requests allowed in the window | `60` |
| `X-RateLimit-Remaining` | Requests remaining in the current window | `42` |
| `X-RateLimit-Reset` | Unix timestamp when the window resets | `1711238400` |

### When Limit Is Exceeded

The gateway returns HTTP 429 with an additional header:

| Header | Description | Example |
|--------|-------------|---------|
| `Retry-After` | Seconds until the client may retry | `12` |

Response body:

```json
{
  "detail": "Rate limit exceeded. Retry after 12 seconds.",
  "retry_after": 12
}
```

## Configuration

Rate limits are configurable via environment variables on the api-gateway
service. All values follow the `slowapi` rate string format
(`<count>/<period>`).

| Env Var | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_LOGIN` | `10/minute` | Login endpoint limit |
| `RATE_LIMIT_REGISTER` | `5/minute` | Registration endpoint limit |
| `RATE_LIMIT_REFRESH` | `20/minute` | Token refresh limit |
| `RATE_LIMIT_WRITE` | `60/minute` | Write endpoint default |
| `RATE_LIMIT_READ` | `300/minute` | Read endpoint default |
| `RATE_LIMIT_GLOBAL` | `600/minute` | Global per-IP fallback |
| `RATE_LIMIT_STORAGE` | `memory://` | Backend for counters (`memory://` or `redis://host:port`) |

### Production Recommendation

In production, set `RATE_LIMIT_STORAGE` to a Redis URL so that limits are
shared across gateway replicas:

```
RATE_LIMIT_STORAGE=redis://redis:6379/1
```

## Implementation Details

### Middleware Stack Order

```
Request
  -> CORS
  -> X-Request-ID (correlation)
  -> RateLimitMiddleware        <-- rate limits checked here
  -> AuthMiddleware
  -> Route handler / proxy
```

Rate limiting runs before authentication so that unauthenticated floods
(e.g., login brute-force) are caught early. For authenticated routes, the
middleware extracts the user ID from the JWT to apply per-user limits.

### Key Identification

| Scope | Key Source |
|-------|-----------|
| Per IP | `request.client.host` (respects `X-Forwarded-For` behind proxy) |
| Per user | `sub` claim from validated JWT |
| Unauthenticated | Falls back to per-IP |

## Testing Rate Limits

```bash
# Trigger login rate limit (11th request should return 429)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8080/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
done

# Check rate limit headers
curl -v http://localhost:8080/api/v1/workspaces 2>&1 | grep -i x-ratelimit
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 429 on internal calls | Verify `X-Internal-Auth` header is set and matches `INTERNAL_AUTH_SECRET` |
| Limits not shared across replicas | Switch `RATE_LIMIT_STORAGE` to Redis |
| Different limits than expected | Check env var overrides in docker-compose |
| Health checks returning 429 | Verify `/healthz` is in the exempt list |
