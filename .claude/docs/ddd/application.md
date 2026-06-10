# DDD shard -- application

How the components that surround a domain model -- user interface,
Application Services, infrastructure -- are assembled into a working
application without leaking domain logic outward or technical detail
inward. Distilled from *Implementing Domain-Driven Design*,
Chapter 14 ("Application").

This shard covers **what lives outside the domain model and how it
talks to the model**. For Domain vs Application Service distinction at
the model boundary, see `services.md`. For Repository wiring, see
`repositories.md`. For composition across contexts at runtime, see
`integrating-bounded-contexts.md`. For the architectural styles in
which all of this sits, see `architecture.md`. For the index of
shards, see `principles-hub.md`.

## What an application is, here

> "I am using the term *application* to mean the finest set of
> components that are assembled to interact with and support a Core
> Domain model. This generally means the domain model itself, a user
> interface, internally used Application Services, and infrastructural
> components." -- Ch. 14

Four compartments, one assembly:

- **Domain model** -- Aggregates, Value Objects, Domain Services. The
  source of business behavior and invariants. (`aggregates.md`,
  `value-objects.md`, `services.md`.)
- **Application Services** -- thin task coordinators, one method per
  use case flow. They open transactions, enforce authorization,
  delegate into the model, and return (or write) the result.
- **User interface** -- whatever surface the user touches: HTTP-served
  HTML, an SPA, a thick client, a REST API consumed programmatically,
  a CLI. Translates user gestures into Application Service calls and
  domain data into rendered output.
- **Infrastructure** -- the implementations of every technical
  capability the other three depend on: persistence, messaging,
  email, file IO, encryption, charts. *Implementations* live here; the
  *interfaces* live in the layer that needs them (Dependency Inversion
  Principle).

The line between these is not architectural ceremony; it is what makes
the domain model independently testable and the technical layer
independently swappable.

## Principles

### 1. Keep Application Services thin -- one method per use case flow

An Application Service method does four things and stops:

- Open a transaction (or read-only transaction for queries).
- Enforce authorization for this use case.
- Delegate into the domain model -- usually one Aggregate command,
  sometimes a Domain Service when the work spans Aggregates.
- Return the result (or write it to a Port -- see Principle 7).

It does **not** carry business logic. The contrast between an
Application Service and a Domain Service should be "stark": if reading
the Application Service tells the reader *how* a use case decides
something, the logic has leaked out of the model. Push it back. The
canonical sign of leakage is an Application Service method that does
two domain steps in sequence and emits two events; that work belongs
in a Domain Service.

> "We should strive to push all business domain logic into the domain
> model, whether that be in Aggregates, Value Objects, or Domain
> Services. Keep Application Services thin, using them only to
> coordinate tasks on the model." -- Ch. 14

**Apply when:** writing or reviewing an Application Service. If the
method has more than transaction-open + authorization + one domain
delegation + return, ask whether the body belongs in a Domain Service
or on the Aggregate.

### 2. Pass arguments as Commands when the parameter list grows

A use case that needs nine arguments produces a nine-parameter
Application Service method that is unreadable, untestable, and a
guaranteed source of "which argument was the third boolean?" bugs.
Replace it with a **Command object**:

- Named after the operation: `ProvisionTenantCommand`,
  `EnableProductOwnerCommand`, `ChangeSummaryWithTypeCommand`.
- Carries primitive / Value-Object fields plus simple constructors.
- The Application Service method takes the Command as its single
  argument and reads off it.

Two side benefits beyond the parameter-list cleanup:

- The Command can be **serialized** for an inbound HTTP / message
  payload (UI form-mapping, message-broker delivery).
- The Command can be **dispatched asynchronously** to a queue and a
  Command Handler that is "semantically equivalent to an Application
  Service method, but temporally decoupled." This unlocks throughput
  and scalability when the synchronous path is the bottleneck.

The Command is *not* a DTO. A DTO is a presentation-shaped data
holder; the Command is named for and bound to a specific use case.

**Apply when:** an Application Service method's parameter list passes
roughly four arguments, or any time the work is a candidate for async
dispatch / replay. Build the Command type even if the synchronous path
is all you ship today.

### 3. Render the UI from a view shaped to the use case, not from Aggregate shape

The most common rendering mistake is to dump Aggregate state straight
to the view -- as a JSON tree of the domain model, as a DTO that
mirrors Aggregate fields one-for-one, or as a REST resource that
mirrors the Aggregate hierarchy. Three failure modes follow:

- The UI now has to understand the domain model. Subtle state
  transitions, invariants, and lazy-loaded edges leak through.
- Every Aggregate change ripples into every consumer that expected the
  old shape. The Aggregate can no longer evolve safely.
- The "view model" grows incidental complexity until it is its own
  domain model, just badly named.

The rule: the shape of what reaches the view is dictated by *what
the user is trying to do*, not by how the Aggregate is stored.
This is a **View Model** or **Presentation Model**; RESTful state
representations work the same way -- a separate model from the
domain.

**Apply when:** designing a view, a DTO, a REST representation, or any
artefact the UI consumes. Name the use case, then design the shape
backwards from it. If the shape mirrors the Aggregate, it is wrong.

### 4. Choose the rendering technique by capability, not by fashion

Five recurring techniques. Each fits a different combination of
"how far is the presentation from the domain?" and "how strict is
the encapsulation?":

- **DTO + DTO Assembler.** The Application Service uses Repositories
  to load Aggregates, an Assembler reads off them, the DTO travels to
  the view. Designed for *remote* presentation tiers; in a single-VM
  app it is often accidental complexity (YAGNI). Lazy-load resolution
  is implicit because the Assembler walks the Aggregate inside the
  transaction.
- **Domain Payload Object (DPO).** Holds references to whole Aggregate
  instances, not flattened attributes. Cheaper than DTO when
  presentation is in the same VM. Risk: lazy-loaded edges may not be
  resolved by the time the transaction commits, so use a Domain
  Dependency Resolver (or eager fetch) to force the necessary loads
  before the Application Service returns.
- **Mediator / Double-Dispatch / Callback.** The Aggregate exposes
  state through a `provide*Interest(interest)` API. Clients implement
  the interest interface. The Aggregate decides what to publish; the
  client never reaches into Aggregate internals. Highest
  encapsulation; some teams find it ceremonious.
- **Use-case-optimal Repository query.** A Repository finder method
  that composes a custom Value Object across one or more Aggregates,
  shaped to a single use case. Lives one short step away from CQRS
  -- once you have several of these, choose CQRS deliberately
  (`repositories.md` Principle 8).
- **REST state representation.** A view model published over HTTP. Use
  case-shaped (Principle 3); never an Aggregate dump.

The choice is driven by:

- Where the presentation runs (in-process, separate VM, browser,
  thick client).
- Whether the persistence layer supports lazy loading or not.
- How tightly clients should be coupled to Aggregate internals.
- Whether the system already has CQRS read models for similar
  questions.

**Apply when:** deciding how the model's state reaches the view. Name
the technique, name the reason. "We've always used DTOs" is not a
reason; "the presentation runs in a separate process" is.

### 5. Don't let the rendering surface couple the UI to Aggregate internals

Whichever rendering technique wins (Principle 4), the Aggregate's
encapsulation must survive. The Aggregate decides *what state to
expose*; the client decides *how to display it*. Two patterns help:

- **Mediator / Double-Dispatch interface** -- the Aggregate publishes
  state through a `provide*Interest(interest)` callback. The client
  implements the interface. The Aggregate's internal shape -- which
  fields exist, which are nullable, how Value Objects compose -- never
  leaks.
- **Use-case-optimal query result** -- a Value Object whose fields are
  named for the *use case*, materialized by the Repository. The UI
  binds to the result type, not to the Aggregate.

DTO Assemblers and DPOs *can* maintain encapsulation, but only if they
go through one of the above interfaces. An Assembler that calls
`aggregate.getInternalCollection().get(0).getSubField()` is *the*
coupling problem the rendering surface was supposed to prevent.

**Apply when:** writing a DTO Assembler, a DPO consumer, or a state-
representation builder. The Aggregate's public surface should reveal
only what *some* use case needs; chase any "for completeness" getter
back out of the Aggregate.

### 6. Decouple Application Services from disparate client types

A single Application Service sometimes serves a REST endpoint, an SPA,
a thick client, a message handler, and tests. Three ways to keep the
Service from sprouting per-client variants:

- **Data Transformer parameter.** Each client passes a Transformer
  implementation when it calls the Service. The Service builds the
  domain result, hands it to `transformer.transform(result)`, and
  returns whatever the Transformer produced (XML, JSON, CSV, DTO, DPO,
  text). One Service method, many output shapes.
- **Hexagonal output Port.** The Application Service is declared
  `void`. Instead of returning, it writes the result to a named
  output Port. Adapters (one per client type) register as readers of
  that Port and transform the bytes for their client. This is the
  same shape as Aggregate → Domain Event Publisher (the publisher is
  a Port; subscribers are adapters).
- **Both.** A void Application Service that writes to a Port whose
  adapters internally use Data Transformers.

Trade-off: the Port pattern complicates query-shaped methods (`tenant`
no longer "returns" a `Tenant`; rename to `findTenant` and document
the Port contract). The Transformer pattern keeps the synchronous
return shape but adds a parameter to every signature.

**Apply when:** the same use case is consumed by more than one client
type. Pick one decoupling shape; do not write per-client Application
Service methods (`provisionTenantForRest`, `provisionTenantForSpa`).

### 7. Apply transactions and authorization at the Application Service, not deeper

The Application Service is the right place for cross-cutting concerns
that *every* use case needs:

- **Transactions.** Open a transaction at method entry, commit on
  normal return, roll back on exception. Read-only transactions for
  queries. The domain model never opens a transaction; the Repository
  never opens a transaction; only the Application Service does.
  (`repositories.md` Principle 9 covers the Repository side.)
- **Authorization.** Declarative method-level checks
  (`@PreAuthorize("hasRole('SubscriberRepresentative')")` in Spring,
  `@requires(role)` in your framework of choice) are correct here.
  The UI hides the navigation; the Application Service enforces it
  against malicious callers who bypass the UI.

Two reasons not to push these into the domain model: it would make the
domain layer depend on a security or transaction framework
(Hexagonal violation), and it would mean every code path that reaches
the model has to remember to enforce them. Catching them at the
Application Service is the single defensible boundary.

The exception: transactions are *one per Aggregate per request*
(`aggregates.md`, one-Aggregate-per-transaction rule). The Application
Service opens *one* transaction; the rule constrains what can happen
inside it.

**Apply when:** wiring a new Application Service method. Add
`@Transactional` and the authorization annotation before writing the
body; if the framework doesn't support declarative annotations, the
first three lines of the method are the equivalent imperative checks.

### 8. Use the Presentation Model as an Adapter, not a Facade

In a rich UI, between the view and the Application Service sits a
**Presentation Model** -- one object per view that:

- **Adapts the model's idioms to the UI framework's idioms.** The
  domain favors `summary()` and `story()`; the UI framework wants
  `getSummary()` and `getStory()`. The Presentation Model exposes
  getters that delegate; the Aggregate stays clean.
- **Tracks edits in flight.** During a session the user modifies
  fields; the Presentation Model holds an `EditTracker` that
  accumulates changes. On submit, the tracker becomes the input to a
  single Application Service call.
- **Exposes view-derived properties.** "Is this button enabled?" is a
  function of model state but not a model concept; the Presentation
  Model derives it.

What the Presentation Model is **not**:

- Not a Facade around Application Services. It does not orchestrate
  multiple service calls or compose results from several Aggregates;
  that work belongs in the Application Service (or in a dedicated
  composing layer -- Principle 9).
- Not a place for business logic. The "is this allowed?" decision
  belongs to the Aggregate; the Presentation Model only asks.
- Not a substitute for DTOs / DPOs. It *consumes* whichever rendering
  technique you chose (Principle 4); it does not replace the choice.

**Apply when:** building a view in a rich-UI framework. One
Presentation Model per view. The submit handler is a single delegating
call into an Application Service; if it is more, the work belongs
elsewhere.

### 9. Compose multiple contexts in one composing Application Layer

A view that needs `Product` (one context), `Discussion` (another), and
`Review` (a third) presents a structural choice:

- **Multiple Application Layers in parallel** -- portal/portlet style,
  one Application Service per context, the UI orchestrates them.
  Pitfall: the use-case-flow logic ends up in the UI, where it
  fragments and is hard to test.
- **Single composing Application Layer** -- one Application Service
  pulls from each context's domain layer (or each context's
  Application Service) and assembles a unified result. The
  preferred default for a single-page composition.

The composing layer has a tendency to grow until it has its own use
cases, its own invariants, and its own vocabulary. At that point it
is a **new Bounded Context with an Anticorruption Layer** -- it just
has not been named yet. Two responses are valid:

- Stay thin. The composing layer translates and aggregates; it does
  not decide. Acceptable when the unification is genuinely
  presentation-only.
- Split it out. Name the new context, give it its own Ubiquitous
  Language, host it in its own module
  (`com.foo.productreviews.domain.model.product` etc.), and treat
  composition as the new context's domain.

The choice is governed by `bounded-contexts.md` (when does a context
deserve a name?) and `context-maps.md` (which relationship pattern is
this composition implementing?).

**Apply when:** a single view consumes more than one context. Default
to a single composing Application Layer. Watch for it growing logic
beyond translation; when it does, propose a new Bounded Context
explicitly.

### 10. Infrastructure implements; interfaces live with their consumer

Dependency Inversion Principle, applied at the application boundary:

- **Interface lives with the consumer.** A Repository interface lives
  in the domain Module that owns its Aggregate. An email-sender
  interface used by an Application Service lives in the application
  layer. A chart-renderer interface used by the UI lives in the UI
  layer.
- **Implementation lives in `infrastructure`.** The Hibernate /
  SQLAlchemy / SES / Chart.js implementation depends on the interface
  but the interface does not depend on the implementation.
- **Wiring is the container's job.** Spring beans, FastAPI
  dependencies, hand-written constructor injection -- the wiring
  layer maps interface to implementation at startup.

Three access patterns to reach an implementation, all valid:

- **Constructor injection.** The Application Service takes the
  interface as a constructor parameter; the wiring layer constructs it
  with the right implementation. Most testable.
- **Property / setter injection.** The container assigns the
  implementation after construction. Equivalent for testing; less
  obvious in code review which dependencies a class has.
- **Service Factory / Registry lookup.** A
  `DomainRegistry.repository()` / `ApplicationServiceRegistry.x()`
  returns the wired implementation. Useful where DI cannot reach
  (e.g., framework-internal callbacks); the registry itself must be
  initialised by the container.

Pick *one* convention per project and apply it across all layers; a
codebase that mixes all three drifts into "where do I find this?"
debt.

**Apply when:** introducing any infrastructure dependency. Define the
interface in the layer that needs it; place the implementation in
`infrastructure`; wire via the project's chosen DI mechanism.

## What this shard does **not** govern

- **The domain layer's internals.** Aggregates, Value Objects,
  Entities, Domain Services, Domain Events, Modules -- those have
  their own shards. This shard governs the *non-domain* compartments
  and how they talk to the domain.
- **Architectural style.** Layers vs Hexagonal vs CQRS vs EDA -- those
  are governed by `architecture.md`. This shard takes the chosen style
  as given and shows how the application compartments sit inside it.
- **Service vs Domain Service distinction at the model boundary.** The
  exhaustive treatment of "what is a Domain Service vs an Application
  Service" lives in `services.md`; Principle 1 here only restates it.
- **Cross-context integration mechanism.** REST / messaging / RPC at
  the boundary between Bounded Contexts is governed by
  `integrating-bounded-contexts.md`. This shard's "user interface" is
  the *human* surface; the API surface used by *other contexts* is the
  Open Host Service in that shard.
- **Specific UI frameworks.** React / Next.js / Spring MVC / Rails
  view layer -- all are valid implementations of the Presentation
  Model and rendering principles here. The shard is framework-
  agnostic; framework conventions live in the relevant `frontend/` or
  `backend/` rule files.
- **Container choice.** Spring vs FastAPI dependency injection vs
  hand-rolled constructor wiring -- the choice is operational; the
  invariants this shard names (interface placement, single
  convention per project) hold for all of them.
- **Event Sourcing as a persistence strategy.** A+ES (see
  `event-sourcing.md`) treats Aggregate state as an event stream
  rather than a row. That decision changes how Repositories,
  Application Services, and Aggregates interact; if and when the
  project adopts A+ES, the relevant changes are described there.
  This shard assumes the conventional Aggregate-state-in-rows /
  documents shape.

## Cross-references

- `principles-hub.md` -- DDD hub: index of shards.
- `services.md` -- Domain vs Application Service distinction
  (Principle 1 restates `services.md` Principles 2 and 4); the
  Service-Factory access pattern (Principle 10 here, `services.md`
  Principle 6).
- `aggregates.md` -- one-Aggregate-per-transaction rule constrains
  what an Application Service does inside its transaction
  (Principle 7 here, `aggregates.md` Principle 1); Mediator /
  Double-Dispatch as Aggregate-encapsulation tool (Principle 5
  here, `aggregates.md` Principle 7).
- `repositories.md` -- Repositories are the persistence side of the
  rendering techniques (Principle 4 here); transactions in the
  Application Service (Principle 7 here, `repositories.md`
  Principle 9); use-case-optimal queries as a CQRS smell
  (Principle 4 here, `repositories.md` Principle 8).
- `value-objects.md` -- Commands (Principle 2) are Value-Object-
  shaped: immutable, named, equal by content; use-case-optimal query
  results (Principle 4) are Value Objects.
- `domain-events.md` -- the Hexagonal Output Port (Principle 6) is
  the same pattern as the Domain Event Publisher; events flowing out
  of an Application Service are governed there.
- `bounded-contexts.md`, `context-maps.md` -- when a composing
  Application Layer (Principle 9) deserves promotion to a real
  Bounded Context, those shards govern the decision.
- `integrating-bounded-contexts.md` -- the API-as-user-interface
  case (REST consumed by other contexts) lives there; the
  Anticorruption Layer that the composing Application Layer
  resembles (Principle 9) is operationalised there.
- `factories.md` -- the Application Service typically calls a Factory
  to construct an Aggregate, then `repository.add(...)`
  (`factories.md` Principle 6).
- `architecture.md` -- Layers, Hexagonal, REST, CQRS, EDA, A+ES are
  all valid hosts for the application compartments named here;
  Hexagonal makes Principle 6 (output Ports) a first-class
  architectural concept.
- `modules.md` -- Application Services and Presentation Models live
  in their own Modules (`application`, `presentation`,
  `infrastructure`), named after the language of the application
  (`modules.md` Principle 1).
- `../../rules/contracts.md` -- the Application Service signature is a contract
  to its UI clients; renaming a Command, changing the output Port
  shape, or rewording an authorization role is a contract change.
- `../refactoring.md` -- swapping a UI framework, container, or
  Repository implementation is the kind of change DIP exists to make
  safe (Principle 10 here); changing an Application Service's public
  signature is *not* a refactor.
