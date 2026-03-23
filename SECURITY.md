# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email security concerns to the repository maintainers
3. Include a description of the vulnerability and steps to reproduce

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Security Model

Keviq Core uses:
- JWT-based authentication with configurable secrets
- Service-to-service authentication via internal auth tokens
- Capability-based RBAC (role-based access control)
- Workspace-level tenant isolation
- Sandbox execution for agent workloads

## Production Security Checklist

Before deploying to production, ensure you:
- Change all default secrets (JWT, internal auth, Redis password, DB passwords)
- Use the `.env.cloud.example` template as a starting point
- Review [docs/ops/production-deployment-checklist.md](docs/ops/production-deployment-checklist.md)
- Enable HTTPS/TLS termination at your load balancer
