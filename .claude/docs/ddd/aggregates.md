# DDD shard -- aggregates

Tactical-design principles for **Aggregates**: how to draw the
transactional consistency boundary, how to size it, how to reference
across boundaries, how to keep separate Aggregates eventually
consistent without sneaking back into multi-Aggregate transactions,
and how to implement Aggregate Roots so clients cannot bypass them.
Distilled from *Implementing Domain-Driven Design*, Chapter 10
("Aggregates").

This shard covers **what an Aggregate is and how to design one**.
For the Entity at its Root, see `entities.md`. For the Value parts
inside it, see `value-objects.md`. For the Events it emits when its
state changes, see `domain-events.md`. For the index of shards, see
`principles-hub.md`.

## What an Aggregate is, here

An Aggregate is a **cluster of Entities and Values around a single
Root Entity that, together, enforce a set of true business
invariants in one transaction**. The Root is the only entry point;
clients hold references only to the Root; the Root mediates all
state changes and emits Events when commands succeed.

> "A properly designed Aggregate is one that can be modified in any
> way required by the business with its invariants completely
> consistent within a single transaction. And a properly designed
> Bounded Context modifies only one Aggregate instance per
> transaction in all cases. ... we cannot correctly reason on
> Aggregate design without applying transactional analysis."
> -- Ch. 10

Three forces motivate Aggregates:

- **Protect invariants** that span more than one piece of state by
  putting all that state inside one boundary.
- **Bound transactional scope** so concurrent users don't collide on
  unrelated parts of a large object graph.
- **Enable scale and distribution** by making the unit of storage
  and transport independent of the rest of the model.

The pattern rewards careful sizing. Get the boundary too big and
the system fights itself with concurrency conflicts; too small and
true invariants leak into application code where they decay.

## Principles

### 1. Aggregate is a consistency boundary; one Aggregate per transaction

The single most load-bearing rule of the pattern: **one user
request modifies one Aggregate instance**. If a command needs to
change state in two Aggregates, the second change happens in a
later, separate transaction (typically driven by a Domain Event;
see `domain-events.md` Principle 4).

This is what makes Aggregates a useful design tool. It is also what
makes the size of the boundary matter: every piece of state inside
the boundary contends with every other piece on every commit. A
sprawling Aggregate is a sprawling lock.

Under optimistic concurrency, the rule shows up as: only one of two
concurrent requests touching the same Aggregate succeeds; the other
sees a stale-version error and retries. That is the behavior you
want -- it is the model defending an invariant. Disabling
optimistic locking to "fix" the conflict is the wrong instinct;
the correct fix is usually to discover that the supposed invariant
isn't real and to break the Aggregate up.

**Apply when:** designing or reviewing the consistency boundary.
For every multi-Aggregate operation in a use case, name which
Aggregate gets the transaction and which one(s) catch up via
Events.

### 2. Model true invariants, not compositional convenience

> "An invariant is a business rule that must always be consistent."
> -- Ch. 10

A **true invariant** is a rule the business genuinely requires to
hold at every commit: "the sum of line-item amounts must not
exceed the order's credit limit," "a backlog item's status must
reflect the remaining hours on its tasks." Invariants are the
*only* legitimate reason to glue state together inside one
Aggregate.

A **false invariant** is a developer-imposed constraint that
sounds protective but isn't a real business rule. Example: "if a
backlog item is committed to a sprint, we must
not allow it to be removed from the system." Plausible-sounding,
but not actually a business rule -- the business has other ways
to prevent inappropriate removal (authorization, soft-delete,
workflow). Treating it as an invariant pulls the entire
collection of backlog items into a single `Product` Aggregate
and reproduces the large-cluster failure mode at scale.

The diagnostic: if removing the rule would *not* cause the
business to lose money, lose data integrity, or fail an audit,
it is not an invariant. It is a convenience or a workflow, and
it belongs elsewhere -- in an Application Service, an
authorization check, a Domain Event subscriber.

**Apply when:** drawing an Aggregate boundary. Write the
invariants the boundary protects on a list. If the list is
empty, the boundary is wrong (or too large). If the list is
"because they always travel together," that is grouping, not
invariant -- consider splitting.

### 3. Design small Aggregates; prefer Root plus Values

> "Limit the Aggregate to just the Root Entity and a minimal
> number of attributes and/or Value-typed properties." -- Ch. 10

Default Aggregate shape: a Root Entity, a handful of attributes,
and several Value-typed properties (per `value-objects.md`
Principle 1). Add Entity parts only when an invariant demands
that the parts have their own identity *and* must change
together with the Root in a single transaction. Roughly 70% of
real Aggregates fit Root-plus-Values; ~30% need two or three
Entities. Treat that ratio as a sanity check, not a
quota.

Smaller Aggregates win on every dimension: less to load (lazy
loads matter less when the eager set is small), less memory, less
contention under optimistic locking, easier serialization in
key-value or document stores, easier reasoning. The cost of
"smaller than necessary" is one extra Repository call from an
Application Service; the cost of "larger than necessary" is
unbounded.

When the boundary feels too small to express a concept, that is
often a hint that the concept itself is missing -- a new named
Aggregate that wraps the relationship, rather than swelling an
existing one.

**Apply when:** designing a new Aggregate, or noticing collections
inside an existing Aggregate that grow without bound. Default to
Root + Values; justify each Entity part with a named invariant.

### 4. Reference other Aggregates by identity, not direct reference

Inside an Aggregate, hold the **identity** of any other Aggregate
you need to know about (`ProductId`, `TenantId`, `SprintId`), not
a direct object reference. `BacklogItem.productId` is right;
`BacklogItem.product` is wrong.

Why this rule:

- It mechanically prevents accidental two-Aggregate transactions.
  If you don't hold the reference, you can't accidentally
  `product.somethingThatMutates()` from inside `BacklogItem`.
- It keeps Aggregates small. Direct references invite eager
  loading; identity references do not.
- It enables distribution. Identity-only references survive
  storage partitioning, cross-context delivery, and
  serialization in document or key-value stores.
- It enforces the typed-identity discipline (`value-objects.md`
  Principle 5). Each Aggregate's id is a Value, distinguishable
  at the type system, so wrong-id-passed errors fail to compile.

When a use case genuinely needs the related Aggregate's data, the
Application Service looks it up via its Repository before
invoking the command, then passes the resolved object (or the
relevant subset) into the Aggregate's method:

```text
ApplicationService.handle(...)
  product       = productRepo.byId(productId)
  backlogItem   = backlogItemRepo.byId(backlogItemId)
  backlogItem.commitTo(sprint)         # the command takes the loaded peer
```

For complex resolution that the Aggregate must drive itself, pass a
Domain Service into the command method (double-dispatch). Do **not**
inject a Repository or a Domain Service as a constructor field on
the Aggregate (Principle 8).

**Apply when:** modeling references between Aggregates. Default to
typed identity. Reach for a direct reference only with a written
reason -- usually a query-performance trade-off you have measured.

### 5. Use eventual consistency outside the boundary

> "Any rule that spans AGGREGATES will not be expected to be
> up-to-date at all times. Through event processing, batch
> processing, or other update mechanisms, other dependencies can
> be resolved within some specific time." -- Evans, quoted in
> Ch. 10

Once the boundary is drawn, every cross-boundary rule is
**eventually consistent by default**. The publishing Aggregate
emits a Domain Event; subscribers (in the same context or in
remote ones) load the corresponding Aggregate(s) in their own
transactions and apply the change. Concurrency conflicts on the
subscriber side resolve by retry; persistent failures escalate
to a compensating action or human review.

Domain experts are usually far more comfortable with eventual
consistency than developers expect. The right tolerance window
is a domain question (`domain-events.md` Principle 9): seconds,
minutes, hours, even days are all viable depending on the
business; the architecture follows from the answer, not the
other way around.

**Apply when:** a use case requires multiple Aggregates to end
up in agreement. Ask the domain expert how stale the second
Aggregate is allowed to be; encode that tolerance as the
Event-propagation budget.

### 6. Break ties with "whose job is it?"

When a use case is genuinely ambiguous between transactional
and eventual consistency -- the team can argue both ways --
ask: **whose job is it to bring the second Aggregate into
consistency?**

- If it is **the same user, in the same request**, lean toward
  transactional consistency (and accept that this is a hint to
  re-examine the Aggregate boundary -- maybe the two Aggregates
  are actually one missing concept).
- If it is **another user, the system, or a downstream process**,
  use eventual consistency.

This tie-breaker is credited to Evans. It is more useful than
"transactional feels safer" or "eventual is more modern" because
it lifts the question into the domain: it forces the team to name
the responsible actor, which often surfaces an invariant that was
hiding in the fog.

**Apply when:** a designer is split between transactional and
eventual. Name the actor responsible for the cross-Aggregate
consistency before choosing the technique.

### 7. Tell-Don't-Ask and Law of Demeter at the Root

The Aggregate Root is the **only entry point for state-changing
commands**. Clients invoke methods on the Root; the Root
delegates internally to its parts. Inner parts may be queried
(read-only navigation is fine in moderation), but their
state-mutating methods are not part of the public surface --
typically `protected` or package-private, reachable only from
the Root.

Two complementary disciplines:

- **Tell, Don't Ask.** Clients tell the Root what business
  outcome they want (`product.reorderFrom(itemId, position)`),
  not "give me your collection so I can mutate one element."
  The Root is what knows how to keep its own invariants.
- **Law of Demeter.** A method may invoke methods only on
  itself, its parameters, objects it constructed, and its own
  directly held parts. Two-step traversals
  (`order.lineItems().get(0).setPrice(...)`) are the smell that
  the Root's interface is missing a command.

The Root's command methods are also the natural points to
**publish Domain Events** when the command succeeds (see
`domain-events.md` Principle 5). The Aggregate emits the fact;
the surrounding Application Service decides what to do with it.

**Apply when:** writing or reviewing an Aggregate's public API.
For every state-changing operation a use case needs, there is
exactly one Root-level command method that performs it. If the
test has to call several methods in sequence to set state up,
the API is missing a command.

### 8. Look up dependencies in the Application Service, not the Aggregate

Do **not** inject a Repository or a Domain Service into an
Aggregate as a constructor field. The "Disconnected Domain Model"
pattern -- Aggregates that wake up holding a
reference to their persistence layer -- couples the model to
infrastructure, makes Aggregates hard to test, and bloats every
in-memory instance with framework references.

The right shape:

- An **Application Service** loads the Aggregate via its
  Repository, loads any peers the command needs via theirs, and
  invokes the command, passing peers in as arguments.
- For cases where the Aggregate genuinely must drive a complex
  resolution, **double-dispatch a Domain Service** into the
  command method as a parameter. The dependency is scoped to the
  call, not held on the Aggregate.

This rule is consistent with `services.md` Principle 5
(Repositories from Services, not Aggregates) and Principle 4
(push multi-step composition off the client into a Service when
the orchestration is domain-shaped).

**Apply when:** drafting an Aggregate's constructor or methods.
The constructor takes domain state and identity Values. Methods
take command arguments and, if necessary, transient
dependencies. Persistence and Domain Service references do not
live on the Aggregate.

### 9. Place optimistic concurrency where the invariant lives

Optimistic concurrency control normally rides on the Aggregate
Root: every state-changing command bumps the Root's version, and
two concurrent commits collide on it.

When the boundary contains Entity parts and a part change must
trigger the same conflict-detection (because the part participates
in a Root-level invariant), the operation that mutates the part
must also mutate something on the Root that the persistence layer
sees as a state change. The cleanest version of this is to mutate
a legitimate domain field on the Root as part of the operation
(e.g. when a `Task`'s zero-hours estimate transitions the parent
`BacklogItem`'s status to `done`, the `BacklogItem`'s status is
the legitimate Root field that takes the bump). Avoid
hooking the persistence layer to silently dirty the Root --
that pulls infrastructure into the model.

When part-level versioning suffices because the parts protect
their own independent invariants (no Root-spanning rule), letting
each Entity part carry its own version is fine. Last-writer-wins
on a part is acceptable when the only "rule" is "two users
shouldn't blindly clobber each other on this part."

When versioning the Root for part changes becomes structurally
painful, it is usually a signal the parts should not be Entity
parts at all -- collapse to Root + Values where the Root
inherently moves with every change, or extract the part to its
own Aggregate referenced by identity.

**Apply when:** designing the concurrency strategy for an
Aggregate with Entity parts. Name which invariants live at the
Root and which live within parts; place the version field at the
level of the invariant.

### 10. Break the rules deliberately, naming the reason

The rules above are rules of thumb, not laws. Four concrete
situations recur where an experienced practitioner may modify
multiple Aggregates in one transaction; the discipline is that
each break is named, not implicit:

- **User-interface batch creation.** A "create N items at once"
  flow that creates N independent Aggregates is semantically a
  loop of single-Aggregate creates. The transaction boundary is
  cosmetic, not invariant-bearing.
- **No technical mechanism for eventual consistency.** No queue,
  no scheduler, no background worker available -- and "build
  one" is genuinely off the table. Pair the rule break with
  user-aggregate affinity (only one user touches the involved
  Aggregates at a time) to keep contention low.
- **Required global transactions** (legacy / policy /
  cross-store XA). The system cannot escape multi-resource
  transactions; minimize how many Aggregates participate, but
  accept that some commits span more than one.
- **Query performance.** A direct reference between Aggregates
  -- breaking Principle 4 -- is justified by a measured query
  cost, not by anticipated convenience.

The discipline is **explicit cost accounting**, not absence of
exceptions. Each rule break is in the spec, says "we are
breaking rule X for reason Y," and lists the trade-off the team
accepts (worse scalability, narrower concurrency, riskier
distribution). When the reason expires, the break is undone.

**Apply when:** a design appears to require breaking one of the
rules above. Name the reason (one of the four, or an explicit
new one) before merging; remove the break when the reason
no longer applies.

## What this shard does **not** govern

- Repository design (how Aggregates round-trip to storage,
  identity generation, query shapes) -- that is `repositories.md`.
  This shard governs *what* an Aggregate is;
  the Repository is *how* it is fetched and stored.
- Factory design (how Aggregates are constructed, with or
  without their parents) -- that is `factories.md`. Factory
  Methods on the Root for child Aggregate creation are
  consistent with this shard but their full design lives there.
- The detailed Entity / Value implementation idioms that go
  inside an Aggregate. Those live in `entities.md` and
  `value-objects.md`; this shard assumes them.
- Sagas / Process Managers that orchestrate work across
  Aggregates over time. Those build on `domain-events.md`
  Principle 4 and `application.md`.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards, anemic-model
  warning, DDD-Lite trap.
- `entities.md` -- the Aggregate Root is an Entity; identity
  stability, identity strategies, and Layer-Supertype surrogate
  identity all apply here. Inner Entity parts also follow that
  shard's rules.
- `value-objects.md` -- prefer Value parts inside the Aggregate;
  the Root's identity is itself a Value (Principle 5 there).
- `services.md` -- Aggregates do not call Repositories
  (Principle 5 there) and do not host multi-step orchestration
  (Principle 4 there); both belong in Domain or Application
  Services.
- `domain-events.md` -- the Aggregate is the Event publisher;
  one-Aggregate-per-transaction (Principle 4 there) is the rule
  that motivates the entire Events pattern.
- `bounded-contexts.md` -- an Aggregate lives in exactly one
  bounded context's Ubiquitous Language; the same English term
  in two contexts is two different Aggregates with two
  different invariant sets.
- `modules.md` -- Aggregates are the cohesion units that drive
  Module design (Principle 2 there); Module boundaries follow
  Aggregate boundaries, not the other way around.
- `architecture.md` -- the persistence and concurrency
  mechanisms (optimistic locking, document vs row storage,
  CQRS) live in the architectural layer; this shard governs
  what they protect.
- `../../rules/contracts.md` -- the Aggregate's command method
  signatures and emitted Event payloads are public contracts
  in the Ubiquitous-Language sense; renaming or reshaping them
  is a cross-callsite change, not a free internal refactor.
- `../refactoring.md` -- splitting or merging Aggregates is
  one of the most consequential refactors in the model;
  treat it as a deliberate design move, not a cleanup.
