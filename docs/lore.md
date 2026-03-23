# Lore — Decision Context in Commits

## Goal
Store **"why"**, not only "what", in commit history.
Conventional Commits = what changed. Lore trailers = why this way.

## Template
```
<type>(<scope>): <summary>

Rationale: <one-line why>
Constraints: <key limits>
Rejected: <alternative and rejection reason>
Confidence: <high|medium|low>
Tested: <not run|partial|full>

Refs: <optional>
```

## Required fields
- **Rationale** — one sentence explaining the decision
- **Confidence** — high / medium / low
- **Tested** — not run / partial / full

## Recommended fields
- **Constraints** — real limits only (deadline, compat, perf, infra)
- **Rejected** — at least one considered alternative when non-trivial
- **Refs** — issue/PR/doc link

## When to use Lore
- **Always**: feat, fix, refactor, perf
- **Skip**: docs, chore, style, test, ci, build

## Confidence values
| Value | Meaning |
|-------|---------|
| high | Root cause understood, tests sufficient |
| medium | Right direction but assumptions remain |
| low | Workaround or emergency fix |

## Tested values
| Value | Meaning |
|-------|---------|
| full | Unit + integration per team standard |
| partial | Local/manual testing only |
| not run | No tests (e.g., docs-only) |

## Writing rules
- Rationale: **1 sentence**
- Constraints: **1–2 bullet points**
- Rejected: **1 alternative + why rejected**
- Total overhead: **4–7 lines** more than a normal commit

## Bad examples
```
Rationale: better
Rejected: other way
```

## Good examples
```
Rationale: avoid double fetch during hydration because it causes duplicate writes
Rejected: move dedupe into backend; rejected because API contract freeze this release
```

## Query history
```bash
scripts/lore-log                          # all decisions
scripts/lore-log "Rejected:"             # rejected alternatives
scripts/lore-log "Confidence: low"       # low-confidence commits needing review
git log --grep="^Constraints:.*Redis"    # constraints about Redis
```

## Lore vs ADR
| | Lore | ADR |
|---|------|-----|
| Scope | Commit-level implementation decision | Architecture-wide decision |
| Location | Git commit message (trailers) | docs/adr/ files |
| When | Every non-trivial commit | Major architecture changes |
| Size | 4–7 extra lines | Full document with diagrams |

**Rule: Architecture-wide → ADR. Commit-level why → Lore.**

## Setup
```bash
# Enable template
git config commit.template .gitmessage.lore.txt

# Enable hooks
chmod +x .githooks/commit-msg
git config core.hooksPath .githooks

# Use helper
chmod +x scripts/lore-commit scripts/lore-log
```
