---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- modules

Strategic-design principles for **how to organize a bounded context's
code into Modules** (packages, namespaces, directories) so that the
structure tells the domain's story instead of fighting it. Distilled
from Vaughn Vernon, *Implementing Domain-Driven Design*, Chapter 9
("Modules").

This shard covers **how to draw, name, and refactor Modules inside a
bounded context**. For the boundary that contains all of these
Modules, see `bounded-contexts.md`. For the index of shards, see
`principles-hub.md`.

## What a Module is, here

A Module is the language's native packaging unit -- Java/Kotlin
packages, C# namespaces, Python packages, Go packages, Rust modules,
TypeScript directories. The DDD pattern overlays domain meaning on
top of the mechanical construct: a Module's name and contents are
themselves part of the Ubiquitous Language.

> "Choose Modules that tell the story of the system and contain a
> cohesive set of concepts. ... Give Modules names that become part
> of the Ubiquitous Language." -- Evans, quoted in Vernon Ch. 9

A Module is a **first-class modeling element**, not bland storage.
The criteria for designing one are the same as the criteria for
designing an Entity or Value: cohesion, naming care, willingness to
refactor when insight changes.

## Principles

### 1. Modules carry domain meaning; their names are Ubiquitous Language

A Module's name is read aloud, written into specs, and seen by every
developer who reads an import. Pick the name with the same care you
pick an Entity name. Avoid generic names that hold no domain meaning
(`core`, `shared`, `common`, `utils`, `misc`, `helpers`) inside the
domain layer -- a Module called `utils` is a placeholder, not a
Module.

The name should be the **shortest noun phrase a domain expert would
recognize**: `product`, `team`, `tenant`, `backlogitem`. Drop filler
words (`identityandaccess` -> `identityaccess`). Resist using brand
or product names (`idovation`, `collabovation`) -- brands change for
trademark or marketing reasons; bounded-context names do not.

**Apply when:** creating a new directory or package inside the
domain layer, or noticing an existing one whose name does not match
how the team talks about its contents.

### 2. Group by cohesive concept, not by mechanical attribute

A Module collects classes that **mean something together** in the
language. Vernon's kitchen analogy: place settings (forks, spoons,
knives, serviettes) belong in one drawer because they participate in
one activity. They do **not** belong sorted by material (metal vs
porcelain), shape (pronged vs scooping vs blunt), or fragility
(sturdy vs delicate). Mechanical groupings stifle the model because
they hide the concept behind an irrelevant property.

In code, the equivalent anti-patterns:

- Folders named after technical layers *inside the domain layer*:
  `entities/`, `valueobjects/`, `services/`, `events/`. The
  Aggregate is the unit of cohesion, not the tactical pattern type.
- Folders named after data-store technicalities: `tables/`,
  `columns/`, `rowmappers/`. Persistence concerns belong outside
  the domain layer; see `architecture.md`.
- Folders named for a transient project phase: `mvp/`, `legacy/`,
  `v2/`. These calcify and turn into permanent dead weight.

**Apply when:** filing a new Entity / Value / Service / Event. The
question is "what cohesive domain concept does this participate in?"
not "what tactical pattern is this?"

### 3. Use a domain-driven Module hierarchy; avoid brand names

Vernon's recommended hierarchy, adapted to any language's package
syntax:

```text
{org}.{bounded-context}.{architectural-compartment}.{domain-module}
```

- **Org / top-level** -- prevents collision with third-party code.
- **Bounded context** -- the *context name*, not the product brand.
  When marketing renames the product, bounded-context-named modules
  survive; brand-named modules become misleading.
- **Architectural compartment** -- `domain.model` for the domain
  layer (the `model` segment is deliberate: we model a domain, we
  do not develop a domain). Peers like `application`,
  `infrastructure`, `interfaces` / `resources` follow the
  compartment used by `architecture.md`.
- **Domain module** -- the cohesive concept (`product`,
  `backlogitem`, `team`, `tenant`).

Keep the `domain.model` segment even when it feels redundant -- it
preserves room to add `domain.service` later without retrofitting
every import. Skipping it ("just put model classes directly under
`domain`") backs the team into a corner the first time a Domain
Service module is needed.

**Apply when:** standing up a new bounded context, or finding an
existing one whose top-level naming makes the bounded-context name
hard to find at a glance.

### 4. Refactor Modules as readily as you refactor classes

Modules are not architectural fixed points. When domain insight
sharpens -- a concept gets a better name, a cohesive cluster splits,
two adjacent clusters merge -- move the code. Renaming a Module is a
**normal operation**, not a high-ceremony event.

The implication for tooling: rely on the language's rename refactor,
the IDE's "move package," and the type system's import resolution.
A Module that cannot be renamed without manual fix-up across many
call sites is a sign the language or the build system is fighting
the team -- worth fixing in tooling, not by leaving the Module's
wrong name in place.

**Apply when:** the team finds itself saying "we've stopped calling
it that, but the package is still named the old way." That gap is
the bug; fix it the same week the language drifts.

### 5. Prefer acyclic Module dependencies; relax for parent/child cohesion

The default goal is **acyclic dependencies**: leaf Modules depend on
shared identity / Value Modules; shared Modules do not depend back.
Cycles between sibling Modules typically signal a missing concept --
two Modules that are constantly importing each other are usually one
Module pretending to be two.

The accepted exception is a **parent / child Module cluster** where
the parent is a Factory or aggregator for its children. Vernon's
example: `product` is parent to `product.backlogitem`,
`product.release`, `product.sprint`; `Product` constructs each, and
each carries a `ProductId`. Strict acyclicity would require either
collapsing all four into one Module (organisationally noisy) or
introducing artificial indirection. The trade-off favors organisation
over coupling purity *inside one cohesive parent/child cluster* and
nowhere else.

**Apply when:** an import-cycle warning fires. First ask "is this a
missing concept?" If yes, extract or rename. If the cycle is
strictly between a parent Aggregate and its child Aggregates that
the parent legitimately constructs, accept it -- and keep the
exception local.

### 6. Don't trade typed identity for loose coupling between Modules

A tempting "decoupling" move when two Modules cross-reference each
other's id types: replace each typed id (`ProductId`, `TeamId`,
`TenantId`) with a single generic `Identity` / `Id` / `Uuid` type so
neither Module imports the other's identity Value. **Do not do
this.** It buys an import-graph aesthetic at the cost of the type
system catching wrong-id-passed bugs at compile time, which the
typed identifier (a Value Object per `value-objects.md` Principle 5)
exists to prevent.

If the cross-Module identity import is genuinely awkward, the right
fix is one of:

- Move the identity types into a small shared Module that both
  consumers depend on (acyclic).
- Re-examine whether the two Modules really belong as separate
  Modules at all (Principle 5).

The fix is never "untype the identity."

**Apply when:** reviewing a refactor PR that swaps `FooId` for a
generic `Identity` to break a cycle. Push back; find one of the
above two routes instead.

### 7. Reach for a new Module before a new Bounded Context

When linguistics are *clear* -- the same English term means two
different things, or two cohesive areas have genuinely different
languages -- a new bounded context is the right answer (see
`bounded-contexts.md` Principles 4 and 5). When linguistics are
*fuzzy* -- the team isn't sure whether a sub-area deserves its own
context or just its own folder -- default to a new Module inside the
existing context.

A Module is a thinner boundary than a bounded context: same
language, same model, same Repository style, same persistence
ownership. Splitting wrongly into a Bounded Context drags along
duplicate Ubiquitous Language definitions, integration overhead,
and a context map entry; splitting wrongly into a Module is a
five-minute move.

Bounded Contexts are not a substitute for Modules. Modules are the
day-to-day organizing tool *inside* a context.

**Apply when:** a spec asks "should this be its own service /
context / module?" Default-answer Module unless the linguistic case
for a new bounded context is concrete.

### 8. Apply Module discipline outside the domain layer too

The same naming and cohesion rules apply to non-domain code:
`application` (use cases / Application Services), `interfaces` /
`resources` / `api` (HTTP routes, GUI, CLI), `infrastructure`
(adapters: persistence, messaging, third-party clients). Sub-divide
each compartment by domain concept (`application.team`,
`application.product`) only when the count justifies it -- a
half-dozen Application Services in one compartment is fine; thirty
isn't.

DDD Modules and **deployment modules** (Java JPMS / Jigsaw, OSGi
bundles, Python distribution packages, Rust crates, Node workspaces)
are different things that happily compose. Loosely-coupled DDD
Modules are what *make* deployment modularization possible later --
when teams want to extract a deployment unit, the seam is already
drawn at the DDD Module boundary. Do not conflate the two: deciding
"this is a separate crate / bundle / package" is a deployment-time
decision, while DDD Module design is a domain-design decision that
happens whether or not the code is ever split for deployment.

**Apply when:** organizing the non-domain code of a new context, or
deciding whether to extract a deployment unit. Let the DDD Module
seams decide where the deployment unit can cleanly cut.

## What this shard does **not** govern

- The architectural-compartment layout itself (Layers vs Hexagonal
  vs Clean) -- that lives in `architecture.md`. This shard governs
  *how Modules are named and grouped* inside whichever architectural
  shape the context uses.
- Boundaries between contexts and how they integrate -- that is
  `bounded-contexts.md` and `context-maps.md`. This shard governs
  the inside; those govern the outside.
- Deployment topology (which Modules ship in which artifact, which
  artifact runs where). DDD Module design is upstream of that
  decision and constrains it but does not make it.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `bounded-contexts.md` -- the boundary that contains all of one
  context's Modules; Module vs Bounded Context choice (Principle
  7 here, Principle 4 there).
- `entities.md`, `value-objects.md` -- typed identifiers (Principle
  6 here, `value-objects.md` Principle 5) are the Modules' shared
  vocabulary; do not strip them to "decouple."
- `services.md` -- Domain Services may live in `domain.model` next
  to the Aggregates they coordinate, or in a peer
  `domain.service` Module. Either is fine; mixing styles inside one
  context is not.
- `domain-events.md` -- the in-process publisher and the
  Event-Store / forwarding components have natural Module homes
  (`domain.model` for the publisher contract, `application` for the
  registration site, `infrastructure` for the messaging adapter).
- `architecture.md` -- the architectural compartments
  (`domain.model`, `application`, `infrastructure`,
  `interfaces` / `resources`) are this shard's hierarchy backbone.
- `../contracts.md` -- public Module surfaces (exported types,
  resource URIs, Event names) are wire-level contracts in their own
  right; renaming an exported Module surface is a contract change,
  not a free internal refactor.
- `../refactoring.md` -- Module renames and moves are exactly the
  kind of behavior-preserving change refactoring exists for; do
  them assertively, but in a single change set with all the
  imports updated, not as a slow drift.
