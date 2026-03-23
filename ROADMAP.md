# Roadmap

> Where Keviq Core is going. This is a living document — priorities shift based on community feedback and production learnings.
>
> Want to influence the roadmap? [Open a discussion](https://github.com/Keviqai/keviq-core/issues) or vote on existing issues.

---

## Vision

Keviq Core today is a **production-ready control plane** for AI agents. The long-term vision is to become the **standard infrastructure layer** that any AI agent — regardless of framework, model, or language — can run on.

The path there has four phases:

```
  Now             Next             Later           Future
┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌───────────────┐
│ Hardened  │──▶│  Open    │──▶│  Extensible  │──▶│  Ecosystem    │
│ Platform  │   │  SDK     │   │  Platform    │   │  & Federation │
└──────────┘   └──────────┘   └──────────────┘   └───────────────┘
  v0.x            v1.0           v1.x–v2.0          v2.x+
```

---

## Phase 1 — Hardened Platform (current)

**Status: In progress**

The foundation is built. 15 microservices, 21 user journeys, 1500+ tests. This phase is about making it production-solid.

| Item | Status | Description |
|------|--------|-------------|
| Kubernetes manifests | Planned | Helm charts for production K8s deployment. Docker Compose is great for dev; K8s is the production target. |
| CI/CD pipeline | Planned | GitHub Actions: lint, test, build images, architecture gate, deploy preview. |
| Database connection pooling | Planned | PgBouncer or built-in pool sizing for multi-worker services. |
| Redis Cluster support | Planned | Event bus scaling beyond single-node Redis. |
| Rate limiting (distributed) | Planned | Move from in-memory to Redis-backed rate limiting for multi-instance API gateway. |
| mTLS between services | Planned | Zero-trust internal networking. Currently services trust the Docker network. |
| ASGI middleware migration | Planned | Replace BaseHTTPMiddleware with pure ASGI for better performance under load. |
| OpenTelemetry traces | Planned | Distributed tracing across all 15 services. Currently Prometheus metrics only. |

**Good first issues:** CI pipeline setup, Helm chart scaffolding, connection pool configuration.

---

## Phase 2 — Agent SDK `@keviq/sdk`

**Status: Design**

The highest-leverage feature for adoption. Today, connecting an agent to Keviq Core means calling REST APIs directly. The SDK makes it a one-liner.

### Python SDK (`keviq`)

```python
from keviq import KeviqClient

client = KeviqClient(base_url="http://localhost:8080", token="...")

# Register an agent
@client.agent("code-reviewer")
def review_code(task):
    # Your agent logic here — LangChain, CrewAI, raw API calls, anything
    result = my_langchain_agent.invoke(task.brief)

    # Artifacts are tracked automatically
    task.upload_artifact("review.md", result, content_type="text/markdown")

    # Need human approval? Just ask.
    approved = task.request_approval(
        action="merge-to-main",
        context={"diff": result}
    )
    if approved:
        task.complete(result)
```

### TypeScript SDK (`@keviq/sdk`)

```typescript
import { KeviqClient } from "@keviq/sdk";

const keviq = new KeviqClient({ baseUrl: "http://localhost:8080" });

const task = await keviq.tasks.create({
  title: "Analyze Q3 reports",
  workspace: "analytics-team",
});

const run = await keviq.runs.start(task.id, { agent: "analyst-v2" });

// Stream events in real-time
for await (const event of keviq.runs.stream(run.id)) {
  console.log(event.type, event.data);
}
```

### SDK scope

| Feature | Description |
|---------|-------------|
| Task lifecycle | Create, start, monitor, cancel tasks programmatically |
| Artifact upload | Upload outputs with automatic provenance tracking |
| Approval gates | Request and poll for human approval within agent logic |
| Event streaming | Subscribe to real-time execution events (SSE) |
| Secret access | Read workspace secrets through the broker |
| Workspace management | CRUD workspaces, manage members and policies |
| Auth | JWT token management, refresh, service accounts |
| Type safety | Full TypeScript types, Python type hints, Pydantic models |

---

## Phase 3 — Plugin System & Extensions

**Status: Concept**

Transform Keviq Core from a platform you deploy into a platform you extend.

### Agent plugins

Register agent implementations as plugins that users can enable per workspace:

```yaml
# keviq-plugin.yaml
name: "code-reviewer"
version: "1.0.0"
runtime: python
entrypoint: "agent:main"
capabilities:
  - artifact:read
  - artifact:write
  - execution:sandbox
triggers:
  - event: "task.created"
    filter: { template: "code-review" }
config:
  model: "gpt-4o"
  max_turns: 10
```

### Tool plugins

Extend the execution environment with custom tools:

```yaml
name: "github-tools"
version: "1.0.0"
tools:
  - name: "create_pull_request"
    description: "Create a PR on GitHub"
    parameters: { ... }
    handler: "tools.github:create_pr"
    secrets: ["GITHUB_TOKEN"]
```

### Extension points

| Extension | What it enables |
|-----------|----------------|
| **Agent plugins** | Drop-in agent implementations. Users install agents like apps. |
| **Tool plugins** | Custom tools agents can call. Sandboxed, secret-aware, audited. |
| **Storage backends** | S3, GCS, Azure Blob — beyond local filesystem for artifacts. |
| **Auth providers** | OIDC/SAML SSO, LDAP, OAuth2 — beyond built-in JWT. |
| **LLM providers** | First-class support for Anthropic, Google, Mistral, local models. |
| **Notification channels** | Slack, Teams, Discord, PagerDuty — beyond email. |
| **Event consumers** | Webhooks, external event buses (Kafka, NATS, SQS). |
| **Execution backends** | Kubernetes Jobs, AWS Lambda, Firecracker — beyond Docker. |

### Plugin registry

A public registry where the community publishes and discovers plugins:

```bash
keviq plugin install @community/github-tools
keviq plugin install @community/slack-notifications
keviq plugin install @community/s3-storage
```

---

## Phase 4 — Ecosystem & Federation

**Status: Future**

### Multi-instance federation

Connect multiple Keviq Core instances across teams or organizations:

- **Cross-instance task delegation** — Team A's agent can request work from Team B's agent
- **Artifact sharing** — publish artifacts to a shared registry across instances
- **Federated identity** — single sign-on across federated instances
- **Audit aggregation** — unified audit trail across the fleet

### Marketplace

- **Agent marketplace** — publish, discover, and install pre-built agents
- **Template library** — task templates for common workflows (code review, report generation, data analysis)
- **Integration catalog** — one-click integrations with GitHub, Jira, Slack, Notion, Linear

### AI infrastructure primitives

| Primitive | Description |
|-----------|-------------|
| **Agent memory** | Long-term memory service — persistent context across tasks and runs |
| **Knowledge base** | RAG-ready document store with automatic chunking, embedding, and retrieval |
| **Evaluation framework** | Automated agent evaluation: accuracy, cost, latency, safety scoring |
| **Cost tracking** | Per-task, per-agent, per-workspace LLM cost attribution |
| **Fine-tuning pipeline** | Collect agent interactions → curate → fine-tune → deploy updated model → A/B test |
| **Multi-model routing** | Intelligent model selection based on task type, cost, latency, quality requirements |
| **Guardrails engine** | Content filtering, output validation, PII detection, compliance checks |

---

## What we're NOT building

Clarity on scope is as important as the roadmap itself.

| Out of scope | Why |
|-------------|-----|
| Our own LLM | We're infrastructure, not a model company. Bring any model. |
| Visual agent builder | Drag-and-drop builders optimize for demos. We optimize for production. |
| Chat interface | Keviq Core is task-driven, not conversation-driven. Chat UIs exist everywhere. |
| Monolithic agent framework | We don't compete with LangChain/CrewAI. We're the OS they run on. |

---

## How to contribute to the roadmap

1. **Comment on issues** tagged [`roadmap`](https://github.com/Keviqai/keviq-core/labels/roadmap) — your use case helps prioritize
2. **Open an issue** describing what you're trying to build and what's missing
3. **Submit a PR** for any planned item — check the issue for design notes first
4. **Build a plugin** when the plugin system ships — early adopters shape the API

---

## Timeline

We don't commit to specific dates — we commit to shipping in order and not skipping phases.

| Phase | Target | Milestone |
|-------|--------|-----------|
| Phase 1 | **Now** | Production-grade: K8s, CI/CD, distributed rate limiting, OpenTelemetry |
| Phase 2 | **Next** | SDK release: `pip install keviq` and `npm install @keviq/sdk` |
| Phase 3 | **After SDK** | Plugin system: agents, tools, storage, auth providers as installable extensions |
| Phase 4 | **After plugins** | Ecosystem: federation, marketplace, AI infrastructure primitives |

Each phase unlocks the next. The SDK can't be great without a hardened platform. Plugins can't work without a stable SDK. The ecosystem can't grow without plugins.
