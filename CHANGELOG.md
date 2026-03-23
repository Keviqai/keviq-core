# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-23

Initial public release of Keviq Core — an AI-native work operating system for
orchestrating tasks, running agents, and managing artifacts with full provenance.

### Added

- **Microservices architecture** — 15 backend services (Python 3.12 / FastAPI), each with isolated DB schema and health endpoints
- **Task orchestration** — create, run, and monitor tasks through a full lifecycle (draft, queued, running, completed, failed)
- **Agentic tool loop** — model-driven tool call cycle with budget enforcement, guardrails, retry policies, and stuck-state recovery
- **Artifact management** — upload, store, finalize, and retrieve artifacts with SHA-256 checksums, provenance tracking, and parent/child lineage
- **Artifact search and tagging** — 10+ filter parameters (name, type, status, MIME type, date range, tags), sortable results, tag CRUD endpoints
- **Human approval gates** — tool-level approval policies for risky operations (shell, scripts), with approve/reject/override/cancel workflows
- **Auth service** — JWT-based authentication with register, login, token refresh, and race-safe duplicate prevention
- **Multi-tenant workspaces** — workspace-scoped data isolation with role-based access control (owner, admin, editor, viewer)
- **Secret management** — encrypted secret storage with versioned key rotation and per-workspace isolation
- **Model gateway** — OpenAI-compatible LLM proxy with pluggable providers, including a local Claude Code CLI bridge for development
- **Event-driven architecture** — outbox pattern with Redis Streams for inter-service communication, 35+ event types
- **Real-time streaming** — Server-Sent Events gateway for live task progress, approval notifications, and activity feeds
- **Telemetry and metrics** — Prometheus-compatible `/metrics` endpoints on all services, scrape engine, and metric storage
- **Observability stack** — optional Prometheus + Grafana overlay via Docker Compose, with pre-built service dashboards
- **Rate limiting** — tiered limits at the API gateway (auth, read, write, global) with configurable thresholds and standard rate-limit headers
- **Task comments** — threaded comments on tasks with outbox event emission and display name resolution
- **Activity feed** — workspace-wide activity stream with 40+ human-readable event labels and category filters
- **Review queue** — shared "Needs Review" page aggregating pending approvals with type filtering and context summaries
- **Next.js frontend** — 21 pages covering workspaces, tasks, runs, artifacts, approvals, activity, health dashboard, and onboarding
- **Tool execution viewer** — debug panel showing stdout/stderr, exit codes, duration, and sandbox context for each tool call
- **Agent diagnostics** — invocation debug panel with failure categorization, turn-by-turn summaries, and intervention timeline
- **Notification service** — delivery tracking with retry (3 attempts, exponential backoff) and status filtering
- **Event retention** — configurable cleanup for events, outbox rows, and notifications with dry-run support
- **Docker Compose setup** — full local environment with health checks, dependency ordering, bootstrap script, and smoke tests
- **Architecture test suite** — 910+ tests enforcing import boundaries, internal auth, workspace isolation, and service contracts
- **Unit test suite** — 636+ tests across all non-stub services
- **End-to-end tests** — Playwright specs covering auth, tasks, artifacts, approvals, and a full 7-step user journey
- **Load testing** — k6 scripts for auth flow, task/artifact flow, and concurrent race condition scenarios
- **Production deployment guide** — operator checklist covering secrets, env config, bring-up procedure, verification, and rollback

### Changed

- Artifact service routes split into sub-modules for maintainability (queries, commands, content, lineage, tags)
- Agent runtime execution handler decomposed into focused modules (resume, tool helpers, shared execution, approval gate)
- API gateway routes split by concern for clarity

### Fixed

- Race condition in concurrent user registration (TOCTOU resolved with INSERT ON CONFLICT)
- Artifact finalization checksum format mismatch between runtime and storage service
- SSE auth for EventSource clients (query-param token fallback since EventSource cannot send headers)
- JSONB bind parameter syntax across 5 services (PostgreSQL/SQLAlchemy compatibility)
- Gateway proxy timeout increased to 30s to prevent false errors on task launch

### Security

- Claude Code CLI bridge restricted to development/local/test environments (hard exit in production)
- Internal service-to-service auth headers stripped before external forwarding
- SSE token query parameter stripped before backend proxying
- API gateway 401 interceptor clears credentials and redirects on JWT expiry
