---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- architecture

Architectural-style principles for **how DDD code is organized and
how concerns are layered** in this repo. Distilled from Vaughn
Vernon, *Implementing Domain-Driven Design*, Chapter 4
("Architecture," PDF pp. 97--132).

This shard covers **what architectural style each context uses, and
why**. For *what* a bounded context is, see `bounded-contexts.md`;
for relationships *between* contexts, see `context-maps.md`; for the
project-level index, see `../ddd-principles.md`.

## Vernon's framing in one paragraph

DDD does not prescribe an architecture. Pick architectural styles
the way you pick anything else in DDD: **drive selection by real
quality demands** (latency, testability, scalability,
auditability), not by fashion. Every style in use must be
justifiable against a specific risk it mitigates; if it can't be
justified, drop it. Vernon walks Layers → DIP → Hexagonal → SOA /
REST → CQRS → EDA → Event Sourcing → Data Fabric, in roughly
ascending complexity, and is emphatic that adding a style you
don't need is itself a risk.

## Principles

### 1. Architecture is risk-driven, not résumé-driven

Adopt an architectural style only when a concrete quality
requirement (latency, testability, scaling, audit, isolation)
demands it. A spec that proposes CQRS, Event Sourcing, or a Saga
must name the risk it mitigates and why a simpler shape will not
do.

**Apply when:** writing or reviewing any spec that introduces a
new architectural pattern. If the spec cannot answer "what fails
without this?", remove the pattern.

### 2. Use Layers + DIP as the default inside a bounded context

Inside the backend we use the classic four DDD layers --
**user-interface / api / application / domain / infrastructure** --
with the Dependency Inversion Principle: high-level layers depend
only on abstractions, and infrastructure implements interfaces
defined by the domain.

In practice for `backend/`:

- `app/api/` -- FastAPI routes; thin Adapters that translate HTTP
  into application calls. No business logic.
- `app/application/` (or whatever name `backend/CLAUDE.md` uses for
  application services) -- orchestration only. An application
  service loads an Aggregate via a Repository interface, calls one
  command method on it, and returns. If it grows complex, domain
  logic is leaking out of the model.
- `app/domain/` -- pure Python, no framework imports. Owns
  Aggregates, Value Objects, Domain Services, Repository
  *interfaces*, and Domain Events. No SQLAlchemy, no Pydantic, no
  HTTP types.
- `app/infra/` -- SQLAlchemy models, Alembic migrations,
  Repository *implementations*, external clients. Implements
  interfaces from `domain/`. Never referenced from `domain/`.

Vernon's "anemic-model" warning (see hub Foundations) applies most
sharply here: a thick application layer that mutates many fields
on a domain object is the symptom. The cure is to push the
behavior onto the Aggregate.

**Apply when:** placing a new file. If it imports from
`domain/`, it is application or infrastructure. If `domain/` would
have to import it, the design is inverted -- fix it.

### 3. The backend is one Hexagon with two driving adapters

The backend hosts **two driving (input) adapters** -- the FastAPI
HTTP service and the ingestion worker -- both of which depend
inward on the same domain. The domain is the **inside** of the
hexagon. Everything outside (HTTP, the LLM, Postgres, external
sources, Vercel revalidation) reaches the inside through an
Adapter.

Driven (output) adapters in this repo:

- **Postgres** -- SQLAlchemy repositories implementing
  `domain/` interfaces.
- **Sonnet (user path) and Opus (worker path)** -- LLM calls
  wrapped behind a domain port; the validator is part of the
  Adapter, not the domain.
- **External sources (worker)** -- HTTP fetchers, PDF extractors,
  jurisdiction-portal clients. Each is an ACL into the
  knowledge-base language (see `context-maps.md` Principle 7).
- **Cache invalidation / revalidation hooks** -- the worker emits
  a Domain Event on apply; the HTTP layer translates that into a
  Vercel revalidation call.

Vernon's rule: design the inside per **functional requirements**,
not per the number or shape of adapters. Adding a new client or
output mechanism must not require changing the domain.

**Apply when:** adding a new ingestion source, swapping LLMs, or
exposing a new client surface. The change should land in an
Adapter, not in `domain/`.

### 4. HTTP is the Open Host Service; TS client is the Published Language

Per `context-maps.md` Principle 3 the backend → frontend
integration is Open Host Service + Published Language. In Vernon's
Ch. 4 framing this is also where REST sits: the FastAPI routes are
Adapters that translate HTTP into application calls; the OpenAPI
spec + generated TS client is the published interface.

Vernon is explicit that **directly exposing the domain model over
REST is brittle** -- every change to a domain type ripples into
every client. We follow his preferred approach: the HTTP layer
exposes use-case-shaped resources whose payloads are derived from
domain objects but are not them. Pydantic response models in
`app/api/` are the wire schema; they are translated from domain
objects, not equated to them.

**Apply when:** adding an endpoint or changing a response shape.
The wire schema is its own type; do not return a domain object
directly.

### 5. Reject the Smart UI; the frontend is a presentation Adapter

Domain decisions do not live in the frontend. "Did this answer
meet the grounding bar?" is decided in the backend's Retrieval
Context and surfaced as a refusal state in the response payload.
The frontend renders the state; it does not compute it.

The generated TS client + thin wrappers in `frontend/lib/` are the
**input Adapter** translating from the Published Language to the
Presentation Context's local language. Treat them like an ACL: do
not let response-shape vocabulary leak past the wrapper into
components.

**Apply when:** any frontend change tempted to inspect, compose,
or override the backend's grounding/refusal logic. Push the
decision back to the backend.

### 6. Eventual consistency between the two driving adapters

The HTTP service (Retrieval) reads. The worker (Ingestion)
writes. Across that surface we follow `context-maps.md`
Principle 5: do not span a transaction; design the reader to
tolerate temporary disagreement.

The domain expression of "we don't yet have grounded evidence" is
a **refusal**, not a 500 -- per `context-maps.md` Principle 6.
The domain expression of "ingestion produced a conflict" is a
named conflict-state row, not an exception escaping to the user.

**Apply when:** the worker writes data the HTTP path will read,
or vice versa. Cross-surface failure modes get domain names.

### 7. CQRS only if the read shape genuinely diverges from the write shape

Vernon's CQRS guidance: split command and query models only when
view sophistication or scaling demands it. Otherwise it is
accidental complexity.

For us, today, **we do not adopt full CQRS.** SQLAlchemy
repositories serve both write (ingestion) and read (retrieval +
SSG page builds). We may, in the future, justify a denormalized
read store for SSG pages or for the `/ask` retrieval index --
that decision belongs in a spec, must name the risk it mitigates
(page build latency, retrieval recall, etc.), and is not part of
the default architecture.

**Apply when:** a spec proposes a separate read store. Require it
to cite the read-vs-write divergence and the failure mode without
the split.

### 8. Event-Driven across contexts where it removes coupling, not as a default

Vernon's EDA, Pipes-and-Filters, and Long-Running Process patterns
fit when work is naturally distributed and asynchronous and when
synchronous coupling would create timeouts or fragility.

For us, the natural EDA seam is **ingestion-apply → cache
revalidation → eval rerun**. An ingestion-apply emits a Domain
Event; downstream subscribers (Vercel revalidation, eval
re-runs, alerting on grounding regressions) react. We do **not**
event-drive the user path: the `/ask` loop is synchronous,
deterministic, and Sonnet-bounded by design (see hub: "Sonnet on
the user path, Opus on the research path").

If a future ingestion workflow becomes a multi-step research loop
that must outlive a single worker invocation, *then* it becomes a
Long-Running Process with an explicit state-tracker Aggregate
(per Vernon's "executive + tracker" pattern). Today, the worker
runs one source per invocation and the state tracker is the
ingestion trace row.

**Apply when:** designing how worker output reaches the HTTP path
or the frontend. Prefer a Domain Event + subscriber over direct
calls. Apply also when proposing multi-step ingestion -- the
state-tracker pattern is the model.

### 9. Event Sourcing is not adopted; ingestion traces serve the audit need

Vernon's Event Sourcing trades ORM persistence for an event log
that can be replayed. Its main payoffs are auditability,
debuggability, and "what-if" replay.

For us, the audit need is real (every assistant claim cites a
source; every ingestion change must be traceable to its source
document and extraction step) but it is met by **ingestion trace
rows**, not by event-sourcing the whole domain. Trace rows record
source, extractor, model, prompt version, validator outcome, and
applied diff -- enough to reconstruct *why* a knowledge-base row
looks the way it does.

We do not Event-Source Aggregates. If we ever need full replay --
e.g., to re-run all extractions under a new validator -- the
trace rows plus stored source documents are the replay input,
not a domain Event Store.

**Apply when:** a spec asks for "audit" or "replay." Reach for
trace-row enrichment first; escalate to event-sourcing only if
trace rows demonstrably can't carry the requirement.

### 10. Data Fabric / Grid is out of scope

Vernon covers in-memory data grids (GemFire, Coherence) for
scaling. We deploy Postgres (Neon) on a serverless tier for the
backend and Vercel SSG + edge cache for the frontend. Adding a
distributed cache is forbidden by default; if a future spec needs
it, the spec must justify the operational cost against the
quality requirement.

## What this shard does **not** govern

- The exact directory layout inside `backend/app/` -- that is in
  `backend/CLAUDE.md`. This shard governs the *style*; that file
  governs the *names*.
- The HTTP wire schema -- that is `../contracts.md`.
- Cross-context relationships -- that is `context-maps.md`.

## Cross-references

- `../ddd-principles.md` -- DDD hub: index of shards, candidate
  contexts, classification.
- `bounded-contexts.md` -- defining and sizing one context;
  Smart-UI anti-pattern.
- `context-maps.md` -- integration patterns, ACLs, eventual
  consistency, modeling unavailability.
- `../contracts.md` -- HTTP wire-schema discipline; complementary
  to the Hexagonal framing here.
- `../../backend/CLAUDE.md` -- concrete layering inside
  `backend/app/` (domain / application / infra / api). The
  *naming* lives there; the *style* lives here.
- `../refactoring.md` -- a refactor may not move code across a
  layer boundary in a way that inverts the dependency direction
  (e.g., importing infra from domain) without authorization.
