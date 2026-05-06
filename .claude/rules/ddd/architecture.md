---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- architecture

Architectural-style principles for **how DDD code is organized and
how concerns are layered** inside a bounded context. Distilled
from Vaughn Vernon, *Implementing Domain-Driven Design*,
Chapter 4 ("Architecture").

This shard covers **what architectural style a context uses, and
why**. For *what* a bounded context is, see `bounded-contexts.md`;
for relationships *between* contexts, see `context-maps.md`; for
the index of shards, see `../ddd-principles.md`.

## Vernon's framing in one paragraph

DDD does not prescribe an architecture. Pick architectural styles
the way you pick anything else in DDD: **drive selection by real
quality demands** (latency, testability, scalability,
auditability), not by fashion. Every style in use must be
justifiable against a specific risk it mitigates; if it cannot be
justified, drop it. Vernon walks Layers → DIP → Hexagonal → SOA /
REST → CQRS → EDA → Event Sourcing → Data Fabric, in roughly
ascending complexity, and is emphatic that adding a style you do
not need is itself a risk.

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

The classic four DDD layers -- **user-interface / application /
domain / infrastructure** -- with the Dependency Inversion
Principle applied: high-level layers depend only on abstractions,
and infrastructure implements interfaces defined by the domain.

In practice:

- **User-interface / API** -- thin Adapters that translate the
  external protocol into application calls. No business logic.
- **Application** -- orchestration only. An application service
  loads an Aggregate via a Repository interface, calls one
  command method on it, and returns. If it grows complex, domain
  logic is leaking out of the model.
- **Domain** -- pure: no framework imports, no persistence types,
  no transport types. Owns Aggregates, Value Objects, Domain
  Services, Repository *interfaces*, and Domain Events.
- **Infrastructure** -- persistence implementations, external
  clients, messaging adapters. Implements interfaces from the
  domain. The domain never imports it.

Vernon's "anemic-model" warning (see hub Foundations) applies
most sharply here: a thick application layer that mutates many
fields on a domain object is the symptom. The cure is to push the
behavior onto the Aggregate.

**Apply when:** placing a new file. If it imports from the
domain, it is application or infrastructure. If the domain would
have to import it, the design is inverted -- fix it.

### 3. Hexagonal (Ports and Adapters): one inside, many outsides

A bounded context is **one hexagon**. The inside is the
application + domain. The outside is everything else: clients
that drive the system (HTTP, CLI, message subscribers, schedulers)
and resources the system drives (databases, external APIs,
message buses, caches, LLMs). Each outside concern reaches the
inside through an Adapter that translates between the foreign
shape and the application's API.

A context may have **multiple driving (input) adapters** sharing
the same domain. Adding a new client surface or output mechanism
must not require changing the domain.

Vernon's rule: design the inside per **functional requirements**,
not per the number or shape of adapters.

**Apply when:** adding a new client surface, swapping a backing
store, or wiring a new external service. The change should land
in an Adapter, not in the domain.

### 4. REST / Open Host Service: do not expose the domain directly

When publishing a bounded context's capabilities over HTTP (or
any wire protocol) the wire schema is its **own type**, not the
domain object. Vernon is explicit that **directly exposing the
domain model over REST is brittle** -- every change to a domain
type ripples into every client.

The HTTP layer exposes use-case-shaped resources whose payloads
are *derived from* domain objects but are not them. Wire schemas
live in the API/adapter layer; they are translated from domain
objects, not equated to them.

**Apply when:** adding an endpoint or changing a response shape.
The wire schema is its own type; do not return a domain object
directly.

### 5. Reject the Smart UI

Domain decisions do not live in the user interface. The UI
**renders** domain state and **collects** input; it does not
decide what counts as valid, complete, or authoritative. Anything
that requires invariant knowledge belongs inside the hexagon.

When a presentation surface consumes a Published Language (an
OpenAPI-generated client, an event schema, a wire-format DTO),
treat the consumer-side wrapper as an **input Adapter**: the
foreign vocabulary stops at the wrapper and is translated into
the presentation context's own terms. Do not let wire vocabulary
leak into components.

**Apply when:** any UI change tempted to inspect, compose, or
override a domain decision. Push the decision back to the domain.

### 6. Eventual consistency between contexts; transactional inside one

Inside a single bounded context a single transaction may enforce
invariants. **Across two contexts -- or across two driving
adapters that share a domain but write under different lifecycles
-- do not span a transaction.** Design the reader to tolerate
temporary disagreement (per `context-maps.md` Principle 5).

The domain expression of "the upstream context has nothing to
report yet" is a named state, not an exception (per
`context-maps.md` Principle 6). The domain expression of "two
sources disagree" is a named conflict state, not a thrown error.

**Apply when:** one adapter writes data another adapter will
read, or a downstream context reads from an upstream one. Cross-
surface failure modes get domain names.

### 7. CQRS only when the read shape genuinely diverges from the write shape

Vernon's CQRS guidance: split command and query models only when
view sophistication or scaling demands it. Otherwise it is
accidental complexity.

A spec that proposes CQRS must cite the read-vs-write divergence
(views that cut across multiple Aggregates, scaling asymmetry,
eventual-consistency tolerance) and the failure mode without the
split. Default is **not** CQRS: a single repository serves both
write and read paths.

**Apply when:** a spec proposes a separate read store. Require it
to name the risk and the failure mode without the split.

### 8. Event-Driven across contexts where it removes coupling, not as a default

Vernon's EDA, Pipes-and-Filters, and Long-Running Process
patterns fit when work is naturally distributed and asynchronous
and when synchronous coupling would create timeouts or fragility.

Default to synchronous calls inside a context and across an Open
Host Service. Reach for Domain Events between contexts when the
publisher and subscriber have **different lifecycles** (one is
batch, one is interactive; one is offline, one is online) or when
a single trigger must fan out to multiple independent
subscribers.

If a workflow becomes a multi-step process that must outlive a
single invocation, it becomes a **Long-Running Process** with an
explicit state-tracker Aggregate (Vernon's "executive + tracker"
pattern). The state tracker carries a unique Process identity on
every related Domain Event so out-of-order completions can be
correlated.

**Apply when:** designing how output from one context reaches
another. Prefer a Domain Event + subscriber over direct calls
when lifecycles differ. Apply the Long-Running Process pattern
when a workflow spans more than one invocation.

### 9. Event Sourcing has a high cost of entry; justify it explicitly

Vernon's Event Sourcing trades ORM persistence for an event log
that can be replayed. Its main payoffs are auditability,
debuggability, and "what-if" replay. Its costs are: a dedicated
Event Store, snapshotting to bound replay latency, an almost
mandatory pairing with CQRS for queryability, and a domain model
that rebuilds itself from history rather than holding state
directly.

Adopt Event Sourcing only when the audit / replay requirement
genuinely cannot be met by simpler means (e.g., enriched audit
records, append-only trace tables, periodic snapshots of
aggregate state). A spec proposing Event Sourcing names the
requirement and the simpler alternative it ruled out.

**Apply when:** a spec asks for "audit" or "replay." Reach for
the simpler shape first; escalate to event-sourcing only if the
simpler shape demonstrably cannot carry the requirement.

### 10. Data Fabric / Grid is out of scope by default

Vernon covers in-memory data grids for scaling. Adding a
distributed cache is forbidden by default; if a future spec needs
it, the spec must justify the operational cost against the
quality requirement.

## What this shard does **not** govern

- The exact directory layout inside a service -- that lives in
  the service's own conventions doc. This shard governs the
  *style*; the service doc governs the *names*.
- The HTTP wire schema -- that is `../contracts.md`.
- Cross-context relationships -- that is `context-maps.md`.

## Cross-references

- `../ddd-principles.md` -- DDD hub: index of shards.
- `bounded-contexts.md` -- defining and sizing one context;
  Smart-UI anti-pattern.
- `context-maps.md` -- integration patterns, ACLs, eventual
  consistency, modeling unavailability.
- `../contracts.md` -- HTTP wire-schema discipline; complementary
  to the Hexagonal framing here.
- `../refactoring.md` -- a refactor may not invert a layer
  dependency direction (e.g., importing infrastructure from
  domain) without authorization.
