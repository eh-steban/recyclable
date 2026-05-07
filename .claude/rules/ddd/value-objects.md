---
paths:
  - "backend/**"
  - "private/specs/**"
---

# DDD shard -- value objects

Tactical-design principles for **modeling Value Objects**: when a
concept deserves a Value (as opposed to an Entity), what
characteristics every Value must have, how to keep behavior
side-effect-free, where Standard Types fit, and how to keep
persistence concerns from corrupting the model. Distilled from
*Implementing Domain-Driven Design*, Chapter 6 ("Value Objects").

This shard covers **what a Value Object is and how to design one**.
For Entities (the identity-bearing counterpart), see `entities.md`.
For the index of shards, see `principles-hub.md`.

## When a concept deserves a Value, not an Entity

> "When you care only about the attributes of an element of the
> model, classify it as a VALUE OBJECT. Make it express the meaning
> of the attributes it conveys and give it related functionality.
> Treat the VALUE OBJECT as immutable. Don't give it any identity
> and avoid the design complexities necessary to maintain ENTITIES."
> -- Evans, quoted in Ch. 6

The stronger formulation: **bias the model toward Values**.
Default to Value; reach for Entity only when individuality plus a
mutable life cycle are both required (see `entities.md` Principle 1).
Even within an Entity, prefer fields-of-Values over fields-of-Entities
where the language allows.

The reason is simple: a Value can be created, handed off, and
forgotten. Nothing downstream can corrupt it; equality is by
attributes; replacement is the only "mutation." That eliminates an
entire category of bugs at no design cost.

## The five characteristics of a Value

Every Value Object exhibits all five. Missing any one is a signal
that the concept is either an Entity in disguise, or a half-modeled
Value that will accumulate complexity later.

### 1. Measures, quantifies, or describes -- it is not "a thing"

A Value is *about* a thing in the domain; it is not a thing itself.
A person *has* an age; the age measures how long the person has
lived. A monetary amount *describes* the worth of an item. The age
and the amount are not domain things in their own right.

**Heuristic:** if you cannot finish the sentence "this object
*describes* / *measures* / *quantifies* X," the concept is probably
an Entity, or a transient DTO, not a Value.

### 2. Immutable

Once constructed, a Value's state never changes. The constructor
sets every attribute (directly or through self-encapsulating private
setters used only during construction); no public method ever
mutates state.

A Value may *hold a reference* to an Entity for compositional
convenience, but using that reference to mutate the Entity through
the Value's interface defeats the immutability guarantee. Treat
Entity references in Values as read-only viewpoints; if a Value
exists primarily to mutate an Entity, redesign.

### 3. Conceptual Whole -- the Whole Value pattern

A Value's attributes mean something *together* that they do not
mean separately. `{50_000_000, "USD"}` is meaningful as a monetary
amount; `50_000_000` alone is a number, `"USD"` alone is a currency
code. Modeling them as two attributes on the parent Entity forces
every caller to know how to combine them, and the next developer
will combine them differently.

**Anti-pattern:** parent Entity carrying loose related fields
(`amount` + `currency`, `street` + `city` + `postal_code` + `country`,
`min_value` + `max_value`) that always travel together but are not
named together as a type. Promote the cluster to a Value.

> "Each attribute contributes an important part to a whole that
> collectively the attributes describe." -- Ch. 6

### 4. Replaceability

To "change" a Value, replace the reference with a new instance.
Mutation does not exist in this vocabulary. `total = 4` replaces
`total = 3`; you do not modify the integer 3. The same applies to
compound Values: `name = name.withMiddleInitial("L")` replaces
`name`, it does not mutate it.

**Heuristic for spotting hidden Entities:** if you find yourself
wanting an "in-place mutator" on a Value, either redesign as
replacement, or accept that the concept is actually an Entity.

### 5. Value Equality

Two Value instances are equal when they have the same type and the
same attribute values. Identity is irrelevant; many distinct
instances may be equal at once. Equality and hashing are defined
across all Value attributes -- never on an internal id, never on
object identity.

This is the inverse of Entity equality (see `entities.md`
Principle 3): Entities are equal iff identity matches; Values are
equal iff all attributes match. The two equality rules must not
mix in one type.

## Principles

### 1. Default to Value; justify every Entity

When introducing a new domain concept, the first design question is
"can this be a Value?" Reach for Entity only when individuality plus
mutable life cycle are both required, and name the reason in the
spec. Modeling drift toward Entities ("everything has an id, so
everything is an Entity") is the most common DDD modeling error.

**Apply when:** introducing a noun in a spec, schema, or code. If
the concept measures, quantifies, or describes -- and the business
does not need to track *which* instance over time -- model it as a
Value.

### 2. Make Values immutable in the type itself

Immutability is a property of the type, not a convention readers
must remember. Use the language's native means: final/readonly
fields, frozen objects, immutable dataclasses, sealed structs.
Constructors validate every attribute; no setter is reachable from
outside construction; no method returns a reference through which
internal state could be mutated.

**Apply when:** writing the Value's type. Reject any "I'll just
add a setter for this one case" -- that one case is the seam that
will rot.

### 3. Compose attributes into Whole Values, not loose fields

When two or more attributes always travel together and are
meaningful only in combination, lift them into a named Value type
rather than carrying them as siblings on a parent. The Value's name
is part of the Ubiquitous Language; the field-bag alternative is
not.

**Apply when:** a parent type accumulates a third or fourth field
that is semantically tied to the second (`name1`/`name2`,
`min`/`max`, `street`/`city`/`postal`). Stop and name the cluster.

### 4. Behavior on Values is side-effect-free

Methods on a Value Object are pure functions over its attributes.
A method either returns a derived value, returns a new replacement
Value, or both. It never mutates `this` and never has observable
side effects on anything else.

This is the **Side-Effect-Free Function** characteristic alongside
CQS (Command-Query Separation): a query method must not change the
answer to itself. The benefit is not aesthetic
-- it makes Values composable, cacheable, and trivially safe to
share across threads, requests, or contexts.

**Apply when:** adding a method to a Value. The method is either a
query (no `self` mutation, returns a derived value) or a
transformer (no `self` mutation, returns a new Value of the same or
related type). If you cannot fit it into one of those two shapes,
the behavior probably belongs on an Entity, an Aggregate, or a
Domain Service.

### 5. Use Values for Aggregate identity

An Entity's unique identifier is itself a Value: it has the
conceptual-whole shape (the identifier as a unit), needs Value
equality (lookup by id), needs immutability (an identity that
silently changes is a bug factory), and benefits from
side-effect-free behavior (formatting, parsing, validation
centralized on the type).

A typed identifier (`UserId`, `OrderId`) catches "wrong-id-passed"
errors at the type system; a raw `string`/`uuid`/`int` does not.
Even when the Entity itself is mutable, its identifier should be a
Value.

**Apply when:** introducing a new Entity. Define the identifier
type before you define any field; pass that type, not the raw
primitive, across module and context boundaries.

### 6. Standard Types belong in the local model as Values

A "Standard Type" -- a closed, descriptive enumeration like
`PhoneKind` (Home / Mobile / Work / Other), `Currency` (USD / EUR /
JPY...), `MedicationRoute` (IV / Oral / Topical) -- describes the
*kind of* something rather than being a thing in its own right.
Model it as a Value in the consuming context, even when the
authoritative source treats it as an Entity in its own bounded
context.

The translation from "remote Entity" to "local Value" is part of
the Anticorruption Layer (see `context-maps.md` Principle 3): the
Standard Type's foreign identity, lifecycle, and metadata stop at
the boundary; only the descriptive type travels inward.

**Apply when:** a closed set of descriptive labels enters the
model. Use a typed enum / sealed type / sum type, not a free
string. Reject "open" string fields whose contents the system
silently depends on being one of N values.

**Anti-pattern:** a column called `status` typed as
`varchar`/`string`, with the valid set documented only in a comment
or inferred from grep. Misspellings (`"doolars"`) become
permanently-broken rows.

### 7. Reject data-model leakage; the domain model leads

When persistence (an ORM, a relational schema, a key-value store)
forces accommodations -- a Value is stored in its own table with a
synthetic primary key, attributes are denormalized across multiple
columns, a collection-of-Values needs a join table -- those are
*persistence-side* compromises. They must not flow upstream into
the domain. The domain still treats the concept as a Value, with
all five Value characteristics, regardless of how the bytes happen
to be laid out on disk.

Four diagnostic questions when persistence tempts you to "promote"
a Value to an Entity:

1. Does this concept describe / measure / quantify a thing in the
   domain, or is it itself a thing?
2. If correctly modeled as descriptive, does it possess all five
   Value characteristics?
3. Am I considering an Entity *only* because the data store has to
   represent it as one?
4. Do I genuinely need unique identity and a managed life cycle, or
   am I confusing those with "has a row"?

If the answers are "describes, yes, yes, no," it is a Value. The
data model bends, not the domain.

**Apply when:** an ORM, a migration plan, or a query optimizer is
about to dictate the shape of a domain type. Push back: design the
data model for the domain model, not the other way around.

### 8. Test Values from the client's perspective

Tests of a Value Object double as the canonical usage manual: how
clients construct it, what equality looks like, what
side-effect-free transformations are available. Build the test
first, against the language the client will use; let that drive the
constructor surface and the method names. A common Value-test
shape:

- Construct an instance.
- Construct a separate-but-equal copy via the equality-bearing
  path (copy constructor or equivalent).
- Assert equality between the two.
- Run a transformation method.
- Re-assert equality with the unchanged copy, proving the
  transformation was side-effect-free.

This pattern is cheap to write and pins down all five
characteristics in a few lines.

## What this shard does **not** govern

- Aggregate boundaries and Aggregate Roots -- that is `aggregates.md`.
  (A Value lives inside an Aggregate; the Aggregate's transactional
  boundary is a separate concern.)
- Repository design and how Aggregates round-trip to storage --
  that is `repositories.md`. The persistence *guidance* here is
  "do not let the data model corrupt the domain model"; the
  *mechanics* of mapping live elsewhere.
- The exact immutability idiom in any one language (frozen
  dataclasses, readonly records, sealed case classes,
  TypeScript `readonly` + `as const`) -- this shard governs the
  *shape*; service-specific conventions handle the syntax.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards, anemic-model
  warning, DDD-Lite trap.
- `entities.md` -- the identity-bearing counterpart. Most fields
  on an Entity should be Values; the Entity's own identity should
  itself be a Value.
- `bounded-contexts.md` -- a Value's name is part of one bounded
  context's Ubiquitous Language. Same English term, different
  Value type, in two contexts is fine and expected (see
  `bounded-contexts.md` Principle 5).
- `context-maps.md` -- Standard Types coming from another context
  enter through an ACL; the foreign Entity becomes a local Value.
- `architecture.md` -- Values live in the domain layer; their
  immutability and side-effect-free behavior are what make
  hexagonal adapters cheap (a Value crossing the boundary needs
  no defensive copy).
- `../contracts.md` -- a wire schema is its own type; Values may
  be serialized into the wire shape, but the wire type is not
  the Value type.
- `../refactoring.md` -- changing a Value's attribute set, its
  equality semantics, or its constructor signature is a
  public-contract change in the Ubiquitous-Language sense; update
  all callers and the glossary in the same change.
