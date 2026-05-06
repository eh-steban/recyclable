---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD principles -- hub

How to apply Domain-Driven Design, distilled from Vaughn Vernon,
*Implementing Domain-Driven Design*.

This file is a **navigation hub**. The principles themselves live
in sibling topic-specific shards. The hub holds the
foundational context, the shard index, and the philosophy of
partial adoption. The project's own catalog of bounded contexts
and their classifications belongs in specs and design docs, not
here.

## Why partial adoption is fine

DDD is not all-or-nothing. Use only the parts that mitigate a
real risk:

- **Strategic design first.** Bounded contexts and a context map
  give a shared mental model for how systems interact. This is
  the highest-leverage DDD investment.
- **Tactical patterns à la carte.** Use Aggregates, Value
  Objects, Repositories, or Domain Events when the model
  genuinely calls for them. Do not introduce them as scaffolding.
- **Ubiquitous Language is non-negotiable.** Whatever is modeled,
  the names in code, schema, prompts, specs, and UI must match
  what the team calls the thing in conversation. This is the
  cheapest DDD habit with the largest long-term payoff.

If a principle in any shard would force ceremony without
clarity, skip it and note why in the relevant spec.

## Foundations (Vernon Ch. 1)

Distilled context an agent needs before reasoning about DDD.
Not exhaustive -- the shards carry the detail.

### The two pillars

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

### Useful, not realistic

DDD models what is *useful to the business*, not the "real
world." When usefulness and realism diverge, choose useful. The
model is whatever lets the business answer its questions
correctly -- not a faithful replica of reality.

### The anemic-model warning

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

### The DDD-Lite trap

Cherry-picking tactical patterns (Aggregates, Repositories,
Value Objects) **without** Ubiquitous Language or explicit
bounded contexts is "DDD-Lite." It captures little of the
benefit and produces a brittle technical scaffold. Strategic
design is what pays; tactical patterns are tools applied
*inside* a strategically named context.

Partial adoption is not DDD-Lite as long as the strategic step
(naming bounded contexts and their language) is not skipped.

### Three recurring challenges

Vernon's list of what makes DDD hard:

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

### When this matters in practice

Cite this section when a spec, plan, or review is about to:

- Introduce a new noun in code, schema, or prompt -- check the
  Ubiquitous Language first; do not invent a synonym.
- Add a service method that mutates several fields on a domain
  object -- check whether the behavior belongs on the object.
- Reach for a tactical pattern -- name the bounded context the
  pattern lives in first.
- Skip strategic naming because "we already know what we mean"
  -- that is exactly when the language drifts.

## Shards

Each shard distills one chapter (or one cohesive topic) of
Vernon's book into principles. Follow the link when working on
something the shard governs; otherwise the hub is enough.

- [`bounded-contexts.md`](bounded-contexts.md) -- Vernon Ch. 2.
  Defining a single bounded context: domains vs subdomains,
  Core/Supporting/Generic, naming, what lives inside the boundary,
  right-sizing, same-word-different-meaning.
- [`context-maps.md`](context-maps.md) -- Vernon Ch. 3.
  Relationships between contexts: integration patterns (Open Host
  Service, Published Language, ACL, Customer-Supplier, Separate
  Ways, Shared Kernel, Conformist, Big Ball of Mud),
  upstream/downstream direction, eventual consistency, translation
  maps, modeling unavailability.
- [`architecture.md`](architecture.md) -- Vernon Ch. 4.
  Architectural styles inside a context: risk-driven selection,
  Layers + DIP as default, Hexagonal (Ports and Adapters), REST as
  Open Host Service, Smart-UI rejection, eventual consistency
  between adapters, when (not) to adopt CQRS / EDA / Event Sourcing
  / Data Fabric.
- [`entities.md`](entities.md) -- Vernon Ch. 5. Entities: when to
  reach for one, unique-identity strategies, identity stability,
  surrogate identity, discovering Entities from the Ubiquitous
  Language, behavior on the type that owns the invariant, roles
  and object-schizophrenia, validation at three levels.
- [`value-objects.md`](value-objects.md) -- Vernon Ch. 6. Value
  Objects: the five characteristics (measures/quantifies/describes,
  immutable, conceptual whole, replaceability, value equality),
  side-effect-free behavior, default-to-Value bias, Values for
  Aggregate identity, Standard Types as local Values,
  rejecting data-model leakage, test-from-the-client style.
- [`services.md`](services.md) -- Vernon Ch. 7. Domain Services:
  when an operation does not fit on an Entity or Value, statelessness,
  distinguishing Domain / Application / SOA "service," naming in the
  Ubiquitous Language, pushing multi-step composition off the client,
  Repositories from Services not Aggregates, Separated Interface as
  opt-in, mini-layer drift toward Anemic Model, testing from the
  client and modeling normal failures as values not exceptions.
- [`domain-events.md`](domain-events.md) -- Vernon Ch. 8. Domain
  Events: discovering them in the language and naming them in the
  past tense, immutable Value shape and minimum payload, when an
  Event needs an identity, the one-Aggregate-per-transaction rule,
  in-process publisher with no middleware in the model, Application
  Services registering subscribers and owning transactions, durable
  Event-with-Aggregate persistence (Event Store), choosing REST
  notifications vs messaging, latency as a domain question,
  at-least-once delivery and de-duplication.
- [`modules.md`](modules.md) -- Vernon Ch. 9. Modules: names as
  Ubiquitous Language, group by cohesive concept (not by tactical
  pattern type or mechanical attribute), the
  org/context/compartment/concept hierarchy, refactor Modules as
  readily as classes, prefer acyclic dependencies (relax for
  parent/child cohesion), don't strip typed identity for "loose
  coupling," reach for a new Module before a new Bounded Context,
  apply the same discipline outside the domain layer.
- [`aggregates.md`](aggregates.md) -- Vernon Ch. 10. Aggregates:
  consistency-boundary as the unit of transactional change,
  one-Aggregate-per-transaction, modeling true invariants (not
  compositional convenience), small Aggregates of Root + Values,
  reference other Aggregates by identity, eventual consistency
  outside the boundary, the "whose job is it?" tie-breaker,
  Tell-Don't-Ask + Law of Demeter at the Root, Application
  Services (not Aggregates) own dependency lookup, optimistic
  concurrency placed where the invariant lives, named rule-breaks.
- [`factories.md`](factories.md) -- Vernon Ch. 11. Factories:
  placing Factory Methods on the parent Aggregate and naming them in
  the language, enforcing identity and tenancy correctness through
  the Factory, hiding the target Aggregate's constructor, guarding
  only state-of-parent invariants, publishing creation Events from
  the Factory Method, the create-vs-persist split, Domain Service
  as Factory when crossing Bounded Contexts, accounting for the
  parent-load cost.
- [`repositories.md`](repositories.md) -- Vernon Ch. 12.
  Repositories: one Repository per Aggregate Root, the Set-mimicking
  contract (no re-save), collection-vs-persistence styles chosen by
  the store's change-tracking, interface in the domain Module and
  implementation in `infrastructure`, `nextIdentity()` on the
  Repository, persistence-exception translation at the boundary, no
  bypassing the Aggregate boundary, use-case-optimal queries as a
  smell, transactions in the Application Service, real-store tests
  for the Repository and in-memory tests for its clients.
- [`integrating-bounded-contexts.md`](integrating-bounded-contexts.md)
  -- Vernon Ch. 13. Integrating bounded contexts: cross-context calls
  are distributed-systems calls (not in-process), choosing messaging
  vs REST vs RPC by the autonomy you need, crossing through a
  Published Language (not shared classes), Open Host Services that
  expose use cases (not Aggregates), Anticorruption Layers as
  Service + Adapter + Translator, mirror-vs-look-up trade-offs and
  the bias toward minimizing duplication, designing for out-of-order
  and at-least-once delivery (per-attribute change trackers,
  idempotent handlers, `occurredOn` on commands), Long-Running
  Processes with a tracker / retries / time-out, multi-gate Processes
  as state machines with `completenessVerified()`, planning for
  broker and consumer downtime.
- [`application.md`](application.md) -- Vernon Ch. 14. The
  application compartments around the domain model: thin Application
  Services as one-method-per-use-case task coordinators (not Domain
  Services), Commands replacing long parameter lists, view shapes
  driven by use case (not Aggregate shape), choosing among DTO / DPO
  / Mediator / use-case-optimal query / REST representation by
  capability not fashion, Mediator/Double-Dispatch to keep Aggregate
  encapsulation through the rendering surface, Data-Transformer
  parameters or Hexagonal output Ports for disparate clients,
  declarative transactions and authorization at the Application
  Service boundary, Presentation Model as Adapter (not Facade),
  composing-Application-Layer for multi-context UIs and when to
  promote it to a new Bounded Context, infrastructure implements
  interfaces declared with the consuming layer (DIP), one DI / Service
  Factory / constructor convention per project.
- [`event-sourcing.md`](event-sourcing.md) -- Vernon Appendix A
  (contributed by Rinat Abdullin). A+ES as Aggregate persistence:
  adopt when reconstruction and history are first-class business
  concerns (audit, replay, regulated industries) -- not by default,
  Aggregate state is the fold of its Event Stream, separating
  `Apply` (record + mutate) from `Mutate` / `When` (state update
  only), the load → execute → append Application Service shape with
  stream version as the optimistic-concurrency guard, retry-and-replay
  vs event-conflict-resolution by whether the behavior has external
  side effects, planning for replay cost via snapshots / caching /
  partitioning, layering a typed Event Store over an untyped append-
  only primitive, reads via disposable Projections of the Event
  Stream (CQRS becomes mandatory), Events serving both reconstitution
  and publication (enrich for the 80 % of subscribers), tag-based
  serialization + immutability + Value Object payloads + optional
  contract DSL, A+ES making Aggregates cheap so aim for Focused
  Aggregates, Given-past-Events / When-command / Then-new-Events
  testing.

Vernon Ch. 1 (introduction, why DDD, anemic-model warning,
DDD-Lite trap, three recurring challenges) is folded into the
"Foundations" section above rather than given its own shard --
the material is context for agentic reasoning, not a
principles list to apply per task.

## How this interacts with other rules

- **`../contracts.md`** governs the *shape* of HTTP-boundary
  contracts. The DDD shards govern *why* that boundary exists
  and what counts as crossing it.
- **`../refactoring.md`** forbids changing public contracts without
  authorization. An integration surface between bounded contexts
  is a public contract in this sense when other contexts depend
  on it -- even when both sides live in the same codebase. A
  refactor may not move or rename that surface without updating
  all dependents.
- **`private/invariants.md`** (repo root) -- if a DDD principle in any shard
  ever conflicts with a numbered invariant, the invariant wins;
  flag the conflict and escalate.

## When to revisit

Update the hub or a shard when:

- A shard's principles outgrow it and need to be split or
  renamed.
- A new shard is added for a chapter worked through.
- A principle proves harmful or vacuous in practice and needs
  revision or removal.

Update via the `spec-writer` agent or with explicit user
approval, per `.claude/rules/doc-ownership.md`.
