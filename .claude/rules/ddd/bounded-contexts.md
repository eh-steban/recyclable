---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- bounded contexts

Strategic-design principles for **defining and sizing bounded
contexts** in this repo. Distilled from Vaughn Vernon,
*Implementing Domain-Driven Design*, Chapter 2 ("Domains,
Subdomains, and Bounded Contexts," PDF pp. 51--78).

This shard covers **what a bounded context is and how to draw
one**. For relationships *between* contexts (integration patterns,
upstream/downstream, ACLs, translation), see
`context-maps.md`. For the project-level index and the catalog of
contexts we currently recognize, see `../ddd-principles.md`.

## Domain, Subdomain, Bounded Context

Vernon distinguishes three terms that are easy to conflate.
Each does a different job:

- **Domain** -- what the business does and the world it operates
  in. For us: helping the public answer recycling questions with
  grounded, source-cited information.
- **Subdomain** -- a logical area of the domain. A *problem-space*
  concept: it names a chunk of business reality we must address,
  regardless of how (or whether) we have built software for it.
- **Bounded Context** -- an explicit boundary inside which a
  single model and a single Ubiquitous Language are consistent.
  A *solution-space* concept: it is the software realization.

Default goal: **one subdomain maps to one bounded context.** Split
or merge only when the language and model genuinely demand it.

### Core, Supporting, Generic

Not all subdomains deserve equal investment. Vernon's
classification:

- **Core Domain** -- where the business must excel. Highest
  priority, best people, most attention to model quality.
- **Supporting Subdomain** -- essential but specialized; not the
  differentiator.
- **Generic Subdomain** -- required for the overall solution but
  nothing about it is special to us; could in principle be
  bought, swapped, or stubbed.

For the project's current Core/Supporting/Generic read of each
candidate context, see the hub: `../ddd-principles.md`.

### Problem-space vs solution-space discipline

When writing a spec or kata:

- The **problem-space** section names subdomains. It explains
  *what areas of the business are in play* and *why* they matter.
  It does not commit to a software shape.
- The **solution-space** section names bounded contexts. It
  commits to which model(s) we will build, how they integrate,
  and what language each one uses.

Don't conflate them. A problem-space discussion that jumps
straight to file paths has skipped a step; a solution-space
discussion that never names the subdomain it serves has skipped a
different one.

## What a bounded context is, here

A **bounded context** is an explicit boundary inside which a
single model and a single Ubiquitous Language are consistent.
Outside that boundary, the same word may mean something different,
and that is fine -- as long as the translation between contexts is
explicit.

Each bounded context owns:

- Its **language** -- the terms used in code, tests, prompts, and
  docs inside the boundary.
- Its **model** -- the domain types, invariants, and behaviors.
- Its **integration surface** -- how other contexts may talk to it.

## Principles

### 1. Name every context, and put the name in the Ubiquitous Language

Every bounded context we recognize must have a name that appears
in: the spec, the relevant directory or package, the code's type
and module names, and ordinary conversation. If a context cannot
be named in one short noun phrase, the boundary is probably
wrong.

**Form:** `{Name-of-Model} Context` -- e.g., *Knowledge Base
Context*, *Retrieval Context*, *Ingestion Context*,
*Presentation Context*. The pattern comes straight from Vernon
(Ch. 2, "Naming a Bounded Context") and exists so the boundary's
name is the same in conversation, code, and docs.

**Forbidden:** generic names like `core`, `shared`, `common`, or
`utils` for anything that holds domain meaning. A context named
`utils` is not a context.

### 2. The boundary contains more than the model

A bounded context is the model **plus everything built to support
it**: the database schema (when we own it), the HTTP routes that
expose it, the application services that orchestrate it, the
prompts and validators that wrap LLM calls inside it, and the
tests that pin its behavior down. All of these live inside the
boundary because they speak the same Ubiquitous Language.

What this means concretely:

- The Postgres schema for jurisdictions, materials, rules,
  sources, etc. lives inside the **Knowledge Base Context**.
  Migrations, repositories, and SQLAlchemy models are part of it.
- The Sonnet prompts, retrieval composition, and grounding
  validator live inside the **Retrieval Context** -- they are not
  "infrastructure" smuggled in alongside the domain; they are
  domain logic for that context.
- The Next.js routes, server components, and the generated TS
  client wrappers live inside the **Presentation Context**. The
  *generation* of the client is a translation step at the
  boundary; the *use* of the client is internal to Presentation.

Reject the **Smart UI anti-pattern** (Vernon, Ch. 2): do not put
domain decisions in the user interface. The frontend renders and
collects -- it does not decide what counts as a grounded answer.

### 3. Right-size by language, not by deployment

> "A Bounded Context should be as big as it needs to be in order
> to fully express its complete Ubiquitous Language."
> -- Vernon, Ch. 2

We do not split a context to make deployment easier, to give
developers smaller tasks, or to fit a framework's project
structure. Those motives produce *technical* boundaries that
fragment the language.

We do not merge two contexts because their code happens to live
in the same Python package. Co-location is not coherence.

**Triggers for re-evaluating size:**

- A single term has two incompatible meanings inside the same
  context (probably *too big* -- split).
- A simple change requires touching code in two contexts that
  always change together (probably *too small* -- merge, or
  rethink the boundary).
- The context's name no longer covers what's inside it.

### 4. One Subdomain, one Bounded Context (default)

Default to a one-to-one mapping: one cohesive area of the
business gets one bounded context. Do not split a subdomain into
two contexts unless there is a concrete reason (different team,
different lifecycle, different language, hostile model conflict).
Do not merge two subdomains into one context for convenience.

**Apply when:** designing or revisiting module structure inside
`backend/app/` or `frontend/app/`.

### 5. Same word, different meaning is allowed -- duplicated meaning is not

Two contexts may legitimately use the same English term for
different model concepts (Vernon's examples: an `Account` in a
banking context vs. a literary context; a `Book` at different
stages of its publishing lifecycle). For us: a `Source` in
ingestion is a URL + extraction provenance; a `Source` shown to
the user on a rule page is a citation reference.

This is fine **only** if the two are distinct types in distinct
modules with an explicit translation between them.

What is **not** allowed: copying a type across contexts so that
two modules hold "the same" definition that will drift. That's a
Shared Kernel by accident, and it always rots.

## Cross-references

- `../ddd-principles.md` -- DDD hub: index of shards, project's
  candidate contexts, classification table.
- `context-maps.md` -- principles for relationships *between*
  bounded contexts.
- `../contracts.md` -- the *shape* discipline for HTTP-boundary
  contracts; complementary to the *why* discipline here.
- `../../backend/CLAUDE.md` -- backend DDD layering (domain /
  application / infrastructure / api). Layering is *within* a
  context; bounded contexts are the larger boundary.
