---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- repositories

How to design and use a Repository so that the domain layer talks about
Aggregates and the persistence mechanism stays underneath. Distilled
from Vaughn Vernon, *Implementing Domain-Driven Design*, Chapter 12
("Repositories").

This shard covers **what a Repository is, what shapes it can take, and
how it interacts with transactions and tests**. For the Aggregate the
Repository persists, see `aggregates.md`. For the Factory that
constructs an Aggregate before it is added, see `factories.md`. For the
index of shards, see `principles-hub.md`.

## What a Repository is, here

A Repository gives the illusion of an **in-memory collection of all
instances of one Aggregate type**, addressed through a well-known
interface. Add to it, remove from it, look an instance up by identity
or by domain criterion -- exactly as you would a `Set` in memory.

> "For each type of object that needs global access, create an object
> that can provide the illusion of an in-memory collection of all
> objects of that type. Set up access through a well-known global
> interface. Provide methods to add and remove objects. ... Provide
> methods that select objects based on some criteria and return fully
> instantiated objects or collections of objects whose attribute
> values meet the criteria. ... Provide repositories only for
> aggregates." -- Evans, quoted in Vernon Ch. 12

A Repository is **not** a Data Access Object. A DAO is "expressed in
terms of database tables, providing CRUD interfaces to them"; a
Repository is expressed in terms of an Aggregate type and the language
of the domain. If a Repository's interface reads like row-level CRUD
(`updateRow`, `selectByColumn`), it is a DAO with a different name.

Two design styles recur:

- **Collection-oriented** -- `add(...)` / `remove(...)`, no `save()`.
  Mutations to an Aggregate already in the Repository are persisted
  *implicitly* by the persistence mechanism's change-tracking
  (copy-on-read, copy-on-write, copy-before-write). Works when the
  store supports a Unit of Work or Session that watches loaded objects.
- **Persistence-oriented** -- `save(...)` / `saveAll(...)`. The caller
  must hand modified Aggregates back to the Repository explicitly.
  Required when the store has no change-tracking (key-value stores,
  in-memory data fabrics, document stores).

The choice is made by the **persistence mechanism's capabilities**, not
by personal preference (Principle 3).

## Principles

### 1. Provide a Repository only for an Aggregate Root

One Aggregate type, one Repository. The Repository's interface is the
*only* public path from the Application layer to instances of that
Aggregate; non-Root entities are reached by navigation through the
Root, never directly through a Repository.

The rare exception is a **polymorphic hierarchy of Aggregates** that
clients use interchangeably (Liskov Substitution): a base Aggregate
class with a small number of concrete subclasses, all addressed
through a single Repository whose finders return the base type. This
works only when clients never need to know which subclass they hold.
The moment client code starts asking "is this a Warble or a Wonkle?"
via id discriminators or runtime type checks, the hierarchy is the
wrong tool. Prefer:

- A single Aggregate with a **Standard Type / State** field that
  dispatches internally (`value-objects.md` discusses Standard Type),
  *or*
- **Role-based interfaces** (`SchedulableService`) implemented across
  separate Aggregates that each keep their own Repository
  (`entities.md` discusses roles).

**Apply when:** introducing a new Aggregate. Generate exactly one
Repository for it. If you find yourself reaching for a shared
Repository across multiple Aggregate types, prove LSP-interchangeable
use first; otherwise split.

### 2. A Repository mimics an in-memory Set, not a CRUD wrapper

Two consequences follow from "the Repository is a Set":

- **Adding the same Aggregate twice is benign.** The unique identity
  of the Root means the Repository already holds it; the second
  `add(...)` is a no-op, not a duplicate row, not an error.
- **You do not "re-save" a modified Aggregate.** When the persistence
  mechanism tracks changes implicitly, asking the Repository to
  persist an Aggregate that is *already in it* is meaningless --
  modifications were already made on the live instance. The
  collection-oriented Repository has no `save()` method because there
  is nothing to call.

This is a discipline question more than a syntax question. A
Repository whose interface forces the caller to remember to "save
after every mutation" has leaked the persistence model upward into
the application code.

**Apply when:** designing a Repository interface. Ask: would this
look strange on `java.util.Set` / `set[Aggregate]` / equivalent? If
yes (an `update()` method, a `flush()` method on the public
interface), reconsider.

### 3. Match Repository style to the store: collection vs persistence

The choice between collection-oriented (`add`/`remove`) and
persistence-oriented (`save`/`saveAll`) is dictated by what the
backing store can track:

- **Collection-oriented** -- when the store is an ORM with a Unit of
  Work / Session that tracks loaded entities (e.g. Hibernate-style
  copy-on-read, SQLAlchemy session, TopLink copy-before-write).
- **Persistence-oriented** -- when the store has no change-tracking:
  key-value stores, in-memory data fabrics, document stores,
  append-only logs.

A persistence-oriented Repository must be `save()`-d on every change;
a collection-oriented one must not. Mixing the two within one bounded
context -- some Repositories collection-oriented, others
persistence-oriented -- is acceptable when each Aggregate has a
genuinely different storage need; mixing the two *for one Aggregate*
is incoherent.

A separate consideration: if the team expects the persistence
mechanism to be swapped later (e.g. relational → key-value), the
persistence-oriented interface ports without rewriting Application-
layer call sites. The cost is the discipline of remembering to call
`save()` -- something the collection-oriented style does not require.
Choose with that swap risk in mind.

**Apply when:** introducing a Repository. Name the persistence
mechanism the implementation will sit on, and pick the style its
capabilities require. Do not pick "save for safety" out of habit if
the Unit of Work already tracks the Aggregate.

### 4. Interface in the domain Module; implementation in infrastructure

The Repository **interface** lives next to the Aggregate it stores --
in the same domain Module (`domain.model.product.ProductRepository`,
not `infrastructure.persistence.ProductRepository`). It is a domain
concept; clients depend on it abstractly.

The **implementation** lives in `infrastructure` (or a peer
implementation Module) and depends on the persistence framework
(Hibernate, SQLAlchemy, MongoDB driver, Coherence, Redis). The
Application Service receives the interface by dependency injection
and never sees the concrete class.

This is the **Dependency Inversion Principle** applied at the
Repository seam: the domain layer must not import the persistence
framework. Crossing that line moves persistence concerns into the
domain and breaks the layering laid out in `architecture.md`.

**Apply when:** creating a new Repository. Two files: the interface
in `domain.model.<aggregate>/`, the implementation in
`infrastructure.persistence/`. If the implementation has any reason
to import a domain class, that is fine; if the *interface* has any
reason to import a framework class, the design is wrong.

### 5. Place nextIdentity() on the Repository

A new Aggregate needs a globally unique identity *before* its
constructor runs. The Repository is the natural place to mint that
identity, because the Repository is what knows the identity domain:

```text
ProductId nextIdentity()
```

Callers do:

1. `id = repository.nextIdentity()`
2. `aggregate = new Aggregate(id, ...)` (often via a Factory Method
   per `factories.md`)
3. `repository.add(aggregate)` *or* `repository.save(aggregate)`

The implementation may use UUIDs, the database's id-generation, a
sequence, or whatever mechanism the persistence layer provides --
that is an implementation choice, not a contract. The contract is "a
fresh, unique, well-typed identity is available on demand from the
Repository, before the Aggregate exists."

**Apply when:** writing a Factory Method or an Application Service
that creates a new Aggregate. The first call is to
`repository.nextIdentity()`; do not generate identifiers ad hoc inside
the domain or the application code.

### 6. Translate persistence exceptions at the Repository boundary

A Repository that lets the persistence framework's exception types
escape -- `ConstraintViolationException`, `IntegrityError`,
`pymongo.errors.DuplicateKeyError`, `OptimisticLockException` --
forces every caller to import the framework just to handle errors.
That is the layering violation Principle 4 forbids, in another form.

The Repository implementation must catch framework exceptions and
re-raise them as **domain or application-layer exceptions** the
caller can name without depending on the framework. A
`ConstraintViolationException` becomes
`IllegalStateException("Aggregate not unique", e)` or, better, a
domain-named exception (`DuplicateProductError`,
`ConcurrentModificationError`) when the failure is a domain-language
concept. The original is preserved as the cause; the type the caller
sees is one the domain owns.

**Apply when:** implementing a Repository method that can throw. The
`try` boundary belongs *inside* the Repository implementation, not
above it. If the application layer ever has to import the persistence
framework to catch an exception, the boundary is in the wrong place.

### 7. Do not use the Repository to bypass the Aggregate boundary

A Repository that returns whole Aggregates is doing its job. A
Repository that returns *parts of* an Aggregate -- inner Entities,
collection-only slices -- is on thin ice and must obey two rules:

1. The path it exposes must be **a path the Root already permits by
   navigation**. Returning an inner Entity that the Root does not
   expose violates the Aggregate contract (`aggregates.md`,
   Principle 7) and creates an alternative mutation path no one else
   can see.
2. The reason must be a **measured performance bottleneck**, not
   client convenience. "It is annoying to load the Root just to read
   one child" is not a reason; "navigation through the Root caused a
   90th-percentile bottleneck under load" is.

The same caution applies to **use-case-optimal queries** that return
a query-shaped Value Object across multiple Aggregates. They are
allowed (Principle 8), but they must be Value Objects, not
Aggregate-internal Entities, and they must not be the Repository's
default mode of access.

**Apply when:** tempted to add `findChildById(parentId, childId)` to
the parent's Repository. First, check the Root navigation path:
`parent.children().byId(childId)`. If that exists and works, use it.
If the bottleneck has been measured, then add the finder; document
the reason in the spec.

### 8. Many use-case-optimal queries are a code smell

A **use-case-optimal query** is a finder that returns a Value Object
shaped for a specific UI / use case, composing data from one or more
Aggregates without rehydrating each. Vernon names them legitimate:

> "It should not seem strange for a Repository to in some cases
> answer a Value Object rather than an Aggregate instance." --
> Vernon Ch. 12

But:

> "If you find that you must create many finder methods supporting
> use case optimal queries on multiple Repositories, it's probably a
> code smell. ... this situation could be an indication that you've
> misjudged Aggregate boundaries and overlooked the opportunity to
> design one or more Aggregates of different types. The code smell
> here might be called *Repository masks Aggregate mis-design*." --
> Vernon Ch. 12

When that smell appears, the response is:

1. **First**, re-examine Aggregate boundaries (`aggregates.md`,
   Principle 2 -- modeling true invariants). The right Aggregates
   may simply not have been drawn yet.
2. **If boundaries are right**, consider CQRS: a separate read model
   shaped for queries, sourced asynchronously from the write model's
   Domain Events. See `architecture.md` and `domain-events.md`.
3. **What is not the answer:** piling more cross-Aggregate finders
   onto the Repository until it becomes a query layer in disguise.

**Apply when:** the Repository's finder count is climbing past the
number of true Aggregate-shaped queries the domain has. Pause and
do step 1 before adding the next finder.

### 9. Transactions belong in the Application Service

> "The domain model and its encompassing Domain Layer is never the
> correct place to manage transactions." -- Vernon Ch. 12

The Application Service starts and commits the transaction; the
Repository participates in whichever Session / Unit of Work the
Application Service has bound to the current request; the Aggregate
knows nothing about transactions at all. Whether the transaction is
declared (annotation, decorator, framework middleware) or
hand-managed (`with session.begin(): ...`), the **start/commit/rollback
site is the Application Service**, not the Repository or the
Aggregate.

This is also the place the **one-Aggregate-per-transaction rule**
(`aggregates.md`, Principle 1) lives in code: the Application Service
chooses how many Aggregates to commit in one transaction. A
Repository that opens its own transaction per call subverts that rule
by hiding the boundary the Application Service is supposed to own.

> "Be careful not to overuse the ability to commit modifications to
> multiple Aggregates in a single transaction just because it works
> in a unit test environment. ... what works well in development and
> test can fail severely in production because of concurrency
> issues." -- Vernon Ch. 12

**Apply when:** writing an Application Service or a Repository
method. The Application Service owns the `with` / `@transactional`
block; the Repository methods are short, do their work, and return.
Repositories do not begin or commit transactions of their own.

### 10. Test the real Repository against the real store; test clients in-memory

Two test surfaces, two strategies:

- **Tests of the Repository implementation itself** must run against
  the **real persistence backend** (real database, real cache, real
  document store). A mocked SQL session is not a test of the
  Hibernate / SQLAlchemy / Coherence implementation; it is a test
  of the mock. The Repository test proves the implementation
  honours the contract under the actual driver.
- **Tests of code that *uses* a Repository** (Application Services,
  Domain Services) should run against an **in-memory implementation
  of the same interface** -- a `HashMap` / `dict`-backed class that
  satisfies the Repository contract. This keeps client tests fast
  and free of database fixtures, while still exercising the real
  interface (no mocks).

Tests against the real store must clean up after themselves
(`tearDown` removes everything the test added), since persistent
state outlasts the JVM / process and will pollute later tests.

A useful side-effect of the in-memory implementation: when the
Repository is persistence-oriented, the in-memory version can count
`save()` invocations, letting Application-Service tests assert "this
use case wrote exactly one Aggregate."

**Apply when:** writing tests around persistence. The real
Repository's tests use the real backend; everyone else's tests use
the in-memory implementation. Do not mock Repository methods on the
client side -- if the in-memory implementation does not exist yet,
write it.

## What this shard does **not** govern

- **The persistence framework's internals** -- ORM mappings, schema
  migrations, indexing, sharding, replication. The Repository sits
  on top of those; this shard governs what the *interface* looks
  like, not how the bytes get to disk.
- **The Aggregate's invariants and shape** -- those live in
  `aggregates.md`. A Repository does not enforce invariants; the
  Aggregate Root does. The Repository only persists and retrieves.
- **CQRS read models** -- when the answer to "many use-case-optimal
  queries" is CQRS (Principle 8), the read model is governed by
  `architecture.md`. The read model is *not* a Repository.
- **Cross-Bounded-Context data access** -- a Repository is *inside*
  one bounded context. Reading data owned by another context goes
  through that context's Open Host Service / Published Language,
  not through a foreign Repository (`bounded-contexts.md`,
  `context-maps.md`).
- **Event Store mechanics** -- the durable store of Domain Events
  has Repository-like aspects but is governed by `domain-events.md`,
  not this shard.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `aggregates.md` -- the Aggregate the Repository persists; the
  Repository must not expose paths the Root forbids (Principle 7
  here, Principle 7 there); transactions and the
  one-Aggregate-per-transaction rule (Principle 9 here, Principle 1
  there).
- `factories.md` -- the Factory creates the new Aggregate; the
  Application Service then calls `repository.add(...)` /
  `repository.save(...)` (Principle 5 here, Principle 6 there).
- `entities.md`, `value-objects.md` -- typed identifiers minted by
  `nextIdentity()` (Principle 5 here, `value-objects.md`
  Principle 5); Standard Type as the alternative to a polymorphic
  hierarchy (Principle 1 here, `value-objects.md` Principle 7).
- `services.md` -- Domain Services may use Repositories;
  Application Services own the transaction surrounding Repository
  calls (Principle 9 here, `services.md` Principle 5).
- `domain-events.md` -- a Domain Event published by the Aggregate
  is persisted in the same transaction as the Aggregate change
  (`domain-events.md` Principle 7); the Repository participates in
  that transaction.
- `architecture.md` -- the Repository implementation lives in
  `infrastructure`; the interface lives in `domain.model`. CQRS
  read models, when chosen as the response to Principle 8, are
  governed there.
- `modules.md` -- the Repository interface lives in the same Module
  as its Aggregate; the implementation lives in an `infrastructure`
  Module. Module discipline (`modules.md` Principle 8) applies on
  both sides.
- `bounded-contexts.md`, `context-maps.md` -- a Repository belongs
  to one context; cross-context reads go through Open Host Service
  / Published Language, not foreign Repositories.
- `../contracts.md` -- a Repository interface consumed beyond its
  bounded context (rare; usually only Application Services consume
  it) is a contract; renaming or reshaping the public interface is
  a contract change.
- `../refactoring.md` -- swapping a Repository implementation
  (Hibernate → SQLAlchemy, MongoDB → Postgres) is exactly the kind
  of behavior-preserving change refactoring exists for, *provided
  the public interface is unchanged*; if the interface changes, it
  is a contract change.
