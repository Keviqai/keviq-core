# Contributing to Keviq Core

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/<your-username>/keviq-core.git`
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Follow the [Quick Start](README.md#quick-start) to set up your local environment

## Development Standards

### Code Style

- **Python**: snake_case, type hints mandatory, functions < 50 lines, files < 300 lines
- **TypeScript**: camelCase, strict mode, components < 150 lines, files < 300 lines
- **API routes**: handler < 80 lines, business logic in service layer

See [docs/CODING-RULES.md](docs/CODING-RULES.md) for detailed coding standards.

### Testing

- All new code must include tests
- Run architecture tests: `python -m pytest tools/arch-test/ -v`
- Run smoke tests: `./scripts/smoke-test.sh`
- See [docs/TESTING-RULES.md](docs/TESTING-RULES.md) for testing standards

### Commit Messages

```
<type>(scope): <summary>

Types: feat, fix, infra, test, docs, refactor, style, chore
```

## Pull Request Process

1. Ensure your changes pass all tests
2. Update documentation if your changes affect APIs, configuration, or architecture
3. Keep PRs focused — one feature or fix per PR
4. Describe what changed and why in the PR description

## Architecture

This is a microservices monorepo with 15 backend services. Each service owns its own PostgreSQL schema.

Key constraints:
- Do not merge services or create new ones without discussion
- Each service communicates via the outbox pattern + Redis Streams
- See [docs/02-architectural-invariants.md](docs/02-architectural-invariants.md) for architectural rules

## Questions?

Open an issue for questions, bugs, or feature requests.
