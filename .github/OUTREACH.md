# Outreach Templates

## Show HN (use LAST — Tuesday-Thursday, 9-11am ET)

**Title:** Show HN: Keviq Core – Open-source control plane for AI agents in production

**Text:**
We built Keviq Core because every team deploying AI agents hits the same infrastructure wall.

You can build a working agent in an afternoon with LangChain or CrewAI. But putting it in production — with traceability, human-in-the-loop approval, RBAC, audit logging, artifact versioning — requires 6+ months of platform work. Every team builds it differently, poorly, or not at all.

Keviq Core is the missing layer between your agent framework and your organization. It's 15 microservices (Python/FastAPI + TypeScript/Next.js) providing:

- Task orchestration with human-in-the-loop checkpoints
- Artifact lineage tracking (like Git, but for agent outputs)
- RBAC, multi-tenancy, and audit logging out of the box
- Event-driven architecture with SSE streaming
- One `docker compose up` to run everything

We're at v0.1.0-alpha — 1500+ tests passing, 19 architecture docs, MIT licensed.

What we'd love feedback on: Is this solving a real pain point for you? What would you need to actually try it?

https://github.com/Keviqai/keviq-core

---

## Reddit (r/selfhosted, r/LocalLLaMA)

**Title:** I open-sourced a control plane for running AI agents in production — 15 microservices, Docker Compose, MIT license

**Text:**
Hey everyone,

I've been building infrastructure for AI agents and kept hitting the same problem: agent frameworks are great for building agents, but terrible for running them in production.

Every team I've seen ends up rebuilding the same things: auth, RBAC, audit logging, artifact tracking, human approval flows, secret management. It's months of work before you write a single line of agent logic.

So I built **Keviq Core** — an open-source control plane that handles all of this. Think of it as "Kubernetes for AI agents" (but without the complexity).

**What's included:**
- 15 microservices: orchestrator, agent-runtime, auth, RBAC, audit, artifact tracking, event store, etc.
- Next.js dashboard
- Docker Compose: `docker compose up` and you're running
- 1500+ tests, 19 architecture docs
- MIT license

**Tech stack:** Python/FastAPI (backend), TypeScript/Next.js (frontend), PostgreSQL, Redis

It's early (v0.1.0-alpha) but the foundation is solid. Looking for feedback and contributors.

GitHub: https://github.com/Keviqai/keviq-core

---

## X/Twitter

**Post 1 (announcement):**
I just open-sourced Keviq Core — a production control plane for AI agents.

Every team building with LangChain/CrewAI hits the same wall: auth, audit, human-in-the-loop, artifact tracking.

15 microservices. One docker compose up. MIT license.

github.com/Keviqai/keviq-core

**Post 2 (thread):**
The problem: You can build an AI agent in an afternoon. But running it in production — with traceability, RBAC, and human approval — takes months of infrastructure.

Keviq Core solves this. Here's what's inside: [thread with architecture diagram]

---

## Dev.to / Hashnode

**Title:** Why I Built an Open-Source Control Plane for AI Agents (And What I Learned)

**Outline:**
1. The problem (every team rebuilds the same infra)
2. What Keviq Core does (with architecture diagram)
3. Technical decisions (why 15 microservices, why event-driven)
4. What's next (roadmap)
5. Call to action (try it, contribute)

---

## Awesome Lists to Submit

- awesome-ai-agents
- awesome-llm-apps
- awesome-selfhosted
- awesome-fastapi
