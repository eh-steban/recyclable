---
paths:
  - "backend/**"
  - "private/specs/**"
---

# DDD shard -- factories

How to use Factories inside a domain model so that constructing a complex
Aggregate is itself part of the *language*, not a chore the client gets
right by accident. Distilled from *Implementing Domain-Driven
Design*, Chapter 11 ("Factories").

This shard covers **why and where to use Factory Methods** inside a
bounded context. For the Aggregate boundary the Factory creates *into*,
see `aggregates.md`. For the Domain Event a Factory often emits, see
`domain-events.md`. For the index of shards, see `principles-hub.md`.

## What a Factory is, here

A Factory is whatever the Ubiquitous Language uses to *create* a complex
Aggregate, such that the client supplies only what the language says it
should supply -- not the parent-Aggregate identity, not the tenant id,
not internal scaffolding.

> "Shift the responsibility for creating instances of complex objects
> and Aggregates to a separate object, which may itself have no
> responsibility in the domain model but is still part of the domain
> design. Provide an interface that encapsulates all complex assembly
> and does not require the client to reference the concrete classes of
> the objects being instantiated. Create entire Aggregates as a piece,
> enforcing their invariants." -- Evans, quoted in Ch. 11

Two shapes recur:

- **Factory Method on an Aggregate Root** -- the parent Aggregate gets a
  method like `calendar.scheduleCalendarEntry(...)` or
  `forum.startDiscussion(...)`. The Aggregate is still primarily an
  Aggregate; the Factory Method is one of its behaviors. This is the
  most common case in the book and in practice.
- **Standalone Factory object** -- a class whose only purpose is to
  create one Aggregate type. It has no other domain responsibility and
  is not a first-class citizen of the model. Reach for this only when
  no parent Aggregate naturally owns the creation, or when the
  construction logic is too dense to live on an Aggregate.

A third shape -- **Domain Service as Factory** -- appears when creation
requires translating an object from another Bounded Context (Principle
7).

## Principles

### 1. Place the Factory Method on the parent Aggregate, named in the language

The right home for a Factory Method is the Aggregate that *owns the
context the new Aggregate is created in*: a `Calendar` schedules a
`CalendarEntry`; a `Forum` starts a `Discussion`; a `Product` plans a
`BacklogItem`. The method name is the **verb the domain expert uses** in
the sentence -- "Calendars schedule calendar entries" maps directly to
`calendar.scheduleCalendarEntry(...)`. A constructor named
`new CalendarEntry(...)` cannot carry that sentence; the Factory Method
can.

Choose the method name with the same care as an Entity name. If the
domain expert says "publish," the method is `publish`, not `create` and
not `save`. If the language has a verb at all, prefer it over a generic
`createX` name.

**Apply when:** adding a new Aggregate type whose creation has a parent
Aggregate the language obviously associates it with. Default to a
Factory Method on the parent before reaching for a standalone Factory.

### 2. Make the Factory Method enforce identity and tenancy correctness

The strongest reason to use a Factory at all is to guarantee that
fields the client should never be allowed to get wrong are *not its
responsibility to supply*. In a multitenant system, the parent
Aggregate already carries the correct `TenantId` and parent-Aggregate
identity; the Factory Method passes those into the new Aggregate's
constructor.

> "If an Aggregate instance were created under the wrong tenant, giving
> it the wrong `TenantId`, it could be disastrous. ... Placing a
> carefully designed Factory Method on specific Aggregate Roots can
> ensure that tenancy and other association identities are created
> correctly." -- Ch. 11

In the canonical example, the Factory Method on `Calendar` accepts
nine parameters; the `CalendarEntry` constructor requires eleven. The two
the client *cannot* supply -- `Tenant` and `CalendarId` -- are the two
it must not be allowed to.

**Apply when:** the new Aggregate carries a tenant id, an
owning-parent id, or any other identity that should be derived from
context, not chosen by the caller. The Factory Method is the place to
derive it.

### 3. Hide the constructor when a Factory Method covers its creation

A Factory Method that *only some* clients use is decoration. To make
the Factory the single path, the target Aggregate's constructor must
be **unreachable from outside the package**: declare it `protected`,
package-private, or whatever the language's narrowest accessibility is
that still lets the parent Aggregate call it. A public constructor
next to a Factory Method invites callers to bypass the Factory and
recreate the bug the Factory exists to prevent.

This is the same accessibility discipline Value Objects use to enforce
their invariants (`value-objects.md`). Apply it consistently.

**Apply when:** introducing a Factory Method on a parent Aggregate.
Audit the target Aggregate's constructor accessibility *in the same
change*. If the constructor stays public, the Factory is advisory.

### 4. Add Factory-level guards only for state-of-parent invariants

A Factory Method does not need to re-validate its own arguments -- the
new Aggregate's constructor and its Value Object parameters already do
that:

> "It is unnecessary to guard the Factory Method itself since the
> constructors of each of the Value parameters and the [target]
> constructor, as well as the setter methods that the constructor
> self-delegates to, provide all the needed guards." -- Ch. 11

Reserve Factory-level guards for invariants the *parent Aggregate's
state* implies and the constructor cannot see. Example:
`Forum.startDiscussion()` throws if `forum.isClosed()` -- only the
parent knows that.

**Apply when:** writing a Factory Method. Resist the reflex to copy
constructor guards up. Ask: "is this an invariant of the new
Aggregate (belongs on its constructor) or of the parent's current
state (belongs on the Factory Method)?"

### 5. Publish the Domain Event from the Factory Method, after construction

Factory Methods are the natural emission site for *creation* Events:
`CalendarEntryScheduled`, `DiscussionStarted`, `BacklogItemPlanned`.
The Method:

1. Constructs the new Aggregate.
2. Publishes the Event.
3. Returns the new Aggregate to the caller.

If construction throws, the Event is never published -- which is the
correct behavior. The one-Aggregate-per-transaction rule
(`aggregates.md`, Principle 1; `domain-events.md`, Principle 4) still
holds: the new Aggregate is the one being persisted within the
transaction's commit boundary, and the parent that hosts the Factory
Method is read, not mutated. Subscribers that need to update other
Aggregates do so in their own transactions.

**Apply when:** the new Aggregate's existence is itself a
domain-relevant fact downstream subscribers care about. Publish from
the Factory Method, not from the Application Service that calls it.

### 6. The Factory creates; the caller persists

A Factory Method returns the new Aggregate. It does **not** call the
Repository:

> "After a new `CalendarEntry` is successfully created, the client
> must add it to its Repository. Failing to do so will release the new
> instance to be swept by the garbage collector." -- Ch. 11

The caller -- almost always an Application Service -- is responsible
for `repository.add(instance)` and for owning the transaction. This
keeps the Aggregate's domain layer free of persistence imports
(`aggregates.md`, Principle 8) and keeps the transaction boundary
explicit at the Application Service.

**Apply when:** writing a Factory Method on an Aggregate. It returns;
it does not save. Place the `repository.add(...)` in the Application
Service that called the Factory.

### 7. Use a Domain Service as Factory when crossing Bounded Contexts

When the new object must be **translated from another Bounded
Context** -- the upstream context owns a different model and a
different language -- a Factory Method on a local Aggregate is wrong.
The translation is a cross-context concern, not an Aggregate
behavior. The right shape is a Domain Service interface (declared in
the domain layer) whose implementation lives in `infrastructure` and
combines:

- An **Adapter** that talks to the upstream Open Host Service.
- A **Translator** that maps the upstream Published Language onto
  local Value Objects or Aggregates.

Example: `CollaboratorService` translates a `User` from the
Identity-and-Access Context into `Author`, `Creator`, `Moderator`,
`Owner`, or `Participant` Value Objects in the Collaboration
Context. The local context never speaks of "users."

This is also where the Anti-Corruption Layer pattern lives (see
`context-maps.md`).

**Apply when:** the new instance's identity or attributes originate in
another Bounded Context. Do not pretend it is a local Aggregate
Factory Method -- give it a Service whose name is the local concept
being produced.

### 8. Account for the load cost of parent-Aggregate Factory Methods

A Factory Method on a parent Aggregate forces the parent to be loaded
from its Repository before the child can be created. Under low
traffic this is fine; under high traffic it becomes a noticeable
cost:

> "[A]s the traffic in this Bounded Context increases, the team will
> have to weigh the consequences carefully." -- Ch. 11

The trade-off is between **expressiveness** (the Ubiquitous Language
sentence holds) and **throughput** (one fewer round trip if the child
can be created without loading the parent). When the cost shows up in
profiling, options are:

- Move to a **standalone Factory** that takes the parent's id
  directly, giving up the language sentence for measured throughput.
- Move to a **Domain Service Factory** if the construction logic has
  grown too dense for either an Aggregate Method or a standalone
  class.

Do not pre-emptively flatten the Factory Method into a static helper
on suspicion. Measure first.

**Apply when:** profiling shows the parent-load step is the
bottleneck, or when designing a high-traffic creation path where the
parent would otherwise be loaded *only* to host the Factory Method.
Document the trade-off in the spec; do not silently demote the
Factory.

## What this shard does **not** govern

- **Abstract Factory** and **Builder** from *Design Patterns* -- those
  are general tooling-level patterns. This shard governs Factories
  whose names are domain language and whose contracts are domain
  invariants. If a domain-specific class hierarchy is what tempts you
  toward Abstract Factory, see `aggregates.md` first -- hierarchies
  inside an Aggregate boundary are usually a smell, not a goal.
- **Construction of Value Objects** -- those are usually direct calls
  through their own constructors or static creation methods (see
  `value-objects.md`). Factory ceremony is overkill for a Value Object
  the language already names directly.
- **Persistence and Repository design** -- the Factory hands off a new
  Aggregate; what happens next is `repositories.md`'s concern, not
  this one.
- **Cross-Bounded-Context integration mechanics** -- this shard names
  the Service-as-Factory shape; the *integration* details (Open Host
  Service, Published Language, Anti-Corruption Layer, message vs HTTP)
  live in `context-maps.md` and `integrating-bounded-contexts.md`.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `aggregates.md` -- the Aggregate the Factory creates *into*; the
  parent-Aggregate Factory Method shape derives from the Aggregate
  rules (no Repository in the Aggregate; the Application Service does
  the lookup and the persist).
- `entities.md`, `value-objects.md` -- the new Aggregate's constructor
  uses Value Objects to guard each field (Principle 4 here); the same
  accessibility discipline (Principle 3 here) applies.
- `services.md` -- the cross-context Factory shape (Principle 7) is a
  Domain Service whose name is the *result* it produces; mini-layer
  drift (`services.md` Principle 7) applies if the Factory grows too
  many siblings.
- `domain-events.md` -- the Factory Method is the natural Event
  emission site (Principle 5); transactional rules and
  one-Aggregate-per-transaction still apply.
- `bounded-contexts.md`, `context-maps.md` -- the Service-as-Factory
  pattern (Principle 7) is one realization of an Anti-Corruption
  Layer; the upstream is an Open Host Service with a Published
  Language.
- `architecture.md` -- the Service-as-Factory implementation lives in
  `infrastructure`; the interface lives in `domain.model` (or
  `domain.service`).
- `../contracts.md` -- a Service-as-Factory whose interface is
  consumed by another team is a public contract; renaming it is a
  contract change.
- `../refactoring.md` -- moving a creation site between
  Aggregate-Method, standalone-Factory, and Service-Factory shapes is
  a refactor as long as the public method name and signature do not
  change; if they do, treat it as a contract change.
