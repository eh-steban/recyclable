---
paths:
  - "backend/**"
---

# Backend Mental Model

Architecture constraints and load-bearing decisions for the Python
research worker. This document describes how the worker is shaped and
why -- not what specific files or APIs exist (those live in code and
in `.claude/rules/backend/architecture.md`).

This is a stub. Fill in as constraints stabilize. Until then, treat
unwritten sections as "no committed constraint -- ask before
introducing one."

## Role of the worker

The backend is a Python research worker. It is not on the user request
path. It runs ingestion, extraction, conflict detection, and eval runs.
Latency is not load-bearing; correctness, citation fidelity, and
auditability are.

The user-facing assistant lives in the frontend and calls Sonnet
synchronously. The worker calls Opus for the agentic research loop.

## Architectural commitments

- **DDD layering.** `domain/` is pure business logic with no framework
  imports. `infra/` adapts external systems (Postgres, HTTP, LLM SDK).
  `api/` exposes use cases. `cli/` is the operator entry point.
  Domain logic must not leak into `infra/` or `api/`.
- **Postgres is the product asset.** Structured rules drive both SEO
  pages and assistant answers. There is no separate hand-written
  content layer. Schema changes are reviewed against
  `.claude/rules/data-model.md`.
- **Fail fast at boundaries.** Validate inputs at the system edge
  (HTTP, CLI, ingestion). Refuse to extract or answer when evidence
  is missing rather than synthesizing a guess.
- **Ingestion is auditable.** Every applied rule traces back to a
  source document and an extraction trace. Mistakes are reviewable;
  silent overrides are not allowed.

## Non-commitments (for now)

- Specific ORM, queue, or scheduler choices are not load-bearing yet.
  When one is chosen, capture the decision here.
- Concurrency model for the ingestion loop is not yet decided.
- Multi-tenant boundaries are not yet defined.

## Open questions

- Where does conflict detection live -- domain service or use case?
- How are extraction confidence scores represented on the data model?
- What is the failure mode when a source document is fetched but
  extraction yields zero rules?

When one of these is decided, promote the resolution into
`Architectural commitments` above and remove it from this list.
