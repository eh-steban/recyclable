---
paths:
  - "private/specs/**"
---

# DDD foundations (Ch. 1)

Foundational context for reasoning about Domain-Driven Design. Load when
introducing DDD concepts, evaluating whether a domain model is anemic, or
when a spec is about to introduce a new noun.

## The two pillars

DDD rests on two patterns that are useless apart:

- **Ubiquitous Language** -- one shared vocabulary, used by
  domain experts, developers, code, tests, prompts, docs, and
  conversation, *inside one bounded context*. Not industry
  jargon, not enterprise-wide standards -- a language the team
  agrees on, evolves, and speaks literally. The model in the
  code is the lasting expression of it.
- **Bounded Context** -- the explicit boundary inside which one
  Ubiquitous Language and one model are consistent. A term
  outside the boundary may mean something different, and that
  is fine if the translation is explicit. There is **one
  Ubiquitous Language per bounded context**, and bounded
  contexts are usually *smaller* than first imagined.

For the model to be useful, **the design is the code**.
Whiteboards and diagrams are discussion aids, not design
artifacts; the code is the truth.

## Useful, not realistic

DDD models what is *useful to the business*, not the "real
world." When usefulness and realism diverge, choose useful. The
model is whatever lets the business answer its questions
correctly -- not a faithful replica of reality.

## The anemic-model warning

A "domain model" that is just data holders with getters/setters,
driven by transaction-script services that mutate fields, is
**anemic**: you pay the cost of a domain model and get none of
the benefit. Symptoms:

- A service method like `saveCustomer(...12 args...)` whose
  behavior depends on which args are null.
- A domain class whose only methods are `getX` / `setX`.
- Business rules living inside service-layer if/else trees,
  not on the entity that owns the invariant.

Cure: put behavior on the type that owns the invariant.
`backlogItem.commitTo(sprint)` enforces "must be scheduled for
release" and "uncommit from prior sprint first" *inside the
aggregate*, and emits the Domain Event as a final step. The
caller cannot get it half-right.

**Apply when:** invariant-bearing logic is about to land in an
API handler, an application service, or framework glue. Push it
onto the domain type that owns the invariant.

## The DDD-Lite trap

Cherry-picking tactical patterns (Aggregates, Repositories,
Value Objects) **without** Ubiquitous Language or explicit
bounded contexts is "DDD-Lite." It captures little of the
benefit and produces a brittle technical scaffold. Strategic
design is what pays; tactical patterns are tools applied
*inside* a strategically named context.

Partial adoption is not DDD-Lite as long as the strategic step
(naming bounded contexts and their language) is not skipped.

## Three recurring challenges

The list of what makes DDD hard:

- **Time to grow the language.** Naming things in domain terms
  takes deliberate work and re-work. Resist the urge to ship
  with placeholder names that calcify.
- **Sustained domain-expert involvement.** Domain experts must
  remain involved continuously, not once at spec time. Specs
  should name who plays this role for the work in question.
- **Changing how developers think.** Behavior on the type that
  owns the invariant is unfamiliar to a service-script habit.
  When in doubt, ask "what business behavior does this type
  *do*?" before adding another field accessor.

## When this matters in practice

Cite this section when a spec, plan, or review is about to:

- Introduce a new noun in code, schema, or prompt -- check the
  Ubiquitous Language first; do not invent a synonym.
- Add a service method that mutates several fields on a domain
  object -- check whether the behavior belongs on the object.
- Reach for a tactical pattern -- name the bounded context the
  pattern lives in first.
- Skip strategic naming because "we already know what we mean"
  -- that is exactly when the language drifts.
