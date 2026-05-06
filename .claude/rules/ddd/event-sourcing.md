---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- event sourcing (A+ES)

How to persist an Aggregate as an ordered, append-only stream of
Domain Events instead of as a serialized row, and the consequences for
Application Services, Repositories, concurrency, reads, testing, and
Aggregate granularity. Distilled from Vaughn Vernon, *Implementing
Domain-Driven Design*, Appendix A ("Aggregates and Event Sourcing:
A+ES"), contributed by Rinat Abdullin.

This shard covers **what changes when the Event Stream is the
Aggregate's persistence**. For Domain Event identity, payload, and
publication semantics, see `domain-events.md`. For the Aggregate's
behavioral and invariant rules, which are unchanged, see
`aggregates.md`. For the Application Service shape that A+ES adapts,
see `application.md`. For the architectural styles A+ES interacts with
(CQRS, EDA, Hexagonal), see `architecture.md`. For the index of
shards, see `principles-hub.md`.

## What A+ES is, here

> "Event Sourcing can be used to represent the entire state of an
> Aggregate as a sequence of Events that have occurred since it was
> created. The Events are used to rebuild the state of the Aggregate
> by replaying them in the same order in which they occurred." --
> Vernon, Appendix A

Two things together, never apart:

- **Aggregate persistence as an Event Stream.** No row, no document.
  The Aggregate's identity addresses an append-only list of Events;
  the current state is the fold of that list.
- **Behavior produces Events.** A command method on the Aggregate
  decides what should change, then emits one or more Events. Those
  Events update in-memory state *and* are appended to the Stream.

A+ES is a deliberate architectural commitment, not a default. It
changes how Aggregates are constructed, how Repositories work, how
the Application Service is shaped, how concurrency is enforced, and
how reads are served. Adopting it for one Aggregate type and not
others is possible, but the operational cost (Event Store, snapshots,
projections, evolving Event schema) is mostly fixed -- partial
adoption pays the full cost for partial benefit.

## Principles

### 1. Adopt A+ES when reconstruction and history are first-class concerns

The benefits A+ES buys:

- **The reason for every change is preserved.** Traditional
  persistence overwrites the old state; A+ES appends the new fact
  next to it. Audit, regulatory replay, debugging "what state was
  this Aggregate in on Tuesday?" become trivial queries.
- **Read shapes are disposable and can be rebuilt.** Add a new view,
  a new report, a new index by replaying the Stream into a new
  projection. No backfill migration.
- **Aggregate internals can be refactored aggressively.** The Event
  schema is the contract; the in-memory representation can change
  whenever the team learns something new about the model.
- **The append-only shape is operationally fast and replicates well.**

The costs A+ES imposes:

- **CQRS becomes mandatory.** Event Streams cannot answer ad-hoc
  queries; reads must come from projections. The team is now running
  two persistence shapes (Stream + projections), not one.
- **Operational complexity.** Event Store, snapshots, projection
  rebuild jobs, schema evolution of Events, replication.
- **Skill and tooling cost.** Teams without prior A+ES experience
  spend weeks learning to design Events, version them, and reason
  about replay correctness.

The decision: choose A+ES when the *business* values
reconstruction and history -- regulated industries, ledgers, audit
trails, behavioral analytics on past state, "what would have happened
if?" replay. Defer it when the persisted artefact is mostly *current
state to be queried*; a row store with conventional CQRS read models
(if needed) is cheaper.

**Apply when:** evaluating the persistence strategy for a new
Bounded Context or a major rewrite. State the business reason for
A+ES in one sentence; if the reason is "it's modern" or "we'll need
audit eventually," defer.

### 2. Aggregate state is the fold of its Event Stream

The Aggregate has no row representation. The Aggregate's identity
addresses a Stream; the constructor takes the Stream's Events and
replays them to arrive at the current state.

```text
state = fold(replay, initial_state, events)
```

Three implications:

- **There is no `update` operation on persistence.** New behavior
  produces new Events; new Events are appended; the next load sees
  the longer Stream.
- **Reconstitution is deterministic.** Given the same Events in the
  same order, the same in-memory state always results. This is a
  testable property, not a hope.
- **The Stream is the source of truth.** Caches, snapshots, and
  projections are derived. They can be wrong, regenerated, or
  discarded; the Stream cannot.

**Apply when:** designing an A+ES Aggregate. The constructor accepts
an iterable of past Events and replays them; no other constructor
exists for an existing Aggregate (a separate factory is fine for the
*new* Aggregate that has no Stream yet).

### 3. Separate `Apply` (record + mutate) from `Mutate` / `When` (state update only)

Three method roles in a clean A+ES Aggregate:

- **`Apply(event)`** -- called from a behavior method. Appends the
  event to the Aggregate's pending `Changes` list *and* calls
  `Mutate(event)` so subsequent steps in the same behavior see
  up-to-date state. Used only for *new* Events produced by behavior.
- **`Mutate(event)`** -- dispatches to the per-Event handler.
  Typically an indexed lookup (or runtime overload selection) on the
  Event's type. Pure routing; no logic.
- **`When(specificEvent)`** -- one per Event type. Updates fields on
  the Aggregate to reflect the Event's facts. Never emits new Events,
  never enforces invariants, never calls services. Just sets state.

A behavior method runs invariant checks, calls Domain Services,
decides what should be true, and emits one or more Events through
`Apply(...)`. Reconstitution from past Events runs `Mutate(...)`
directly, with no `Apply(...)` -- those Events are already in the
Stream and must not be appended again.

This separation lets snapshots reuse `Mutate` (replay events past
the snapshot to bring state current) without polluting `Changes`,
and lets unit tests run "given these past events, then when this
command, expect these new events" cleanly (Principle 12).

**Apply when:** writing or reviewing an A+ES Aggregate. If a
behavior method is updating fields directly instead of going through
`Apply(...)`, the in-memory state and the Stream will drift -- the
field updates won't be replayed on next load. Push the field update
into a `When(event)` handler.

### 4. Application Services become load → execute → append

The A+ES Application Service shape:

```text
def handle(command):
    stream     = event_store.load(command.aggregate_id)
    aggregate  = AggregateType(stream.events)        # replay
    aggregate.execute(command, ...domain_services)   # behavior → Changes
    event_store.append(
        command.aggregate_id,
        expected_version=stream.version,
        events=aggregate.changes,
    )
```

Four responsibilities, in order:

- **Load the Stream by Aggregate identity.** The Stream carries a
  version number reflecting the count (or last index) of events
  appended so far.
- **Reconstitute the Aggregate.** `new Aggregate(stream.events)`.
- **Dispatch the command.** Pass needed Domain Services as method
  arguments (`aggregates.md` Principle 6 -- Application Services
  look up dependencies, not Aggregates).
- **Append the Aggregate's `Changes` with the loaded version as
  guard.** The Event Store enforces "no other writer has appended
  since this version" atomically.

The Application Service is still thin (`application.md` Principle 1):
no business logic, no field updates, no decisions. It is the same
shape as a row-oriented Application Service, but with `load → mutate
→ save` replaced by `load-stream → execute → append-with-version`.

**Apply when:** writing an Application Service against an A+ES
Aggregate. Every command path follows the four-step shape; if a
command needs to read state without changing it, load the Stream and
read the Aggregate, no append.

### 5. Concurrency is optimistic on stream version, with two recovery strategies

When two threads load the same Stream at version N, both run their
behaviors, and both try to append, only the first append succeeds.
The second sees a version-mismatch and the Event Store throws (call
it `EventStoreConcurrencyException` or
`OptimisticConcurrencyException`). Two recovery strategies:

- **Retry-and-replay.** Catch the exception, reload the Stream
  (which now contains the winning thread's Events), reconstitute the
  Aggregate, re-run the behavior, retry the append. Loop until
  success or until a retry budget exhausts.
  - Use when the behavior is idempotent and side-effect-free --
    pure domain logic that can run again without external
    consequences.
- **Event-conflict resolution.** Catch the exception, compare each
  of *this* thread's intended Events against the Events that were
  appended concurrently. If any conflict (a per-Aggregate-type
  predicate), throw a real concurrency error to the caller. If none
  conflict, append at the new version.
  - Use when the behavior has external side effects that cannot
    repeat (payment captured, identity allocated, e-mail sent).
  - Default conflict rule: Events of the same type conflict; Events
    of different types do not. Override per Aggregate when the
    domain calls for it.

The version guard is *not* optional -- without it, two threads can
silently produce two Aggregate states that diverge from the Stream's
own ordering.

**Apply when:** wiring the append step. Decide retry-vs-resolution
per Aggregate type by asking "if I run this behavior twice, will the
*outside world* tolerate it?" If yes, retry; if no, resolve.

### 6. Plan for replay cost: snapshots, caching, partitioning

Replay is `O(events_since_creation)`. At hundreds of thousands of
Events per Stream, load latency dominates command throughput. Three
operational responses, all optional, all standard:

- **Snapshots.** At periodic version thresholds (every N events),
  serialise the full Aggregate state and persist it keyed by Stream
  identity + version. On load: fetch the latest snapshot, then
  replay only Events appended *after* the snapshot's version. Use a
  separate `ReplayEvents` method on the Aggregate (calls `Mutate`
  but not `Apply` -- those Events must not re-enter `Changes`).
  Generated by a background job; threshold tuned per Aggregate type.
- **In-memory Event caching.** Events are immutable once appended;
  cache the Stream's tail in process memory and ask the Store for
  "events since version K" on load. Trades memory for latency.
- **Identity-hash partitioning.** Spread Aggregate Streams across
  nodes by hash of identity. Combines with caching: each node holds
  the cache for its own partition.

Do not pre-optimise: a new A+ES system without snapshots performs
fine until Streams grow. Plan for the *shape* of the optimisation
(the `ReplayEvents` API, the snapshot key, the threshold knob) so
adding it later is configuration, not refactor.

**Apply when:** designing the Aggregate's replay API and the
Repository / Event Store interface. Build `LoadEventStream(id,
afterVersion)` from day one; defer snapshot generation until a
Stream's load latency complains.

### 7. Layer the Event Store: typed wrapper over an untyped append-only store

Two interfaces, two roles:

- **Typed Event Store** (project-specific, knows your domain). Its
  contract is `LoadEventStream(id) → EventStream`,
  `LoadEventStream(id, skip, take)`, and `AppendToStream(id,
  expectedVersion, events)`. It deals in your `IEvent` /
  `DomainEvent` type, your `IIdentity` type, and your stream version
  semantics. It owns serialization, identity-to-string conversion,
  and translation of low-level concurrency exceptions into domain-
  facing exceptions.
- **Untyped append-only store** (generic, reusable). Its contract is
  `Append(name, bytes, expectedVersion)`,
  `ReadRecords(name, afterVersion, maxCount)`, and `ReadRecords(
  afterVersion, maxCount)`. It deals in byte arrays, string names,
  and integer versions. It owns the storage primitive: relational
  table, BLOB file, append-only log, cloud blob, KV store.

The split exists because storage primitives generalise; domain
serialization and typing do not. Multiple typed Event Stores can sit
on top of one append-only store; the same typed Event Store can be
backed by a swappable append-only implementation.

Two append-only patterns Vernon documents:

- **Relational.** A `(name, version, data)` table. Append is a
  transaction: read max version for the name, compare to expected,
  insert with `version + 1`. Strong consistency for free; cheap to
  operate.
- **BLOB / append-only log.** One file per Aggregate (or per type),
  length-prefixed records, append with exclusive write lock,
  CRC for integrity. More work; pays off when a relational store is
  unavailable or when the workload is event-firehose-shaped.

The second `ReadRecords(afterVersion, maxCount)` overload (no name)
exists because *projections* (Principle 8) need to consume the
global event order, not just one Aggregate's stream.

**Apply when:** introducing an Event Store. Define the typed
interface in the domain or application layer; place the
implementation in `infrastructure`. The append-only primitive can
start as the simplest thing that works (often relational) and be
swapped without touching the typed wrapper.

### 8. Reads come from projections of the Event Stream, not from the Stream itself

Event Streams cannot answer ad-hoc queries efficiently -- "total of
all customer orders this month" would require loading every Customer
and replaying every order. Reads come from a separate persistent
**Read Model** built by **Projections**:

- A Projection is an Event subscriber. It receives Events as they
  are appended (or by replaying the Stream) and updates a stored
  view -- a document, a row, a key in a cache, an index entry.
- The Projection's update step looks like an Aggregate's `When`
  handler but writes to a query store rather than to in-memory
  Aggregate state.
- Read Models are persisted wherever fits the read shape: document
  store, relational table, cache, search index, CDN object.

Three properties make Projections powerful:

- **They are disposable.** Throw the Read Model away, replay the
  full Stream through the Projection, and you have a fresh,
  consistent Read Model. No migration script.
- **They are cheap to add.** A new view = a new Projection class +
  a new store + a replay run. The Aggregate code does not change.
- **They support cross-Aggregate, cross-context views.** A
  Projection can subscribe to Events from several Aggregates or
  several contexts and join them into a single read shape, without
  any Aggregate knowing about the join.

A+ES makes CQRS not optional. Treat the read side as a first-class
artefact: each Projection has a name, an owning team, a rebuild
procedure, and a deployment story.

**Apply when:** designing how data reaches the UI / API / report.
The write side appends Events; the read side queries a Projection
output. Do not query the Stream directly except for replay or
debugging.

### 9. Events serve both reconstitution and publication; enrich for the 80 percent

Under A+ES an Event has two consumers:

- **The Aggregate itself**, replaying to reconstitute state. It
  needs *exactly* the data needed to update its own fields.
- **External consumers**: Projections, other Bounded Contexts,
  notification subscribers. They need *display-friendly* and
  *self-contained* data so they don't have to look up secondary
  tables for every Event they handle.

The collision: an Event sized for reconstitution alone is too sparse
for projections; an Event sized for every conceivable subscriber is
bloated and leaks the consumer's needs back into the Aggregate.

The rule of thumb: **enrich Events to satisfy roughly 80 % of
subscribers**. Carry:

- Owning identifiers (`customerId` on every customer-scoped Event).
- Display names and natural keys consumers commonly need
  (`customerName`, `projectName`).
- Values that are stable for the lifetime of the Event (currency,
  timezone, locale).

Do *not* carry data that:

- Belongs to a single subscriber's secondary lookup -- that
  subscriber maintains its own index.
- Mutates over time (today's customer email if the projection wants
  the historical email *at event time*, that is correct; if the
  projection wants the *current* email, it must look it up).
- Encodes the subscriber's view shape (no `formattedDisplayString`
  on the Event).

This is not optional decoration. Under A+ES the Event is the
contract; once written, it is in the Stream forever. Underbaking the
payload now means projections do `LoadCustomerById(id).name` for
every replayed event later.

**Apply when:** designing an A+ES Domain Event. List the projections
and external consumers; carry the data that the majority need;
review with the Aggregate's owning team to confirm reconstitution is
covered.

### 10. Choose evolution-friendly serialization, immutability, and Value Objects

Three concrete tooling choices that pay back across the lifetime of
an A+ES system:

- **Tag-based serialization** (Protocol Buffers, Avro, Thrift,
  MessagePack, FlatBuffers). Fields are addressed by integer tag,
  not by name. Renaming a field, adding a field, deprecating a
  field -- all backward-compatible at the wire level. Name-based
  serialization (JSON, XML, default `DataContractSerializer` /
  `Jackson`) breaks consumers when a field is renamed and silently
  produces wrong data. Choose tag-based for any persisted Event
  format. (Principle 3 of `integrating-bounded-contexts.md` --
  Published Language not shared classes -- still applies; the
  serialization choice is *how* the Published Language is encoded.)
- **Immutable Event objects.** Constructor-only initialization,
  private setters, no mutating methods. The Event has occurred; it
  cannot be modified. Encode this in code so a careless caller
  cannot violate it.
- **Value Objects in Event payloads.** Typed identifiers
  (`CustomerId`, `ProjectId`), typed quantities (`Money`,
  `Duration`), typed enums (`Currency`). Two benefits over raw
  primitives: the compiler catches argument-order bugs (`new
  ProjectAssignedToCustomer(customerId, projectId)` swap), and the
  Event reads as the Ubiquitous Language rather than as a tuple of
  longs and strings. (`value-objects.md` Principle 4 -- typed
  identity over primitive obsession.)

A fourth, optional, pattern that pays off as Event count grows past
roughly 50 types: **a contract DSL that generates Event and Command
classes from a compact definition file**. Reduces hand-written
boilerplate, supplies a single-screen overview of the Event
vocabulary, and standardises the constructor / immutability shape.

**Apply when:** committing to A+ES for any Aggregate. Pick the
serializer and Value-Object conventions before the first Event ships
to a Stream; retrofitting them across an existing Stream is
expensive.

### 11. A+ES makes Aggregates cheap; aim for Focused Aggregates

In a row-oriented system, introducing a new Aggregate means a new
table (or document type), a new mapping, a new Repository, a new
migration. The cost biases teams toward *adding to* an existing
Aggregate -- a "Customer" Aggregate accumulates billing, security,
preferences, consumption history, and audit until the invariant
boundary is meaningless.

A+ES removes most of that cost: a new Aggregate means a new Stream
name and a new constructor that takes Events. The bias inverts. Aim
for **Focused Aggregates**: each Aggregate is responsible for one
cohesive set of invariants and one slice of the real-world entity
it represents.

Vernon's example: a real-world customer becomes

- `Customer:505` (billing, invoicing, account)
- `SecurityAccount:505` (users, permissions)
- `Consumer:505` (service consumption metering)

each with its own Stream, possibly in its own Bounded Context,
possibly hosted on infrastructure tuned to its load profile.

Two safeguards on the "smaller" pressure:

- **Invariants still rule.** An Aggregate exists to protect
  invariants (`aggregates.md` Principle 1). "Smaller" never means
  "split a true invariant across two Streams."
- **Identity sharing across the focus boundary is a context-map
  question.** When `Customer:505` and `Consumer:505` reference each
  other, that is a cross-Aggregate (and possibly cross-context)
  relationship; it goes through identity, not a foreign-key edge
  inside one Stream.

**Apply when:** designing or carving Aggregates in an A+ES system.
For each candidate, name the invariants that hold within. If the
list reads like three different concerns, split into three Focused
Aggregates.

### 12. Test as `Given past Events / When command / Then new Events`

A+ES Aggregates have a natural specification shape:

```text
Given:    [past Events that establish initial state]
When:     [a command (or a behavior method call)]
Then:     [Events the Aggregate should produce]
          OR   an exception of type X
```

The test scaffold:

- Construct the Aggregate by replaying the `Given` Events.
- Invoke the `When` behavior (directly on the Aggregate, or via the
  Application Service with a Command).
- Assert that the Aggregate's `Changes` list (or the appended-Event
  capture) equals the `Then` list, in order.

Three properties this style yields:

- **Tests are decoupled from internal Aggregate state.** A refactor
  that changes private fields but preserves the Event-emitting
  behavior leaves all tests green. Tests calcify around behavior,
  not implementation -- the right place.
- **Tests are readable as specifications.** The `Given` / `When` /
  `Then` blocks read like a domain expert's use case. Some teams
  print them as human-readable scenario documents for review.
- **Tests are runnable as documentation.** New team members read the
  scenarios to learn what the Aggregate does, not the field shape.

Two practical notes:

- **Equality of Events** must be by value, not by reference. Value-
  Object Events with `equals` / `__eq__` defined on payload fields
  give this for free.
- **The Application Service is testable too** -- pass a Command, let
  the Service load (from an in-memory Event Store), execute, and
  append; assert on the appended Events.

**Apply when:** writing tests for an A+ES Aggregate. The default
test shape is Given-When-Then; if a test is asserting on the
Aggregate's *fields* directly, the test is reading the wrong surface.

## What this shard does **not** govern

- **The decision *whether* to use A+ES across the system.** That is
  an architectural commitment, governed by `architecture.md` and the
  project's strategy docs. Principle 1 here surfaces the trade-offs
  but does not mandate adoption.
- **Aggregate invariants and shape.** Whether an Aggregate is
  persisted as rows or as a Stream, its invariants and consistency
  boundary are governed by `aggregates.md`. A+ES does not loosen
  the invariant rules.
- **Domain Event identity, payload, immutability, and per-
  transaction publication.** Those are governed by
  `domain-events.md`. This shard adds A+ES-specific concerns:
  reconstitution faithfulness (Principle 9) and Stream ordering as
  the source of truth (Principle 2).
- **Generic Event-Driven Architecture or messaging integration.**
  How Events flow between Bounded Contexts is governed by
  `integrating-bounded-contexts.md`; A+ES is one *internal* design
  for Aggregate persistence, not a messaging strategy. (Though A+ES
  systems frequently publish their Events to other contexts via
  messaging, see Principle 8 of that shard.)
- **CQRS as a standalone pattern.** A+ES *forces* a read/write split
  (Principle 8 here); CQRS without A+ES is a separate choice
  governed by `architecture.md` and `repositories.md` Principle 8.
- **Specific Event Store products** (EventStoreDB, Kafka with
  compaction, Marten, Axon, custom). Selection is operational; the
  invariants this shard names hold for any of them.
- **Functional / non-OO implementations.** Vernon notes that Event
  Sourcing is "inherently functional" -- the Aggregate state becomes
  a left fold of Events, behaviors become `Func<State, Event,
  State>` and `Func<Args..., State, Event[]>`. The principles in
  this shard hold under both shapes; idiomatic translation to F#,
  Clojure, Haskell, or Elixir is a project choice.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `aggregates.md` -- the Aggregate's invariants, consistency
  boundary, and one-Aggregate-per-transaction rule are unchanged
  under A+ES (Principles 1, 4 here all rest on `aggregates.md`).
  Tell-Don't-Ask still governs behavior; A+ES just changes how the
  outcome is persisted.
- `domain-events.md` -- A+ES Events are Domain Events with
  reconstitution duty added (Principle 9 here builds on
  `domain-events.md` Principles 4 and 5; immutability is
  `domain-events.md` Principle 4).
- `application.md` -- the load → execute → append shape (Principle 4
  here) is `application.md` Principle 1 with row-oriented save
  replaced by Event-Store append; Commands as input
  (`application.md` Principle 2) are unchanged.
- `repositories.md` -- under A+ES, the Repository is replaced by (or
  wraps) the Event Store. The Set-mimicking metaphor
  (`repositories.md` Principle 2) holds for `add(...)` (new
  Aggregate) but `update`/`save` does not exist; mutation is implicit
  in command-then-append. Use-case-optimal queries
  (`repositories.md` Principle 8) become Read Model Projections
  (Principle 8 here).
- `value-objects.md` -- typed identifiers and Value Objects in Event
  payloads (Principle 10 here, `value-objects.md` Principles 4 and
  5); Events themselves satisfy the five Value-Object criteria
  (immutable, conceptual whole, replaceability, value equality).
- `factories.md` -- Factories still create *new* Aggregates that
  have no Stream yet; the result is added (no Events to replay yet)
  and the Aggregate's first behavior produces its first Events
  (`factories.md` Principles 1, 6).
- `services.md` -- Domain Services are passed into A+ES Aggregate
  methods exactly as in row-oriented systems (`services.md`
  Principle 6); the Application Service still owns the transaction
  surface, now realised as the append step (Principle 4 here).
- `architecture.md` -- A+ES is an architectural style choice
  alongside Layers / Hexagonal / EDA / CQRS. It pairs naturally
  with CQRS (forced by Principle 8 here) and with Event-Driven
  Architecture (Events flow naturally to subscribers).
- `bounded-contexts.md` -- Focused Aggregates (Principle 11 here)
  often align with sub-context boundaries; an A+ES Aggregate per
  context is a clean default.
- `integrating-bounded-contexts.md` -- when A+ES Events are
  published to other contexts, the integration rules there apply
  (Published Language, at-least-once delivery, idempotent handlers,
  out-of-order tolerance).
- `modules.md` -- the Event Store interface lives in domain or
  application Modules; the implementation in `infrastructure`
  (`modules.md` Principle 8); Projection classes typically live in
  their own Module so they can be added and replaced without
  touching the Aggregate's Module.
- `../contracts.md` -- the Event schema is a contract, *especially*
  under A+ES, because past Events live in the Stream forever. Adding
  a field is safe with tag-based serialization (Principle 10);
  removing or renaming one is a contract change requiring a versioned
  successor.
- `../refactoring.md` -- A+ES makes Aggregate *internals*
  refactor-friendly (Principle 11) because the Event schema is the
  invariant; refactoring an Event schema, by contrast, is *not* a
  refactor and requires a versioned migration.
