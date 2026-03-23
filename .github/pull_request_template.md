## What does this PR do?

<!-- Describe the change and why it's needed. Link to an issue if applicable. -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring (no behavior change)
- [ ] Documentation
- [ ] Infrastructure / CI
- [ ] Test coverage

## Checklist

- [ ] I have read [CONTRIBUTING.md](CONTRIBUTING.md)
- [ ] My code follows the project's coding standards ([docs/CODING-RULES.md](docs/CODING-RULES.md))
- [ ] I have added tests for new functionality
- [ ] All existing tests pass locally (`python -m pytest tools/arch-test/ -v`)
- [ ] I have updated documentation if my change affects APIs, config, or architecture
- [ ] No file exceeds 300 lines
- [ ] No function exceeds 50 lines
- [ ] No route handler exceeds 80 lines

## Architecture compliance

- [ ] No cross-service imports (each service owns its own schema)
- [ ] No new services created without discussion
- [ ] Event contracts follow the outbox pattern
- [ ] API changes are backward-compatible or documented as breaking
