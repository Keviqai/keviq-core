# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-alpha] — 2026-03-25

### Added
- 15 microservices: orchestrator, agent-runtime, execution-service, api-gateway,
  model-gateway, auth-service, policy-service, workspace-service, artifact-service,
  event-store, audit-service, notification-service, secret-broker, telemetry-service,
  sse-gateway (stub)
- Next.js web dashboard (`apps/web`)
- Shared TypeScript SDK (`packages/api-client`)
- Docker Compose development stack
- CI pipeline (TypeScript build + Python unit tests)
- 19 architecture documents translated to English
- Contributor onboarding: CONTRIBUTING.md, Your First Contribution guide
- Issue templates (bug report, feature request) and PR template
- MIT license

### Known Issues
- `sse-gateway` is a stub with health endpoints only; SSE streaming is handled by `event-store`
- Contract tests for slices 5-6 are excluded from CI (in progress)
