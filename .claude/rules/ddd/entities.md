---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- entities

Tactical-design principles for **modeling Entities**: when a concept
deserves an Entity, how to give it identity, how to keep that identity
stable, how to discover its intrinsic characteristics from the
Ubiquitous Language, and how to validate it. Distilled from
*Implementing Domain-Driven Design*, Chapter 5 ("Entities").

This shard covers **what an Entity is and how to design one**. For Value
Objects (the immutable counterpart) see the value-objects shard when it
lands; for Aggregates (clusters of Entities + Values with a Root and an
invariant boundary) see the aggregates shard when it lands. For the
index of shards, see `principles-hub.md`.

## When to model a concept as an Entity

> "When an object is distinguished by its identity, rather than its
> attributes, make this primary to its definition in the model. Keep the
> class definition simple and focused on life cycle continuity and
> identity." -- Evans, quoted in Ch. 5

Two characteristics, both required:

- **Individuality.** The business cares about distinguishing this
  thing from every other thing of the same type, even when their
  attributes coincide.
- **Continuous change.** The thing has a life cycle. Its attributes
  change over time, sometimes substantially, while the business still
  treats it as the same thing.

If only one of those is true, reach for a different building block:

- Individuality without mutation -> often a **Value Object** carrying
  an identifier, not an Entity.
- Mutation without individuality -> often a Value Object that is
  *replaced* rather than mutated.
- Neither -> probably a Value, a calculation, or a transient DTO.

**Anti-pattern:** modeling everything as an Entity because it has a
database row. A row is a persistence concern, not a domain one. Many
"entities" in a CRUD-style app are really Values that the schema
happens to store with surrogate keys.

## Principles

### 1. Identity is the Entity's primary attribute -- design it first

In early modeling, ignore most attributes and behaviors and focus only
on what identifies the Entity and what is essential to find it. Add
other state and behavior only as it earns its place. An Entity that
starts as a bag of fields tends to stay that way.

**Apply when:** introducing a new Entity in a spec or in code. The first
question is "how is this uniquely identified, and who issues that
identity?" -- not "what columns does it have?".

### 2. Pick one of four identity-generation strategies, explicitly

Four origins of unique identity recur. A spec must name which one
is in force for each Entity:

- **User-provided.** The user types or selects a value the system then
  treats as identity. Cheap, but the system must enforce uniqueness, and
  user-corrected identities require an explicit policy.
- **Application-generated.** The application produces the identity (UUID
  or comparable algorithm) at construction time. Default for most
  Entities; gives the model full control over timing and uniqueness.
- **Persistence-generated.** A database (sequence, auto-increment) issues
  the identity. Convenient, but the Entity has no identity until it has
  been persisted -- ripple effects on construction, equality,
  in-flight events, and tests.
- **Assigned by another bounded context.** An upstream context owns the
  identity; this context records and references it. The translation of
  the foreign identifier into the local model is part of the
  Anticorruption Layer (see `context-maps.md`).

The choice has design consequences. Persistence-generated identity
forces "saved vs unsaved" reasoning into the domain. Foreign-assigned
identity adds a coupling the spec must own. Pick deliberately; do not
let an ORM choose for you by accident.

### 3. Identity is stable: protect it from modification

Once assigned, an Entity's identity does not change. Enforce this in the
type itself, not by convention:

- The identity is set exactly once -- in the constructor or a Factory
  method.
- Setters for the identity field either do not exist or guard against
  re-assignment when the field is already populated.
- Equality and hashing are defined on identity, not on mutable fields.

If the business genuinely permits identity correction (e.g. fixing a
typo in a user-provided identifier), model the correction as an explicit
domain operation with its own name and Domain Event, not as a silent
mutation.

**Apply when:** writing the Entity's constructor and setters; reviewing
any code that touches the identity field.

### 4. Surrogate identity is a persistence concern; hide it from the model

When the persistence mechanism (ORM, table) wants its own primary key
type that does not match the domain identity, give the Entity **two**
identities:

- The **domain identity** -- meaningful in the Ubiquitous Language,
  used by clients, used in equality.
- The **surrogate identity** -- a primary-key value the persistence
  layer cares about, hidden from clients of the domain.

Hide the surrogate behind protected accessors on a Layer Supertype or
similar. Domain code, tests, and other contexts must not be able to
observe or use the surrogate; if they can, persistence has leaked into
the model.

**Apply when:** introducing an ORM-mapped Entity, or noticing that
clients are reaching for a numeric `id` instead of the domain
identifier.

### 5. Discover Entities from the Ubiquitous Language, not from a schema

Read the language out loud. Watch for:

- **Verbs of change** ("change," "rename," "deactivate," "expire") --
  the noun being changed has a life cycle, which usually implies an
  Entity.
- **Words that imply search or resolution** ("authenticate," "find,"
  "look up by," "match against") -- the resolved noun needs unique
  identity to be found among many of its kind.
- **Lifecycle states** ("active," "deactivated," "pending,"
  "registered") -- usually an Entity carrying a state.

Capture these in the spec's glossary as they are uncovered. The
glossary is a working artifact; the truth is the code.

**Anti-pattern:** distilling a model by listing all the nouns and
making each one a class. The first pass yields too many Entities, most
of which are really attributes, Values, or roles.

### 6. Behavior on the type that owns the invariant

This is the foundational anemic-model cure (see hub Foundations),
expressed at the Entity level: every business rule that constrains an
Entity's state lives on that Entity, not in a service that pokes its
fields. A method named in the Ubiquitous Language
(`backlogItem.commitTo(sprint)`, `tenant.deactivate()`) replaces a
service method that mutates several fields by name.

Symptoms of the anti-pattern, restated for Entities specifically:

- Setters are public and called from application services to assemble
  state piece by piece.
- The Entity has no methods named in domain terms -- only `getX` /
  `setX`.
- A service layer holds if/else trees that decide what state
  combinations are legal.

Cure: **constructors and command methods enforce the invariant in one
step**. Self-encapsulate by having the constructor delegate to internal
setters that guard their preconditions. The caller cannot land the
Entity in a half-valid state.

**Apply when:** an application service is about to call more than one
setter on an Entity in sequence to "build it up." That sequence is the
domain operation; name it and put it on the Entity.

### 7. Use a Factory when construction is non-trivial; let the parent be the Factory

When creating an Entity requires coordination -- enforcing a parent's
identity on the child, validating a multi-field invariant at birth,
emitting a Domain Event on creation -- put creation behind a Factory
method rather than a public constructor. A common shape: the **parent
Entity is the Factory** for its children, and the child's constructor
is package-/module-private so nothing else can instantiate it.

This keeps "you cannot have a `User` without a `Tenant` that
registered them" expressible in the type system rather than in prose.

(Factory patterns are covered in detail in their own future shard;
this shard only notes when an Entity needs one.)

### 8. Entities can play roles, but be wary of multi-role objects

A class plays a role; an interface is the explicit name of that role.
A single Entity may legitimately implement multiple role interfaces
when those roles share identity and lifecycle.

Caution: a single object that *delegates* to multiple sub-objects
to implement its roles risks **object schizophrenia** --
the delegates lose track of the originating identity, and behavior
that depends on identity becomes ambiguous. Symptoms: forwarding
methods that do not know which "self" to act on, conditional
delegation that picks among nullable sub-objects.

Default: prefer fine-grained role interfaces on a single Entity over
forwarding/delegation across multiple objects. Reach for delegation
only when the roles have genuinely different lifecycles.

### 9. Validate at three levels; do not bake validation into the Entity

Validation answers three different questions, and they should not be
collapsed into one:

- **Attribute / property validation.** A single field's value is sane
  in isolation (non-null, in range, format-conformant). Enforce as
  guards in the Entity's setter or constructor; the field cannot be set
  to garbage in the first place.
- **Whole-object validation.** All of this Entity's fields are
  individually valid *and* their combination is consistent. Often
  changes more frequently than the Entity itself, and benefits from
  living in a separate Validator (Specification or Strategy) sited
  alongside the Entity, with at least package-scope access to the
  Entity's accessors. The Validator collects all violations through a
  notification handler rather than throwing on the first failure.
- **Composition validation.** A cluster of Entities (or Aggregates)
  is valid together. Belongs in a Domain Service, which uses
  Repositories to load what it needs and may be triggered by a Domain
  Event signalling that the cluster has reached a state where
  validation is meaningful.

**Anti-pattern:** a single `validate()` method on the Entity that
mixes all three. It tangles concerns that change at different rates
and forces the Entity to know about cross-aggregate state it should
not see.

**Apply when:** adding a check. Decide which level it belongs to
before writing it. Field-level guards stay on the Entity; whole-object
checks go in a Validator; cross-Entity checks go in a Domain Service.

### 10. Track changes only when domain experts care

By definition, an Entity's history is not part of its identity -- only
its current state must be supported. Adding change tracking is a
*choice* with a cost.

Reach for change tracking when domain experts ask questions like
"who changed this and when?", "what did this look like before that
event?", or "show me every state transition this thing went through."

The mechanism: a unique **Domain Event** type for every important
state-altering command on the Entity, published as part of the command
method, and recorded by a subscriber. The Event name + properties is
the audit record; do not invent a parallel "audit log" data structure
that the Entity must keep in sync with itself.

Adopt full **Event Sourcing** only when the simpler shapes (audit
columns, append-only event subscribers, periodic snapshots) cannot
carry the requirement -- see `architecture.md` Principle 9.

## What this shard does **not** govern

- Aggregate boundaries, Aggregate Roots, transactional consistency
  inside a cluster of Entities -- that is the future aggregates shard.
- Repository design and persistence patterns -- those are the future
  repositories shard.
- Value Objects (immutable, equality-by-value, replace-not-mutate) --
  that is the future value-objects shard.
- The exact constructor / setter / factory idioms in any one
  language -- this shard governs the *shape*; service-specific
  conventions handle the syntax.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards, anemic-model warning,
  DDD-Lite trap.
- `bounded-contexts.md` -- an Entity belongs to exactly one bounded
  context; its name lives in that context's Ubiquitous Language.
- `context-maps.md` -- when an identity is assigned by another
  context, the translation of the foreign identifier is an ACL
  concern.
- `architecture.md` -- the Entity lives in the domain layer; setters
  and command methods are domain-side; Validators and Domain
  Services that use them sit in the application/domain layers per
  the Layers + DIP principle. Event Sourcing as a way to track
  change is a high-cost architectural choice (Principle 9 there).
- `../contracts.md` -- a wire schema is its own type; do not return an
  Entity directly over HTTP.
- `../refactoring.md` -- renaming an Entity, its identity field, or
  its command methods is a public-contract change in the
  Ubiquitous-Language sense; update all dependents and the glossary
  in the same change.
