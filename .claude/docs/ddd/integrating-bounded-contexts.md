# DDD shard -- integrating bounded contexts

How to wire two bounded contexts together at runtime so that the
relationship from `context-maps.md` shows up in code without smuggling
one context's model into the other. Distilled from *Implementing
Domain-Driven Design*, Chapter 13 ("Integrating Bounded Contexts").

This shard covers **the integration mechanism** -- wire shape,
translation, autonomy under failure, eventual consistency between
contexts. For the *kind of relationship* (Open Host Service,
Anticorruption Layer, Conformist, Shared Kernel, Customer-Supplier,
Separate Ways), see `context-maps.md`. For the events that flow on the
wire, see `domain-events.md`. For the index of shards, see
`principles-hub.md`.

## What integration is, here

Two bounded contexts integrate when one needs information or a behavior
that lives in the other. The Context Map names the relationship; this
shard governs how that relationship is *implemented* -- the actual code
that crosses the boundary.

> "Define a protocol that gives access to your subsystem as a set of
> services. Open the protocol so that all who need to integrate with you
> can use it. Enhance and expand the protocol to handle new integration
> requirements." -- Evans, on Open Host Service, quoted in Ch. 13

There are three common implementation shapes:

- **RPC** -- one context's API is called as if it were a local
  procedure. Easy to reason about; lowest autonomy. The caller fails
  when the callee is down.
- **REST over HTTP** -- resources identified by URI, manipulated via
  GET/PUT/POST/DELETE. A natural Open Host Service. The caller still
  needs the callee online at request time, but the protocol is open and
  versioning-friendly.
- **Messaging** -- pub/sub or queues, often carrying Domain Events as
  notifications. Highest autonomy: as long as the broker is up, sender
  and receiver do not have to be online together.

File-share and shared-database integration are dismissed as cures
worse than the disease ("doing so could make you old before your
time"); RPC is to be avoided where autonomy matters.

The choice between these is not aesthetic; it is a function of how much
*autonomy* the consuming context needs and how *coupled* the two
deployments may be (Principle 2).

## Principles

### 1. Cross-context calls are not in-process calls

A call that crosses a bounded-context boundary crosses a
*distributed-systems* boundary, even if both contexts run on the same
host today. Treat it that way from the start. Restate the classic
fallacies of distributed computing as principles to design around:

- The network is not reliable.
- There is always some latency, sometimes a lot.
- Bandwidth is not infinite.
- The network is not secure.
- Network topology changes.
- Knowledge and policies are spread across multiple administrators.
- Network transport has cost.
- The network is heterogeneous.

The most common failure mode is treating a remote call like a local
method call: a single naive RPC that times out then cascades through
the calling stack into a context-wide outage. Cross-boundary code must
have an explicit story for timeout, partial failure, retry, and the
caller's behavior when the callee is unreachable.

**Apply when:** writing the first call between two contexts, or
introducing a new dependency between processes. State the failure mode
in the spec before writing the client.

### 2. Choose the integration mechanism by the autonomy you need

Three knobs:

- **Caller-online-required?** RPC and REST require the callee to be up
  when the call is made. Messaging does not (the broker is the
  mediator).
- **Latency tolerance.** Messaging trades latency for autonomy: a
  message may sit in a queue for seconds or minutes before processing.
  REST/RPC are roughly real-time but fail when latency spikes.
- **Coupling shape.** RPC ties the consumer to the producer's *method
  signatures*. REST ties it to a *resource shape*. Messaging ties it to
  an *event vocabulary*. Each is harder to change in roughly that
  order.

Default rules of thumb:

- If the consumer must keep working when the producer is down, use
  messaging.
- If the consumer's use case is request/response with a short SLA and
  the producer is available enough, use REST.
- If you find yourself reaching for RPC, ask whether REST gives you
  90 % of the value with looser coupling -- it usually does.
- Even with REST or RPC, the consumer can simulate temporal decoupling
  with timers or its own message queue: "reach out only when a tick
  fires," with backoff.

**Apply when:** designing a new cross-context interaction. Pick the
mechanism deliberately; a wrong choice survives for years because
flipping it later is a rewrite.

### 3. Cross the boundary through a Published Language, not shared classes

The cheapest way to integrate two contexts in the same monorepo is to
share the producer's serialization classes (or interfaces, or a
generated client jar). Resist this. Sharing a type across a context
boundary forms a Shared Kernel whether you call it that or not, and the
slope to "everyone uses each other's domain objects" is steep.

The alternative is a **Published Language**: a media-type
specification, a JSON schema, an OpenAPI document -- some external
artefact that defines the wire shape independently of either side's
in-memory types. Producers serialize *to* the spec; consumers read *from*
the spec into their own local types.

Trade-offs:

- Lose: navigation through typed property accessors, IDE completion on
  the wire shape, "free" deserialization into a domain object.
- Gain: producer and consumer can evolve their internal types
  independently, the consumer never tempted to call a method that
  belongs to the producer's model, no recompile-and-redeploy chain
  through every consumer when the producer reshapes a field.

A reader-style helper (`NotificationReader`, a JSON path / dot-property
extractor) makes Published-Language consumption ergonomic without
deploying classes everywhere.

**Apply when:** designing the wire format between two contexts, or
deciding whether to publish a generated client. Default to the spec; do
not publish a client jar / npm package that exposes the producer's
internal types as if they were local. Generated *types from a spec* are
fine; generated types *re-exporting the producer's domain* are not.

### 4. Open Host Service exposes use cases, not Aggregates

When a context offers itself as an Open Host Service via REST, the
temptation is to expose the domain model directly: `GET /tenants/{id}`
returns the full `Tenant` Aggregate, `GET /tenants/{id}/users` returns
the users tree, and so on. That is not an Open Host Service. It is a
**Shared Kernel** or **Conformist** relationship in disguise -- every
consumer is now coupled to the producer's Aggregate shape and must
follow its evolution.

A real Open Host Service publishes resources *shaped to integrators'
use cases*. Not "give me the user," but "is user X in role Y for
tenant Z?":

```http
GET /tenants/{tenantId}/users/{username}/inRole/{role}
→ 200 + minimal representation, or 204 No Content
```

The use case dictates the resource. New use cases earn new resources.
Old resources stay stable because their inputs and outputs are framed
by *the integrator's* question, not the producer's storage layout.

**Apply when:** designing an HTTP API that other contexts will consume.
For each endpoint, name the integrator's use case in one sentence; if
the answer is "they want our Aggregate," redesign.

### 5. Translate at the edge with an Anticorruption Layer

When the consuming context calls or listens to another context, the
foreign data must be translated into the consumer's Ubiquitous Language
*before* it reaches the consumer's domain model. The classic shape:

- A **Service-shaped facade** in the consumer's language, in the domain
  layer as a Separated Interface. The consumer's Application Service
  calls `collaboratorService.authorFrom(tenant, identity)` and receives
  back a local `Author` Value Object -- it never sees the foreign
  `User` representation.
- An **Adapter** in the infrastructure layer that knows the wire
  protocol (HTTP client, message listener, RPC stub). It speaks the
  foreign Published Language.
- A **Translator** that maps Published-Language fields to local types.
  No domain-layer code calls the wire format directly.

The pattern applies symmetrically to messaging: the message *listener*
is the Adapter, the *reader* (`NotificationReader`) plus a translator
produces local commands or local Value Objects, and the listener
dispatches into a local Application Service exactly as if the call had
arrived through any other surface.

A Repository may stand in for the Service-shaped facade when the
foreign call returns a *local Aggregate to be reconstituted*. For Value
Objects, prefer a plain Service-shaped facade -- a "Repository" that
manufactures Value Objects misuses the pattern.

**Apply when:** a consuming context is about to receive foreign data
(REST response, message payload, RPC result). Three artefacts -- facade
in domain, adapter and translator in infrastructure -- before the
domain layer ever sees a foreign byte.

### 6. Decide between mirroring and look-up; carry the consequence

When a consumer needs information that lives in another context, there
are two paths:

- **Hold a copy.** Materialize a local Value Object or Entity from
  events received over messaging or representations fetched over REST.
  Subsequent reads do not touch the network. The consumer is more
  autonomous.
- **Look up on demand.** Each read calls the producer. The data is
  always fresh, but the consumer is coupled to the producer's
  availability and response time.

The trade-off is between **autonomy + freshness latency** (hold a copy)
and **freshness + availability coupling** (look up). Two refinements
sharpen the decision:

- If the local copy is a **Value Object** (immutable, replaceable),
  the cost is low: never sync, just replace the Value the next time
  the question is asked. The Collaboration context's `Author` /
  `Moderator` / `Owner` Values are this shape.
- If the local copy is part of an **Entity / Aggregate** that holds
  derived state and history, the cost is high: now the consumer owns
  the responsibility to react to *every* foreign event that could
  invalidate the copy (see Principle 7).

Default bias: **minimize duplication across contexts**. Share identity,
share use-case-specific Values, but do not mirror entire foreign
Aggregates without a clear reason. SLA pressure ("we cannot afford a
remote call on every read") is a legitimate reason; "it felt
convenient" is not.

**Apply when:** a consumer needs information from a producer. Name the
shape (Value Object vs Entity), enumerate the foreign events that
could invalidate the local copy, and decide whether the consumer is
prepared to handle all of them. If not, fetch on demand.

### 7. Engineer for out-of-order and at-least-once delivery from day one

Any non-trivial messaging mechanism delivers *at least once* and *not
necessarily in order*. Both must be designed for, not patched in
later when the bug shows up in production.

- **Stamp every command with `occurredOn`.** When the consumer applies
  a foreign event to a local Aggregate, it passes the event's
  occurrence timestamp into the Aggregate method. The Aggregate -- not
  the listener -- decides whether the new fact is newer than what it
  already knows.
- **Make handlers idempotent.** A redelivered event must not corrupt
  state. The simplest idempotency check is "is this Aggregate already
  in the state this event would produce?"; the next-simplest is a
  per-attribute change tracker that records when each attribute was
  last updated and refuses out-of-order updates.
- **Track per-attribute change times when ordering matters.** If
  events `UserAssignedToRole` and `UserUnassignedFromRole` can arrive
  in either order, a single "last updated" timestamp is not enough --
  one event toggling the wrong way will leave the consumer stuck. Each
  independently-toggleable attribute needs its own `*ChangedOn`.
- **Treat the change tracker as an implementation detail of the
  Aggregate.** It does not belong to the Ubiquitous Language; clients
  never see it; only the `occurredOn` parameter on the Aggregate's
  command methods leaks out.

**Apply when:** building any consumer that listens to events over a
messaging backbone. Every command that mutates a mirrored attribute
takes `occurredOn`; every Aggregate method that uses it gates the
mutation by the per-attribute change record.

### 8. A Long-Running Process needs a tracker, retries, and a time-out

A multi-step interaction across contexts ("create a Product, then
request its Discussion in the Collaboration context, then attach the
Discussion id back to the Product") is a Long-Running Process. It
spans the time between the first event and the last confirmation, and
during that window any of the legs can fail or be delayed.

The pattern:

- The **process state** lives on the originating Aggregate (e.g. a
  `discussionInitiationId` on `Product`). The Aggregate carries the
  state machine -- `REQUESTED`, `READY`, `FAILED`.
- A **Time-Constrained Process Tracker** is a separate small Aggregate
  in a technical Subdomain (reusable across processes) that watches
  one process. It knows the allowable duration, the retry interval,
  the total retries permitted, and the event class to publish on
  retry / time-out.
- A **periodic timer** (background job, scheduled task) wakes up,
  asks the tracker repository for "all timed-out trackers," and tells
  each to publish its `ProcessTimedOut` subclass event.
- A **listener** for that event subclass dispatches to the
  Application Service, which decides whether this is a retry (re-issue
  the original command) or a full time-out (compensate -- mark the
  Aggregate `FAILED`, send an alert, etc).
- When the process completes successfully, the originating Aggregate
  transitions to its terminal state and the tracker is marked
  `completed()`; the tracker is no longer selected for retries.

The tracker lives in the *consumer / orchestrator* context, not in the
producer. The orchestrator owns the process; the producer just answers
commands.

**Apply when:** an interaction across contexts spans more than one
event-round-trip and must complete within a bounded time. Add a
tracker, a periodic check, and a `ProcessTimedOut` subclass before the
happy-path code.

### 9. When the process has multiple gates, model it as a state machine

A single boolean "completed" check is not enough when several
independent confirmations must arrive before the process is done. In
that case the process itself is an Aggregate (or extends an
`AbstractProcess` base), and a `completenessVerified()` predicate
returns true only when *all* required steps have been confirmed.

Each step's command method on the Process Aggregate (a) sets the
relevant flag, (b) calls the framework's `completeProcess(...)` which
(c) marks the Process complete *only if* `completenessVerified()`
returns true. The same tracker mechanism (Principle 8) still
supervises retries and time-outs around the whole machine.

This avoids three failure modes:

- Premature completion (one leg arrives, process marks itself done,
  the other legs are dropped on the floor).
- Stuck completion (a confirmation never arrives, the process never
  realizes, the tracker is the only thing that eventually fires).
- Completion-state ambiguity (the team has to guess which Aggregate
  owns the truth about whether the process finished).

**Apply when:** the cross-context interaction involves more than one
confirmation event before completion is real. Promote the Process from
"a flag on the originating Aggregate" to its own state machine.

### 10. Plan for the messaging backbone -- and your own context -- being down

Two failure modes that are not the network or the producer:

- **Messaging mechanism unavailable.** Publishers cannot send. Back
  off attempts (30 s -- 1 min between retries) until one send
  succeeds. If the context has an Event Store, queued events
  accumulate locally and drain when the broker returns. Without an
  Event Store, an outage during publish drops the event -- a strong
  argument for the Store.
- **Consumer context unavailable.** Durable queues / exchanges fill
  with undelivered messages. When the consumer comes back, it must
  drain the backlog before it is current. Plan for that backlog --
  consumer auto-resubscribe, redundant consumer nodes, brief
  downtime windows, capped backlog age.

Two operational obligations follow:

- **Verify auto-resubscribe behavior of the messaging client.** If the
  client does not reconnect-and-resubscribe automatically, the context
  silently stops receiving events after the first broker hiccup. That
  is a kind of eventual consistency that breaks the system without
  surfacing an error.
- **Know the recovery cost.** A long enough consumer outage produces a
  backlog whose drain time is part of the recovery time, not separate
  from it. Capacity-plan for it; do not assume "messages are durable,
  so a backlog is fine."

**Apply when:** specifying or operating a context that depends on
messaging. The unavailable-broker and unavailable-consumer paths are
explicit in the runbook before launch.

## What this shard does **not** govern

- **Which Context-Map relationship to choose.** Open Host Service,
  Anticorruption Layer, Conformist, Customer-Supplier, Separate Ways
  -- those are governed by `context-maps.md`. This shard governs how
  the chosen relationship is *coded*.
- **Domain Event identity, payload shape, and the
  one-Aggregate-per-transaction rule.** Those are governed by
  `domain-events.md` and `aggregates.md`; this shard takes them as
  given and shows how Events flow on the wire.
- **HTTP contract specifics.** Header conventions, error codes, OpenAPI
  versioning, security scheme -- those are governed by `../../rules/contracts.md`
  and `architecture.md`. This shard governs what crosses the wire and
  why, not how to spell HTTP.
- **Messaging-broker internals.** RabbitMQ exchanges, Kafka partitions,
  SQS queues, retry policies on the broker side -- those are
  infrastructure concerns. This shard governs what the consumer and
  producer do *in the domain layer* around the broker.
- **Authentication, authorization, tenancy at the boundary.** A
  cross-context call carries identity, tenant, and authorization; the
  rules for that surface are owned by the security model and
  `aggregates.md` (tenancy in the Aggregate). This shard assumes those
  are in place.
- **CQRS read models served across contexts.** A read model exposed to
  another context is an integration surface; what shape it takes is
  governed by `architecture.md`.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `bounded-contexts.md` -- the boundary this shard's principles cross;
  same word can mean different things on either side, so translation
  (Principle 5) is mandatory.
- `context-maps.md` -- the *kind* of relationship between contexts
  (Open Host Service, Anticorruption Layer, Conformist, Customer-
  Supplier, Separate Ways, Shared Kernel) that this shard implements.
  Principle 4 (use-case-shaped resources) operationalises Open Host
  Service; Principle 5 (Service + Adapter + Translator)
  operationalises Anticorruption Layer; Principle 3 (Published
  Language not shared classes) is the antidote to accidental Shared
  Kernel.
- `domain-events.md` -- the events that flow over messaging are
  Domain Events; their identity, payload, and per-transaction rules
  live there. Principle 7 here builds on at-least-once delivery and
  the Event Store described there.
- `aggregates.md` -- the originating Aggregate carries the
  Long-Running Process state (Principle 8); the consumer Aggregate
  carries the change tracker (Principle 7); the
  one-Aggregate-per-transaction rule still applies on each side.
- `factories.md` -- a Factory in the consumer constructs the local
  Value Object / Aggregate from translated foreign data
  (`factories.md` Principle 7, "Domain Service as Factory across
  contexts").
- `repositories.md` -- the consumer's Repository persists the
  mirrored Aggregate; the tracker has its own Repository in the
  technical Subdomain.
- `services.md` -- the Service-shaped facade in the Anticorruption
  Layer (Principle 5) is a Domain Service; the listener dispatches
  to an Application Service, which owns the transaction
  (`services.md` Principle 5).
- `architecture.md` -- Hexagonal / Ports-and-Adapters places the
  REST resource, the message listener, the HTTP client, and the
  Repository implementation on the *outside* of the hexagon; the
  Service-shaped facade is the *port* on the inside. CQRS read
  models, Event-Driven Architecture, and Long-Running Processes as
  architectural styles are governed there.
- `modules.md` -- the listener and the Repository implementation
  live in `infrastructure` Modules; the facade interface and the
  local Aggregate / Value Object live in domain Modules
  (`modules.md` Principle 8).
- `../../rules/contracts.md` -- the wire shape between two contexts is a
  contract; the Published Language (Principle 3) is the artefact
  that contract is written down in. Renaming a field in the wire
  format is a contract change.
- `../refactoring.md` -- swapping the integration mechanism (REST →
  messaging, RPC → REST) is *not* a refactor; it changes
  observable behavior at the boundary and the consumer's failure
  modes. Treat it as a feature change with full review.
