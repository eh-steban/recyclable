---
paths:
  - "backend/**"
  - "private/specs/**"
---

# DDD shard -- domain events

Tactical-design principles for **Domain Events**: how to discover them
from the domain language, how to shape them as immutable facts, how to
publish them without coupling the model to messaging middleware, how
to keep one transaction modifying one Aggregate while still
synchronizing the rest of the system, and how to cross bounded-context
boundaries reliably under at-least-once delivery. Distilled from
*Implementing Domain-Driven Design*, Chapter 8 ("Domain Events").

This shard covers **what a Domain Event is, how to model it, and how
to publish it inside and across bounded contexts**. For the
transactional Aggregate that emits Events, see `aggregates.md`. For
the Application Services that register subscribers and control
transactions, see `application.md`. For the index of shards,
see `principles-hub.md`.

## What a Domain Event is

> "Something happened that domain experts care about. ... A domain
> event is a full-fledged part of the domain model, a representation
> of something that happened in the domain." -- Evans, quoted in
> Ch. 8

A Domain Event is a **fact about a past occurrence** in one bounded
context's domain that domain experts care about. It is part of the
Ubiquitous Language. It is named in the past tense. It is normally
immutable. It carries enough state for any subscriber, local or
remote, to react correctly without having to query back into the
publishing context.

Three forces motivate Domain Events:

- **Express the domain.** Some business rules are best modeled as
  "when X happens, Y must follow." The Event makes the X explicit and
  promotes the rule from procedural code into a first-class domain
  concept.
- **Honor the one-Aggregate-per-transaction rule.** When the
  consequence of a command must touch a second Aggregate, that touch
  cannot ride the same transaction. Events let the second Aggregate
  catch up asynchronously.
- **Decouple bounded contexts.** Events crossing context boundaries
  let downstream contexts react in their own time on their own model,
  with eventual consistency, instead of being tied to the publisher
  via in-band RPC.

## Principles

### 1. Discover Events from domain language; name them in the past tense

Listen for "When ...", "If that happens ...", "Notify me if ...",
"An occurrence of ..." in conversations with domain experts. Each is a
candidate Event. Once the team agrees an Event is real, the Event's
name joins the Ubiquitous Language and appears in code, docs, tests,
prompts, and conversation in the same form.

The Event name is **the verb of a past command, in the past tense**:
`commitTo(...)` produces `BacklogItemCommitted`, not
`CommitBacklogItem` and not `BacklogItemCommitting`. If a more
specific name reads more clearly to the team
(`BacklogItemCommittedToSprint`), use it; if context makes the
shorter name unambiguous, prefer the shorter. The grammatical rule
is non-negotiable -- present-tense or imperative names invite
treating the Event as a request, which it is not.

**Apply when:** specifying a new behavior whose consequences fan out
beyond a single Aggregate, or when a domain expert uses a "when /
notify me if" phrase. Name the Event before designing the publisher
or any subscriber.

### 2. Events are immutable; carry the minimum state to be replayable

Model Events as immutable Values: a single full-state constructor,
read-only accessors, no setters, no mutators. Any "behavior" on the
Event is side-effect-free per `value-objects.md` Principle 4 -- a
derivation of the carried state, never a mutation.

Carry the state described as "what would be necessary to trigger
the Event again": a timestamp (`occurredOn`), the identity of
the originating Aggregate, the identities of any other Aggregates the
Event materially mentions, and any command parameters or
state-transition values a reasonable subscriber needs. In a
multi-tenant system, the tenant identity always travels with the
Event, even when not in the originating command's signature.

**Do not** ship whole Aggregates inside Events. Cross-context
subscribers should not be reconstituting the publisher's model from
its Event payload -- that is the modeling error `bounded-contexts.md`
and `context-maps.md` warn against. If a subscriber genuinely needs
data the Event does not carry, the team-wide Event contract is
incomplete; revise the Event (probably as a new version), do not
swell it ad hoc.

**Apply when:** designing the Event's fields. Default to: timestamp,
tenant id (if multi-tenant), originating Aggregate id, related
Aggregate ids, command parameters, key state transitions. Justify
each additional field against an actual subscriber need.

### 3. Give an Event identity only when comparison or de-dup needs it

Most Events get by with structural identity -- the tuple of
`(type, occurredOn, originating-Aggregate-ids)` is unique in practice.
No `equals` / `hashCode` over an internal id is needed if the
publishing context never compares Events to each other.

Generate a unique id when:

- The Event is itself modeled as an Aggregate (i.e., a domain concept
  whose existence is the Event -- a `UserRegistered` that is also
  the canonical record of registration, with its own Repository that
  forbids removal).
- Cross-context delivery requires de-duplication and the messaging
  layer does not assign a stable message id of its own (see
  Principle 10).
- The publishing context needs to compare Events for any other
  reason.

**Apply when:** introducing a new Event type. Default to no id. Add
one only when one of the three reasons above is named in the spec.

### 4. Modify one Aggregate per transaction; propagate to others via Events

This is the rule the Events pattern exists to make practical. A
command may not modify two Aggregates atomically. When the second
Aggregate must change as a consequence, the publishing Aggregate
emits an Event, the transaction commits, and a subscriber -- in a
**later** transaction -- applies the change to the second Aggregate.

The corollary: a subscriber registered in the same in-process
publisher (Principle 5) **must not** load and mutate a second
Aggregate. That work must happen out of band, via the messaging path
or an Event-Store-backed forwarder. The in-process subscriber's
legitimate jobs are: write the Event to the Event Store, push it onto
a messaging exchange, send a notification, log it. Never "while we're
here, also commit Aggregate B."

**Apply when:** a command has cross-Aggregate consequences. The shape
of the fix is: Aggregate A emits Event; an out-of-band consumer (in
the same context or another) loads Aggregate B in a new transaction
and applies the change. Do not collapse the two transactions to feel
neat.

### 5. Publish through a thin in-process publisher; keep the model clean

The domain model must not import a messaging library. Publish through
a tiny in-process Observer / Publish-Subscribe component that lives
in a domain module but knows nothing of the wire. Subscribers run on
the same thread as the publishing Aggregate, inside the same
transaction, registered *before* the Aggregate's command method runs.

Aggregates publish a fact and move on:

```text
backlogItem.commitTo(sprint)
  -> Aggregate validates invariants
  -> Aggregate mutates state
  -> Aggregate publishes BacklogItemCommitted
  -> control returns to Application Service
```

The publisher's responsibilities are mechanical: dispatch the Event
to currently-registered subscribers on this thread, prevent
re-entrant publish, and reset between requests. It is not where
business logic lives.

**Apply when:** wiring the publish path. Keep the publisher in the
domain module, keep the messaging adapter in the infrastructure
module, and keep the Aggregate ignorant of both -- the Aggregate
calls `publisher.publish(event)` and that is the end of its
involvement.

### 6. Application Services register subscribers and own the transaction

The Application Service is the natural place to register the
subscribers a given operation needs, invoke the Aggregate command,
and commit (or roll back) the surrounding transaction. The Aggregate
publishes; the Application Service controls when and whether the
publish becomes durable.

Domain Services may also register subscribers when there is a
domain-specific reason to listen, but the transactional control
remains an application concern (see `services.md` Principle 4 on the
client/coordinator split).

**Apply when:** an operation needs a subscriber that is specific to
this use case (e.g., emit an audit Event, append to a projection
table, kick off a downstream notification). Register it in the
Application Service before calling into the model; let the
Application Service own the transaction boundary.

### 7. Persist the Event with the Aggregate change

If the Aggregate change commits but the Event delivery does not (or
vice versa), the system silently drifts. The model and the published
record disagree, and the disagreement is unrecoverable.

Three ways to keep the two consistent:

1. **Shared store.** Use a messaging system that persists into the
   same database as the model; both commit in one local transaction.
   Cheapest when available.
2. **XA / two-phase commit.** Span the model store and the messaging
   store with a global transaction. Heavy, slow, often unavailable.
3. **Event Store table in the model's database.** Write the
   serialized Event into a dedicated table in the same local
   transaction as the Aggregate change. An out-of-band forwarder
   reads unpublished Events from the table and pushes them through
   the messaging system, marking them published once acknowledged.

The Event Store option is the default this shard recommends: it
keeps the durability decision local, removes the messaging system
from the critical path of the user request, and naturally supports
the REST-notification publishing style (Principle 8).

Whichever option is chosen, the **invariant** is: the Event is
durable iff the Aggregate change is durable. Fire-and-forget
publishing -- "send the message, hope it lands, return success" --
is not a third option, it is a bug.

**Apply when:** designing the publish-side persistence story for a
context. State which option is in use; if "Event Store table," name
the table, the forwarder process, and how its watermark is tracked.

### 8. Choose REST notifications vs messaging on traffic and ordering

Two cross-context publishing styles, both Publish-Subscribe:

- **REST notification feeds (Atom-style).** The publisher exposes a
  current log and a chain of immutable archived logs at a stable
  URI. Subscribers pull, track their own high-water mark, and replay
  forward. Archived logs are cacheable forever (HTTP cache headers
  do real work). Best when many subscribers consume the same Event
  set, ordering is by sequence id, no special infrastructure is
  available, or the subscriber set is open-ended.
- **Messaging middleware (push).** The publisher sends to an
  exchange / topic; the broker fans out to registered subscribers.
  Best when subscriber latency must be low, when the broker provides
  delivery guarantees the team would otherwise have to build, or
  when fan-in queueing is needed.

Mixing styles is fine -- the same Event Store can feed both a REST
endpoint and a message exchange.

What does **not** work is using REST notifications as a queue (single
consumer that must serialize ordered work across multiple producers)
or using messaging as a publication archive (subscribers cannot
"replay from the beginning" through most middleware without help).
Match the style to the consumption pattern.

**Apply when:** introducing a new cross-context Event channel. Name
the consumption pattern (fan-out / queue / archive), choose the
style, and document the cache / ack / replay contract before any
subscriber is written against it.

### 9. Latency tolerance is a domain question; ask before assuming sub-second

Eventual consistency is the default for cross-Aggregate and
cross-context propagation. The right tolerance window is **a domain
question** -- "How did the business work without computers? How would
it work without them now?" In most domains, seconds to hours of lag
is invisible to users and acceptable to experts. In some, it is not.

Decide the window with domain experts, write it into the spec for
the relevant capability, and let it drive the architecture (timer
intervals, retry budgets, alert thresholds), not the other way
around. Do not retrofit "sub-second" as a default because it sounds
safer.

**Apply when:** a spec mentions consistency between two Aggregates or
two contexts. Name the acceptable lag explicitly; let the technical
choices follow from it.

### 10. Subscribers de-duplicate or operate idempotently

At-least-once delivery is the working assumption for any Event that
crosses a process boundary (and sometimes within one). A message can
be redelivered because the broker did not see the ack, because the
publisher restarted mid-batch, or because the publisher's
"published" watermark rolled back with a failed transaction.

Two ways to handle it:

- **Idempotent domain operation.** The action triggered by the Event
  is naturally a no-op when applied a second time (e.g., "commit
  this BacklogItem to this Sprint" -- if it is already committed
  there, the call has no effect). Prefer this when the domain
  permits.
- **Idempotent receiver.** The subscriber records the
  `(channel, message-id)` of every handled message in its own data
  store, in the **same local transaction** as the model change it
  performs in response. On every incoming message it queries first;
  if already handled, it drops the message.

REST-notification subscribers get this almost for free: each
notification carries a stable id, and the subscriber's
"most-recently-applied id" suffices because the server delivers
notifications in strict ascending order.

The tracking table is a technical artifact, not a domain concept.
Garbage-collect it when handled-message ids age past any plausible
redelivery window.

**Apply when:** writing any Event subscriber. Name which of the two
de-dup strategies is in use; write a test that delivers the same
message twice and asserts a single observable effect.

## What this shard does **not** govern

- Aggregates (when to emit which Events from which command, which
  invariants the publishing Aggregate enforces) -- that is
  `aggregates.md`. This shard governs the Event's *shape* and
  *delivery*, not the Aggregate's design.
- Event Sourcing (reconstituting Aggregate state by replaying Events
  rather than persisting current state). Event Sourcing is one
  consumer of an Event Store, but the durability and propagation
  rules in this shard apply with or without Event Sourcing -- see
  `architecture.md` for when (not) to adopt it.
- Saga / Process Manager orchestration across Events. `application.md`
  covers long-running workflows that listen to multiple Events and
  emit commands.
- Concrete messaging-library choices (RabbitMQ, Kafka, NATS, SQS,
  application-server timers) -- service conventions handle that.
  This shard governs the *contract*, not the wire.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards, anemic-model
  warning, DDD-Lite trap.
- `entities.md` -- Aggregates emit Events; the Event reflects a
  successful invariant-preserving command on the Aggregate.
- `value-objects.md` -- the Event itself is almost always a Value:
  immutable, side-effect-free, equality by attributes (when
  equality is needed at all).
- `services.md` -- Application Services register subscribers and
  own the transaction; Domain Services may register subscribers for
  domain-specific reasons. The Aggregate publishes -- it does not
  orchestrate.
- `bounded-contexts.md` -- Events leaving the boundary become part
  of the integration surface and therefore part of the Published
  Language; their names belong to the publishing context's
  Ubiquitous Language.
- `context-maps.md` -- cross-context Events typically arrive
  through an Anticorruption Layer that translates them into local
  domain terms; remote Events are not blindly mapped to local
  Aggregates.
- `architecture.md` -- Hexagonal places the messaging adapter
  outside the domain; Event-Driven Architecture, CQRS, and Event
  Sourcing are downstream architectural choices that build on the
  rules here.
- `../contracts.md` -- a published Event is a wire-level public
  contract. Adding fields is usually safe; removing or renaming is
  a breaking change that must be versioned and coordinated.
- `../refactoring.md` -- changing an Event's name, payload shape,
  or semantic meaning is a public-contract change and is forbidden
  by default; introduce a new Event version and migrate
  subscribers, do not silently mutate the existing one.
