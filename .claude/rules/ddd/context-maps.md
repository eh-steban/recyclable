---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- context maps

Strategic-design principles for **relationships between bounded
contexts**: integration patterns, upstream/downstream direction,
translation, and cross-context state. Distilled from Vaughn
Vernon, *Implementing Domain-Driven Design*, Chapter 3 ("Context
Maps," PDF pp. 79--96).

This shard covers **how contexts interact**. For what a bounded
context *is* and how to size one, see `bounded-contexts.md`. For
the project-level index and the catalog of contexts we currently
recognize, see `../ddd-principles.md`.

## What a context map is

A Context Map captures the **existing terrain**: the bounded
contexts that exist today and the integration relationships
between them. It is not an enterprise architecture diagram, not a
deployment topology, not a future-state vision. It is a tool for
two purposes: (1) giving a team shared vocabulary about what is
actually wired up to what, and (2) forcing decisions about
**which integration pattern** governs each relationship.

The most detailed expression of a context map is the source code
of the integrations themselves. Diagrams are summaries; the code
is the truth.

## Principles

### 1. Map the existing terrain before drawing new lines

When proposing a boundary or a new integration, first describe
what is **already there** -- modules, tables, prompts, routes --
and the relationships among them. Speculative future contexts go
in a separate "where this is heading" section. Vernon: *a
Context Map captures the present, not the imagined future.*

**Apply when:** writing a new spec, splitting a module, proposing
a new service, or adding an integration with an external system.

### 2. Keep boundaries permeable but vetted

A boundary is not a wall. Things cross it -- but only on terms
the inside controls. Any value entering a context from outside
(HTTP request, ingestion source, LLM output, another module's
API) must be translated into the local model at the boundary,
never used directly downstream.

**Apply when:** adding any code that consumes data from outside
its context. The translation step is mandatory.

### 3. Pick one integration pattern explicitly per relationship

Vernon names several organizational patterns. We use a small
subset. Whenever two contexts integrate, the spec **must** name
which pattern is in force.

- **Open Host Service + Published Language.** Default for the
  backend → frontend boundary. The FastAPI HTTP API is the Open
  Host Service; the OpenAPI spec + generated TS client is the
  Published Language.
- **Anticorruption Layer (ACL).** Default for ingestion. Every
  external source (jurisdiction website, PDF, third-party API) is
  foreign; the worker translates into knowledge-base terms at
  ingest time and never lets foreign vocabulary reach the domain.
  The LLM is also foreign -- validators are an ACL over LLM output.
- **Customer-Supplier.** Use between the user-path context
  (customer) and the knowledge-base context (supplier) when
  retrieval needs shape ingestion priorities. Make the request
  explicit in a spec, not implicit in code.
- **Separate Ways.** Use when two areas have no real
  relationship. Prefer this over speculative integration. Cheaper
  to merge later than to split later.
- **Shared Kernel.** Avoid by default. Only acceptable when a
  tiny, stable set of types is genuinely shared and the cost of
  duplication exceeds the cost of coordinated change. If used,
  mark the shared module explicitly and document its change
  protocol in the spec.
- **Conformist.** Acceptable only when integrating with an
  external system we cannot influence (e.g., a government data
  portal). Inside our own code, conformism between contexts is a
  smell.
- **Big Ball of Mud.** Name it when we see it. Do not extend it.
  Wrap it in an ACL.

Patterns we do **not** use as a matter of course: Partnership
(we are one team), Published Language as a bespoke XML schema (we
publish JSON via OpenAPI).

### 4. Direction of dependency: upstream / downstream is a design decision

For every integration, label which side is upstream (provides
state or behavior) and which is downstream (consumes it). The
downstream context must:

- never assume the upstream context is available without an
  explicit fallback (refusal, retry, eventual consistency);
- never share the upstream's database;
- never let upstream vocabulary leak past the ACL.

**Concrete invariants in this repo:**

- Frontend (Presentation) is **downstream** of the backend HTTP
  API. The frontend holds no schema knowledge; it consumes the
  generated TS client.
- The user-path retrieval context is **downstream** of the
  knowledge-base context. Retrieval reads, ingestion writes.
- The ingestion worker is **downstream** of external sources and
  the LLM. Both are wrapped in ACLs.

### 5. Prefer eventual consistency across contexts; transactional consistency inside one

Inside a single bounded context, a single transaction may enforce
invariants. Across two contexts, do not span a transaction. If
state must propagate, use a Domain Event or an explicit
synchronization step, and design the receiver to tolerate
temporary disagreement.

**Apply when:** the worker writes data the user path will read,
or the user path needs to trigger ingestion.

### 6. Make unavailability an explicit state, not an exception

When a downstream context depends on an upstream one and the
upstream might be unavailable, model the unavailability as a
domain state, not a thrown exception leaking to the user.

Vernon's example: a `DiscussionAvailability` enum with
`ADD_ON_NOT_ENABLED, NOT_REQUESTED, REQUESTED, READY`. Our
analogue: a retrieval result that has no grounding evidence
returns a refusal state -- a first-class outcome -- rather than
a 500.

**Apply when:** any cross-context call could fail or return
nothing. The "nothing" case must be a named domain value.

### 7. Translation maps are code, not magic

Every ACL needs a concrete translation: foreign shape → local
shape. That mapping lives in code (a function, an Adapter class)
inside the downstream context, not in the upstream system, not
in shared utilities, and not implicit in serialization.

**Apply when:** consuming the generated TS client in the
frontend, or consuming an ingestion source in the worker.

### 8. Keep the context map cheap

Vernon is emphatic: avoid ceremony. We do not maintain a separate
"context map document" -- the map lives in the hub
(`../ddd-principles.md`) plus the candidate-contexts list there,
refined in specs as we learn. If a discussion needs a diagram,
draw it in the spec it belongs to. Don't build infrastructure to
keep diagrams in sync with code; the code is the truth.

## Cross-references

- `../ddd-principles.md` -- DDD hub: index of shards, project's
  candidate contexts, classification.
- `bounded-contexts.md` -- principles for *defining* a single
  bounded context.
- `../contracts.md` -- the *shape* discipline for HTTP-boundary
  contracts; complementary to the *integration pattern* choice
  here.
- `../refactoring.md` -- a refactor may not move or rename an
  integration surface (the boundary between two contexts) without
  updating all dependents; that surface is a public contract in
  this sense even when both sides are internal Python.
