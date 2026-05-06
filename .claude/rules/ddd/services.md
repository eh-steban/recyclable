---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- services

Tactical-design principles for **Domain Services**: when an operation
genuinely does not belong on an Entity or Value Object, how to express
it without slipping into an Anemic Domain Model, how it differs from
an Application Service or an SOA "service," and how to keep clients of
the model thin. Distilled from Vaughn Vernon, *Implementing
Domain-Driven Design*, Chapter 7 ("Services").

This shard covers **what a Domain Service is and how to design one**.
For Entities, see `entities.md`. For Values, see `value-objects.md`.
For the index of shards, see `principles-hub.md`.

## What a Domain Service is (and is not)

> "When a significant process or transformation in the domain is not a
> natural responsibility of an ENTITY or VALUE OBJECT, add an operation
> to the model as a standalone interface declared as a SERVICE. Define
> the interface in terms of the language of the model and make sure the
> operation name is part of the UBIQUITOUS LANGUAGE. Make the SERVICE
> stateless." -- Evans, quoted in Vernon Ch. 7

A Domain Service is a **stateless operation that fulfills a
domain-specific task**. Three legitimate uses, per Vernon:

- Perform a significant business process.
- Transform a domain object from one composition to another.
- Calculate a Value that requires input from more than one domain
  object.

Three things it is **not**:

- **Not an Application Service.** Application Services coordinate
  (transactions, security, calls into the model); they hold no
  business logic. Domain Services hold business logic. The natural
  client of a Domain Service is an Application Service.
- **Not an SOA / RPC / messaging service.** Coarse-grained,
  remote-capable, transactional integration components live at a
  different layer (see `architecture.md`). A Domain Service is a
  fine-grained operation inside one bounded context's model.
- **Not a static method on an Aggregate Root.** When an operation feels
  out of place on an Entity or Value, the reflex to "make it static on
  the Aggregate class" is a code smell. The right answer is a Service.

## Principles

### 1. Default to Entity / Value behavior; justify every Service

Before introducing a Service, ask: does this behavior belong on the
type that owns the invariant it enforces? Most of the time, the answer
is yes -- and putting the behavior there makes the Ubiquitous Language
more expressive, not less. Reach for a Service only when the operation
genuinely does not fit on any single Entity or Value, and write down
why in the spec.

**Apply when:** a method is about to be added that touches two or more
Aggregates, or that does work whose home is unclear. If you can't name
the type that "owns" the behavior, that's a hint -- but check whether
splitting or renaming a domain type would give the behavior a natural
home before reaching for a Service.

### 2. Make Services stateless

A Domain Service holds **behavior, not state**. No per-call data
survives on the instance; instances must be safe to share, swap, and
re-enter concurrently. All inputs arrive as parameters, all outputs
leave as return values. Caching, queues, retries, and connection pools
are infrastructure concerns and live behind ports, not on the Service
itself.

**Apply when:** writing a Service. If you find yourself adding a
mutable field, stop -- either the field is dependency-shaped (inject
it through the constructor and treat it as immutable) or the operation
should live on an Entity or Aggregate that legitimately owns the state.

### 3. Name the Service and its operations in the Ubiquitous Language

The Service interface is part of the model's vocabulary. Operations
read as **verbs the team would say out loud**: `authenticate(...)`,
`businessPriorityTotals(...)`, not `isAuthentic(...)` or
`computePriorityData(...)`. The Service's class name is itself a noun
phrase from the language (`AuthenticationService`,
`BusinessPriorityCalculator`).

**Apply when:** naming a new Service or method on one. If the verb
isn't one a domain expert uses, neither the Service's name nor its
home in the model is right yet.

### 4. Push multi-step composition off the client and into the Service

The diagnostic example: when authenticating a user requires "find
Tenant, check active, find User, encrypt password, compare to stored
encrypted password, check enabled," and the *client* is doing that
choreography, **the client is hosting domain logic**. Move the entire
choreography behind a Service operation; the client becomes a
one-liner.

The principle generalizes: any time an Application Service orchestrates
a multi-step interaction with the domain that would mean the same thing
in a different application (CLI, worker, batch job, test), that
choreography is domain knowledge, and it belongs in a Domain Service.
The Application Service's job is task coordination -- transaction
boundaries, security, picking which Service to call -- not assembling
business behavior.

**Apply when:** an Application Service grows beyond simple
"validate input -> call one Service / Aggregate method -> return."
That's the seam to extract a Domain Service.

### 5. Domain Services may use Repositories; Aggregates should not

A Service is the right place to fan out across multiple Aggregates --
that is one of the three reasons it exists. Calling a Repository from
inside an Aggregate is the wrong direction (it inverts the dependency
and pulls infrastructure into the model); calling a Repository from a
Service is fine and expected.

**Apply when:** a calculation or process needs data from several
Aggregates. Put it in a Service that takes the Repositories it needs
as dependencies; do not push the lookup into one of the Aggregates
themselves.

### 6. Separated Interface is optional, not default

Defining `interface FooService` plus `class FooServiceImpl` is
justified only by a concrete decoupling need:

- A **technical** implementation that should live outside the domain
  layer (encryption, hashing, external calls). Place the interface in
  the domain module and the implementation in infrastructure, per the
  Dependency Inversion Principle (see `architecture.md`).
- **Multiple specialized implementations** that the spec actually
  calls for. Each implementation gets a *meaningful* name describing
  its specialty (`MD5EncryptionService`, `Argon2EncryptionService`),
  not a generic `*Impl`.

If the Service has a single, non-technical implementation, a single
class is fine. The `*Impl` naming convention is a smell: if the
implementation deserves a name, give it one; if it doesn't, you
didn't need a separated interface.

**Apply when:** introducing a new Service. Default to a single class.
Promote to interface + implementation only when one of the two reasons
above is named.

### 7. Beware the Service mini-layer drift toward Anemic Domain Model

A growing collection of Services that sit *above* the Entities and
Values, doing work the Entities and Values "could" have done, is the
classic Anemic Domain Model failure mode -- the cost of a domain model
without the benefit. Each new Service should be justified by Principle
1; if the answer is "I just preferred a procedural style here,"
push back.

There are exceptions: an `Identity and Access` context, for example,
legitimately leans on a thin Service layer because much of its work is
cross-Aggregate orchestration (Tenant + User + Group + Role). The
distinction is **whether the Entities still own their invariants**.
If the Entities have collapsed into bags of getters/setters and the
Services hold all the rules, the model is anemic regardless of how
"natural" the layer felt to write.

**Apply when:** reviewing a context's domain layer. Count the
behaviorless Entities; count the Services. If the ratio is tipping
heavily toward Services with thin Entities, the model has rotted and
needs rebalancing, not another Service.

### 8. Test from the client; represent normal failures as return values

Service tests double as the Service's usage manual. Each test reads as
"a client of this model would call it like this, and expect this
back." Cover the happy path and **every domain-normal failure mode**
the Service exposes -- wrong tenant, wrong username, wrong password,
disabled user. These are not exceptional errors; they are normal
outcomes of the operation in this domain.

A domain-normal failure is represented in the **return type**, not as
a thrown exception: `Optional<T>` / `Result<T, E>` / a sum type / a
nullable in languages where that is the idiom. Reserve exceptions for
genuine programmer errors (null required arguments, broken
invariants). The test for a "wrong password" call is `assertNull(...)`
or `assertEqual(result, AuthFailure.WrongPassword)`, not
`assertThrows(...)`.

**Apply when:** writing a Service or its tests. List the failure
modes the domain treats as normal *before* writing the implementation;
each one is a return-shape decision, not an `else throw` afterthought.

## What this shard does **not** govern

- Application Services -- transaction boundaries, security checks,
  request-shape translation, calling into the model. Those are the
  topic of a future application shard (Vernon Ch. 14).
- Domain Events emitted by Services -- a Service may publish Events
  as a final step of its operation; the Event modeling rules belong
  to the future domain-events shard (Vernon Ch. 8).
- Anticorruption-Layer translators between contexts. Those are
  Services in the technical sense but their design is governed by
  `context-maps.md` Principle 3.
- Concrete dependency-wiring style (constructor injection,
  framework DI, manual factory). Vernon is deliberately neutral;
  service-specific conventions choose the form.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards, anemic-model
  warning, DDD-Lite trap.
- `entities.md` -- the first place to look for behavior. A Service
  exists only because the operation didn't fit there.
- `value-objects.md` -- the second place to look. A Service often
  *returns* a Value (e.g., `BusinessPriorityTotals`,
  `UserDescriptor`); the Value's shape is governed there.
- `bounded-contexts.md` -- a Service's name and language belong to
  one bounded context's Ubiquitous Language. The same English verb
  in two contexts is allowed and means different things.
- `context-maps.md` -- cross-context translation Services
  (Anticorruption Layer adapters) are governed there, not here.
- `architecture.md` -- Dependency Inversion places technical Service
  implementations in infrastructure while the interface stays in the
  domain layer.
- `../contracts.md` -- the wire shape of any cross-service operation
  is its own contract; the Service's signature is the *domain* shape,
  not the wire shape.
- `../refactoring.md` -- changing a Service's operation set, its
  argument shapes, or its return type (including the failure
  representation) is a public-contract change in the
  Ubiquitous-Language sense; update all callers in the same change.
