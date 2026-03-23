# Security Policy

## Reporting a Vulnerability

**Do NOT open a public GitHub issue.** Instead:

1. Email **security@keviqai.com** with a description and reproduction steps.
2. Include affected versions, impact assessment, and any suggested fix.
3. If you have a CVE ID, include it.

### Response Timeline

| Step | Target |
|------|--------|
| Acknowledgment | 48 hours |
| Patch available | 7 days |
| Public disclosure | 90 days after report (coordinated) |

We will credit reporters in the release notes unless anonymity is requested.

## Scope

### In Scope

- Core platform code (all services in `apps/`)
- Shared packages (`packages/`)
- Authentication and authorization flows (JWT, RBAC, internal auth)
- Secret management (secret-broker, key rotation)
- Dependency vulnerabilities in our lock files

### Out of Scope

- Third-party Docker base images (report upstream)
- User misconfiguration (weak passwords, exposed ports)
- Denial-of-service via resource exhaustion on local dev setups

## Security Model Summary

| Layer | Mechanism |
|-------|-----------|
| User authentication | JWT with configurable signing secrets |
| Service-to-service auth | Internal auth tokens verified at each service |
| Authorization | Capability-based RBAC with workspace-level tenant isolation |
| Agent execution | Sandboxed runtime environment |
| Secrets at rest | Encrypted via secret-broker with key rotation support |
| Transport | HTTPS/TLS termination expected at load balancer |

## Production Deployment

Before deploying to production, follow the full checklist:
[docs/ops/production-deployment-checklist.md](docs/ops/production-deployment-checklist.md)

At minimum: rotate all default secrets, enable TLS, and restrict network access
to internal service ports.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest `v0.x` release | Yes |
| Older releases | No — upgrade to latest |

Keviq Core is pre-1.0. We only patch the latest release.
