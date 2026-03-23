# Observability Architecture

> How Keviq Core services expose metrics, propagate correlation IDs, and integrate
> with the Prometheus/Grafana monitoring stack.

## Overview

All 15 backend services expose a `/metrics` endpoint in Prometheus text format.
The telemetry-service scrapes these endpoints on a configurable interval and
stores samples in the `telemetry_core` schema. An optional Prometheus + Grafana
stack can run alongside the core compose file for dashboarding and alerting.

## Metrics Library

Metrics are provided by the shared `mona_os_logger` package
(`packages/logger/mona_os_logger/metrics.py`).

### MetricsRegistry

A per-process singleton that holds counters and histograms.

```python
from mona_os_logger.metrics import MetricsRegistry

registry = MetricsRegistry()
registry.increment("mona_http_requests_total", labels={"method": "GET", "path": "/api/v1/tasks", "status": "200"})
registry.observe("mona_http_request_duration_ms", 42.5, labels={"method": "GET", "path": "/api/v1/tasks"})
```

### MetricsMiddleware

ASGI middleware that automatically records HTTP metrics for every request.
Applied in each service's `main.py`:

```python
from mona_os_logger.metrics import MetricsMiddleware

app.add_middleware(MetricsMiddleware)
```

The middleware records three metric families per request:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `mona_http_requests_total` | counter | method, path, status | Total HTTP requests |
| `mona_http_request_duration_ms_sum` | counter | method, path | Cumulative request duration (ms) |
| `mona_http_request_duration_ms_count` | counter | method, path | Number of duration observations |
| `mona_http_request_errors_total` | counter | method, path | Requests with status >= 500 |

### /metrics Endpoint

Each service registers a `GET /metrics` route that renders the registry in
Prometheus exposition format:

```
# HELP mona_http_requests_total Total HTTP requests
# TYPE mona_http_requests_total counter
mona_http_requests_total{method="GET",path="/api/v1/tasks",status="200"} 147
mona_http_requests_total{method="POST",path="/api/v1/tasks",status="201"} 23

# HELP mona_http_request_duration_ms_sum Cumulative request duration in ms
# TYPE mona_http_request_duration_ms_sum counter
mona_http_request_duration_ms_sum{method="GET",path="/api/v1/tasks"} 6234.5

# HELP mona_http_request_duration_ms_count Number of duration observations
# TYPE mona_http_request_duration_ms_count counter
mona_http_request_duration_ms_count{method="GET",path="/api/v1/tasks"} 147
```

## Agent-Runtime Domain Metrics

The agent-runtime service emits additional domain-specific metrics via
`apps/agent-runtime/src/application/runtime_metrics.py`:

| Metric | Type | Description |
|--------|------|-------------|
| `mona_agent_invocations_total` | counter | Agent invocations started |
| `mona_agent_tool_calls_total` | counter | Tool calls executed across all invocations |
| `mona_agent_turns_total` | counter | LLM turns completed |
| `mona_agent_guardrail_retries_total` | counter | Guardrail-triggered retries |
| `mona_agent_budget_exhausted_total` | counter | Invocations stopped due to budget limits |

These are recorded at invocation lifecycle points and exposed on the same
`/metrics` endpoint.

## Correlation IDs

Every inbound request receives a correlation ID via the `X-Request-ID` header.
If the caller provides the header, the value is preserved; otherwise a new
UUID is generated. The ID is:

1. Attached to all log records for the request (structured JSON logs).
2. Propagated to downstream service-to-service calls.
3. Returned in the response `X-Request-ID` header.

This allows tracing a single user action across multiple services.

## Telemetry Service

The telemetry-service (`apps/telemetry-service`, port 8015) acts as a
lightweight scraper:

- Periodically fetches `/metrics` from all configured service endpoints.
- Parses Prometheus text format via `apps/telemetry-service/src/application/metrics_parser.py`.
- Stores samples in `telemetry_core.metric_samples`.
- Exposes scraped data via its own API for the frontend health dashboard.

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SCRAPE_INTERVAL_SECONDS` | 30 | How often to scrape targets |
| `SCRAPE_TARGETS` | (all 15 services) | Comma-separated list of `host:port` |

## Prometheus + Grafana Stack

An optional observability overlay is available for local development and
staging environments.

### Enabling

```bash
docker compose \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.observability.yml \
  up
```

This adds:

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | 9090 | Metric scraping and storage |
| Grafana | 3001 | Dashboards and alerting |

### Prometheus Configuration

Prometheus is pre-configured to scrape all 15 services at their internal
`host:8000/metrics` endpoints. The scrape config is generated from the service
registry in `docker-compose.observability.yml`.

### Grafana

Grafana starts with Prometheus as a pre-configured datasource. Default
credentials: `admin` / `admin`.

Suggested dashboard panels:

- **Request Rate**: `rate(mona_http_requests_total[5m])` by service
- **Error Rate**: `rate(mona_http_request_errors_total[5m])` by service
- **Latency P50/P99**: computed from duration sum/count
- **Agent Invocations**: `rate(mona_agent_invocations_total[5m])`

## Service Inventory

All 15 services expose `/metrics`:

| # | Service | Internal URL |
|---|---------|-------------|
| 1 | api-gateway | `http://api-gateway:8000/metrics` |
| 2 | auth-service | `http://auth-service:8000/metrics` |
| 3 | workspace-service | `http://workspace-service:8000/metrics` |
| 4 | policy-service | `http://policy-service:8000/metrics` |
| 5 | orchestrator | `http://orchestrator:8000/metrics` |
| 6 | agent-runtime | `http://agent-runtime:8000/metrics` |
| 7 | artifact-service | `http://artifact-service:8000/metrics` |
| 8 | execution-service | `http://execution-service:8000/metrics` |
| 9 | event-store | `http://event-store:8000/metrics` |
| 10 | model-gateway | `http://model-gateway:8000/metrics` |
| 11 | sse-gateway | `http://sse-gateway:8000/metrics` |
| 12 | audit-service | `http://audit-service:8000/metrics` |
| 13 | notification-service | `http://notification-service:8000/metrics` |
| 14 | secret-broker | `http://secret-broker:8000/metrics` |
| 15 | telemetry-service | `http://telemetry-service:8000/metrics` |

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `/metrics` returns 404 | Verify `MetricsMiddleware` is added in the service's `main.py` |
| Metrics are stale | Check telemetry-service logs for scrape errors |
| No correlation ID in logs | Ensure `X-Request-ID` middleware is registered before route handlers |
| Grafana shows no data | Verify Prometheus targets are up at `http://localhost:9090/targets` |
