---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD principles -- hub

How we apply Domain-Driven Design in this repo, distilled from
Vaughn Vernon, *Implementing Domain-Driven Design*, and adapted
to a two-service codebase (FastAPI backend + ingestion worker,
Next.js frontend) backed by a single Postgres knowledge base.

This file is a **navigation hub**. The principles themselves live
in topic-specific shards under `ddd/`. The hub holds:

- the philosophy (why we use DDD partially),
- the index of shard files,
- the project's catalog of bounded contexts and their
  classification,
- pointers to neighboring rules.

## Why we use DDD here, partially

DDD is not all-or-nothing. We use only the parts that help us:

- **Strategic design first.** Bounded contexts and a context map
  give us a shared mental model for how the user-path service,
  the ingestion worker, the frontend, and external sources
  interact. This is the highest-leverage DDD investment for a
  small team.
- **Tactical patterns à la carte.** Use Aggregates, Value
  Objects, Repositories, or Domain Events when the model
  genuinely calls for them. Don't introduce them as scaffolding.
- **Ubiquitous Language is non-negotiable.** Whatever we model,
  the names in code, schema, prompts, specs, and UI must match
  what we call the thing in conversation. This is the cheapest
  DDD habit with the largest long-term payoff.

If a principle in any shard would force ceremony without
clarity, skip it and note why in the relevant spec.

## Shards

Each shard distills one chapter (or one cohesive topic) of
Vernon's book into project-specific principles. Follow the link
when working on something the shard governs; otherwise the hub is
enough.

- [`ddd/bounded-contexts.md`](ddd/bounded-contexts.md) --
  Vernon Ch. 2. Defining a single bounded context: domains vs
  subdomains, Core/Supporting/Generic, naming, what lives inside
  the boundary, right-sizing, same-word-different-meaning.
- [`ddd/context-maps.md`](ddd/context-maps.md) -- Vernon Ch. 3.
  Relationships between contexts: integration patterns
  (Open Host Service, Published Language, ACL,
  Customer-Supplier, Separate Ways, Shared Kernel, Conformist,
  Big Ball of Mud), upstream/downstream direction, eventual
  consistency, translation maps, modeling unavailability.

Future shards (one per chapter, added as we work through the
book): Architecture, Entities, Value Objects, Services, Domain
Events, Modules, Aggregates, Factories, Repositories, Integrating
Bounded Contexts, Application.

## Candidate bounded contexts in this repo

These are the boundaries we currently believe exist. Treat this
list as the **starting context map**; refine it in
`private/specs/` as we learn.

- **Knowledge Base Context** -- jurisdictions, materials, rules,
  sources, facilities, traces. Owned by the backend; SQLAlchemy +
  Alembic is the source of truth. Lives in `backend/app/domain/`
  and `backend/app/infra/db/`.
- **Retrieval Context (user path)** -- the Sonnet loop:
  retrieval, prompt composition, validator, refusal, response.
  Lives in `backend/app/api/` + the domain services it composes.
- **Ingestion Context (research path)** -- the Opus loop: source
  fetch, extraction, conflict detection, eval. Lives in
  `backend/app/worker/`.
- **Presentation Context** -- SSG jurisdiction/material pages and
  the `/ask` UI. Lives in `frontend/app/` and `frontend/lib/`.

The HTTP API and generated TS client are the **boundary** between
backend contexts and the Presentation Context. The Postgres
schema is **internal** to the backend contexts and must not leak
across.

### Classification (Core / Supporting / Generic)

Vernon's classification, applied to our current candidate
contexts. Revisable as we learn.

- **Retrieval -- Core.** The product *is* "ask a recycling
  question, get a cited answer or an honest refusal." This is
  the differentiator.
- **Knowledge Base -- Core.** "Postgres is the product asset"
  per `CLAUDE.md`. The structured, sourced data is what we sell.
- **Ingestion -- Core.** The autonomous research loop is what
  lets the knowledge base scale beyond hand-curation.
  Non-trivial, differentiating.
- **Presentation -- Supporting.** Essential -- this is the
  surface users see -- but the model lives in the backend. The
  frontend is presentation around the core, not the core itself.

If we adopt third-party services (auth, billing, content
moderation, geocoding), classify them as **Generic** and wrap
them in an ACL.

### Caveat on Retrieval and Ingestion

Today these two surfaces share a single domain layer
(`backend/app/domain/`) and a single persistence layer
(`backend/app/infra/db/`) per `backend/CLAUDE.md`. By Vernon's
strict test (one model, one Ubiquitous Language = one context),
they are currently **application-service-level distinctions
inside a single backend context**, not two fully separate
bounded contexts. We list them separately because they have
distinct integration patterns (sync HTTP vs. async worker),
distinct LLM models (Sonnet vs. Opus), and distinct lifecycles --
useful for reasoning about upstream/downstream and ACL placement.
The boundary that today actually enforces a separate language is
the HTTP API surface between backend and frontend. Revisit this
split if Retrieval and Ingestion ever grow incompatible
vocabulary or stop sharing the domain layer.

## How this interacts with other rules

- **`contracts.md`** governs the *shape* of the HTTP boundary
  (the Open Host Service / Published Language for the
  backend → frontend integration). The DDD shards govern *why*
  that boundary exists and what counts as crossing it.
- **`backend/CLAUDE.md`** describes the DDD layering inside the
  backend (domain / application / infrastructure / api). Layering
  is *within* a context; bounded contexts are the larger
  boundary.
- **`refactoring.md`** forbids changing public contracts without
  authorization. An integration surface between bounded contexts
  -- even a purely internal Python module boundary -- is a public
  contract in this sense when other contexts depend on it. A
  refactor may not move or rename that surface without updating
  all dependents.
- **`private/invariants.md`** -- if a DDD principle in any shard
  ever conflicts with a numbered invariant, the invariant wins;
  flag the conflict and escalate.

## When to revisit

Update the hub when:

- A new context appears (new service, new external integration).
- Two contexts merge or split.
- An integration pattern between two contexts changes (e.g., we
  move from synchronous RPC to event-driven).
- We add a new shard for a chapter we've worked through.
- A shard's principles outgrow it and need to be split or renamed.

Update via the `spec-writer` agent or with explicit user
approval, per `.claude/rules/doc-ownership.md`.
