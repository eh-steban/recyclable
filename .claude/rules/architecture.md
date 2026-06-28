---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# Architecture

How the recyclable codebase is organized: bounded contexts, Modules,
layering, type categories, persistence boundaries, and the principles
that make those choices coherent. This file is the *what we have*; the
DDD shards under `ddd/` are the *why*. Those shards live in
`.claude/docs/ddd/` (open on demand via `principles-hub.md`), not in
the auto-loaded rules tree; `ddd/<shard>` citations below are shorthand
for that location.

When a question is "why is it organized this way?", the answer lives
in the relevant shard. When the question is "where does this code
go?", the answer lives here.

## Bounded contexts

Two contexts span the codebase.

- **Backend Context** -- the Python service in `backend/`. Contains
  all schema knowledge, all domain logic, and the Sonnet user path
  plus the Opus ingestion loop. Two application services share one
  domain layer:

    - **Retrieval** (user path, synchronous): location resolution,
      material normalization, rule retrieval, prompt composition,
      validator, response. Driven by the FastAPI HTTP API.
    - **Ingestion** (research path, asynchronous): source fetch,
      extraction, conflict detection, eval. Driven by the worker
      runner.

  Retrieval and Ingestion are *application services within one
  bounded context*, not separate bounded contexts. They share
  Ubiquitous Language (`Jurisdiction`, `Material`, `Rule`, `Source`
  mean the same thing in both), share `domain/`, and share
  `infra/db/`. The distinction between them is
  application-service-level, not context-level. See
  `ddd/bounded-contexts.md` "right-size by language" for why.

- **Presentation Context** -- the Next.js service in `frontend/`.
  Owns SEO-crawlable jurisdiction/material pages and the interactive
  `/ask` UI. Renders results from the Backend Context; holds no
  schema knowledge, makes no direct database connections, and never
  calls the LLM directly.

The HTTP API and the OpenAPI-generated TypeScript client are the
only boundary between the two contexts. Schema changes happen in
the Backend Context; the frontend re-runs codegen and the compiler
catches type drift.

**The OpenAPI specification is the Published Language** between
the two contexts (per `ddd/integrating-bounded-contexts.md`
Principle 3). Both producer and consumer target the spec; neither
imports the other's internal types. The backend's domain types are
not exported to the frontend even when names happen to match, and
the frontend's presentation-context types are not echoed back to
the backend. The spec is the contract; everything else translates
to or from it.

## Modules inside the Backend Context

Per `ddd/modules.md` Principle 2, the domain layer is organized by
**cohesive domain concept**, not by tactical pattern type. Four
Modules cover the Backend Context's domain:

- **`retrieval`** -- the Sonnet user path's domain logic: `Query`,
  `Citation`, `ItemVerdict` (and its variants `Accepted`, `Refused`,
  `NotCovered`, `Conflicted`), `EvaluatedAnswer`, `NoEvaluation`,
  the `RetrievalService` that owns the choreography, the
  `GroundingValidator` Specification, and the retrieval LLM port.
  Used by the Retrieval application service.

- **`knowledge_base`** -- persisted reference data:
  `Jurisdiction`, `Material`, `Rule`, `Source`, plus their
  repository ports. Read by Retrieval; written by Ingestion. The
  shared substrate of the two application services.

- **`ingestion`** -- the Opus research path's domain logic:
  `IngestionReport`, the `ConflictDetector` Domain Service, the
  ingestion LLM port. Used by the Ingestion application service.

- **`audit`** -- accountability records: `AnswerAuditRecord`, the
  `AnswerAuditRecordValidator` (which enforces INV-PROD-001 at
  construction), the answer-audit repository port. Written by the
  user path; read for feedback association, eval replay, and
  operational analytics. Future audit Entities for ingestion,
  feedback, or admin actions live alongside in this Module as
  separate Entities (each with its own invariants and validator),
  not as variants of one polymorphic record.

Each Module's name is part of the Ubiquitous Language. It appears
in code (folder names, type imports), in conversation, in prompts,
and in specs. Same word, same meaning, every place it shows up.

The same Module names appear in other compartments (`api/`,
`application/`, `infra/db/`) only when the file count in that
compartment justifies sub-division (per `ddd/modules.md`
Principle 8). At MVP scale, those compartments are flat; they
sub-divide as they grow.

### Shared kernel: `src/domain/shared/`

`src/domain/shared/` is an owner-approved **shared-kernel** location
for cross-cutting domain abstractions that belong to no single bounded
context. It is **not** a fifth Module in the Ubiquitous Language.
Currently it holds the generic `Repo[T, ID]` Protocol
(`domain/shared/repo.py`); all aggregate-repo ports extend it.
Per `ddd/modules.md` Principle 6, moving cross-Module identity or
abstraction types into a small shared package is the correct way to
keep Module dependencies acyclic without untyping them.

## Layers + DIP (inside the Backend Context)

The four DDD layers, with the Dependency Inversion Principle
applied. The domain owns the interfaces; infrastructure provides
implementations; the dependency arrow always points inward.

```text
backend/src/
├── api/                      # FastAPI driving adapter (HTTP)
│   ├── main.py
│   ├── deps.py
│   ├── schemas/              # Pydantic wire types (flat at MVP)
│   └── routes/               # Thin handlers; delegate to use cases
│
├── worker/                   # Worker driving adapter (async)
│   ├── runner.py
│   └── pipelines/            # ingestion pipelines
│
├── cli/                      # CLI driving adapter (operator)
│   └── ingest.py
│
├── application/              # Thin task coordinators (flat at MVP)
│   ├── answer_query.py       # user path use case
│   ├── ingest_source.py      # ingestion use case
│   ├── apply_report.py       # ingestion use case
│   ├── record_feedback.py    # audit use case
│   └── mappers/              # ORM <-> domain, domain <-> wire,
│                             #   wire-request <-> domain-input
│
├── domain/                   # Pure: no framework, no persistence,
│   │                         #   no transport. Module-organized.
│   ├── retrieval/
│   │   ├── query.py                  # Value
│   │   ├── citation.py               # Value
│   │   ├── item_verdict.py           # ItemVerdict sum + variants
│   │   ├── evaluated_answer.py       # Value
│   │   ├── no_evaluation.py          # Value
│   │   ├── retrieval_service.py      # Domain Service: choreography
│   │   ├── grounding_validator.py    # Specification (Level 2)
│   │   └── retrieval_llm.py          # port (LLM)
│   │
│   ├── knowledge_base/
│   │   ├── jurisdiction.py           # Entity
│   │   ├── material.py               # Entity
│   │   ├── rule.py                   # Entity
│   │   ├── source.py                 # Entity
│   │   ├── rule_repo.py              # port
│   │   ├── source_repo.py            # port
│   │   ├── jurisdiction_repo.py      # port
│   │   └── material_repo.py          # port
│   │
│   ├── ingestion/
│   │   ├── ingestion_report.py       # Entity (likely future Aggregate)
│   │   ├── conflict_detector.py      # Domain Service
│   │   ├── ingestion_report_repo.py  # port
│   │   └── ingestion_llm.py          # port (LLM)
│   │
│   └── audit/
│       ├── answer_audit_record.py            # Entity (Aggregate Root)
│       ├── answer_audit_record_validator.py  # Specification (Level 2)
│       └── answer_audit_record_repo.py       # port
│
└── infra/                    # Implementations of domain ports
    ├── db/
    │   ├── models/           # SQLAlchemy ORM rows (flat at MVP)
    │   └── repos/            # Implementations of repo ports
    └── external/
        ├── anthropic_client.py       # implements RetrievalLLM +
        │                             #   IngestionLLM
        └── source_fetcher.py         # implements SourceFetcher
```

**Dependency rules:**

- `domain/` imports nothing outside itself. No SQLAlchemy, no
  Pydantic, no FastAPI, no Anthropic SDK. If a domain file imports
  from `infra/` or `api/`, the design is inverted.
- `application/` depends on `domain/` only. Application services
  accept ports as parameters (FastAPI `Depends` injects
  implementations at request time); they never import `infra/`
  directly.
- `api/`, `worker/`, `cli/` depend on `application/` and on their
  own adapter concerns (Pydantic for `api/`, scheduling for
  `worker/`).
- `infra/` depends on `domain/` (to implement ports) and on its
  external libraries (SQLAlchemy, Anthropic SDK).

This is `ddd/architecture.md` Principle 2 applied. A refactor that
inverts a dependency direction is forbidden by `refactoring.md`
without explicit authorization.

### Application services are thin task coordinators

Per `ddd/services.md` Principle 4 and `ddd/application.md`
Principle 1, multi-step domain choreography that would mean the
same thing in any client (HTTP, CLI, worker, batch, test) is
*domain knowledge* and lives in a Domain Service inside `domain/`.
Application services in `application/` are thin coordinators: open
the transaction, enforce authorization, validate input, call one
Domain Service or one Aggregate command, return.

**Authorization on the user path is write-restriction.** The Sonnet
`/ask` surface is read-only against `rules`, `sources`, and
`traces`; its only sanctioned writes are the `AnswerAuditRecord` the
API service mints per query and feedback annotations on an existing
record (INV-AUTH-001). "Enforce authorization" here means a use case
on this surface must not reach a rule/source mutation -- not even
indirectly through a feedback endpoint that writes the same tables,
which is INV-AUTH-001's stated violation example. Rule and source
writes belong to the worker/CLI surface behind the review-and-apply
gate (INV-LLM-003).

Concretely for the user path:

```text
AnswerQuery (Application Service in application/answer_query.py)
  parse and validate wire input
  call RetrievalService.answer(query, jurisdiction_id)
  map domain result to wire response
  return

RetrievalService (Domain Service in domain/retrieval/)
  resolve location (LocationResolver)
  normalize material (MaterialNormalizer)
  retrieve rules (RuleRetriever, uses RuleRepo port)
  compose prompt (PromptComposer)
  call LLM (RetrievalLLM port)
  validate grounding (GroundingValidator Specification)
  return EvaluatedAnswer | NoEvaluation
```

**Trust boundary at prompt composition.** The `Query` reaching
`PromptComposer` is untrusted free text from the public `/ask`
surface. The composer delimits it from the system prompt and never
concatenates it as instructions; the system prompt is not
user-controllable (INV-LLM-004). `GroundingValidator` is an *output*
check and does not substitute for input containment -- prompt
injection that subverts grounding is the cheapest attack on the
product's core guarantee.

If an application service grows beyond "validate input -> call one
thing -> map and return," extract the choreography into a Domain
Service. Non-trivial logic in the application layer is the signal.

Per `ddd/application.md` Principle 2, when an application service
method's parameter list grows past roughly four arguments, replace
it with a **Command object** named after the operation
(`AnswerQueryCommand`, `IngestSourceCommand`). The Command is a
Value -- immutable, named, equal by content -- and unlocks future
asynchronous dispatch without rewriting the service signature.

### Tuple boundary-guard idiom on frozen domain dataclasses

Frozen domain dataclasses whose fields cross the LLM or ORM boundary
(e.g. `Accepted.conditions`, `AnswerAuditRecord.citations`) declare a
`tuple[...]` type but cannot trust it at runtime -- LLM and ORM adapters
may pass a list. The standing idiom is a `__post_init__` guard using
`isinstance(cast(object, self.field), tuple)`. The `cast(object, ...)`
deliberately defeats type-checker narrowing so the `isinstance` is not
flagged unreachable and remains a real runtime check. Policy is reject
(`TypeError`), never silently coerce. The `cast(object, ...)` is
load-bearing -- do not simplify it away.

## Hexagonal framing

The Backend Context is one hexagon. The inside is `application/` +
`domain/`. The outside is everything else, reached through
Adapters.

**Driving adapters (input):**

- FastAPI HTTP server in `api/` -- the user path's entry point.
- Worker runner in `worker/` -- the ingestion loop's entry point.
- CLI in `cli/` -- operator workflows (one-off ingestion, report
  apply).

All three call the same use cases in `application/`. The use cases
do not know which adapter invoked them.

**Driven adapters (output):**

- Postgres via `infra/db/` -- implements repo ports.
- Anthropic SDK via `infra/external/anthropic_client.py` --
  implements LLM ports.
- HTTP source fetcher via `infra/external/source_fetcher.py` --
  implements the source-fetcher port; target-restricted per
  INV-LLM-006 (no SSRF).

Adding a new client surface (a different HTTP framework, a queue
consumer, a gRPC server) lands as a new driving adapter. Swapping
Postgres for a different store lands as a new driven adapter.
Either change must not require touching `domain/`.

## Three-category type model

Three distinct type categories, with mappers between them. Each
category serves a different concern; conflating them is a recurring
source of bugs.

| Category | Where | What it represents |
| :--- | :--- | :--- |
| **Domain types** (Values + Entities) | `domain/{module}/` | The business model: invariants, behavior, Ubiquitous Language. Frameworkless. |
| **ORM rows** | `infra/db/models/` | Persistence: rows, columns, indexes. Knows the schema. |
| **Wire schemas** | `api/schemas/` | The HTTP/OpenAPI contract: request/response shapes. Knows JSON. |

**Mappers** (in `application/mappers/`) translate across each
boundary:

- ORM row → domain Entity / Value (load path).
- Domain Entity / Value → ORM row (write path).
- Domain → wire schema (response path).
- Wire request schema → domain command input (request path).

**The discipline:**

- ORM rows never leave `infra/db/`. Repo implementations return
  domain types; no other code returns ORM rows.
- Domain types never appear in HTTP responses. Routes return wire
  schemas; mappers translate.
- Wire schemas never enter the domain. Routes parse the request
  body into a wire schema, then map to a domain input.
- **Wire schemas are use-case-shaped, not Aggregate-shaped**
  (per `ddd/integrating-bounded-contexts.md` Principle 4). A
  route's response is composed for the integrator's question, not
  for raw access to a domain Aggregate. The SEO jurisdiction page
  wants jurisdiction summary + materials + counts in one
  request, not three round trips through `Jurisdiction`,
  `Material`, and `Rule` Aggregate endpoints. Naming routes after
  the integrator's use case (`/pages/jurisdiction/{slug}`,
  `/ask`) keeps Aggregate shape from leaking into the wire
  contract.

Per `ddd/architecture.md` Principle 4 ("do not expose the domain
directly") and `ddd/value-objects.md` Principle 7 ("reject
data-model leakage").

### Entity vs Value: the four diagnostic questions

When introducing a new domain concept, apply Vernon's diagnostic
(`ddd/value-objects.md` Principle 7). If the answers are
"describes, yes, yes, no," it is a Value:

1. Does this concept describe / measure / quantify a thing in the
   domain, or is it itself a thing?
2. If correctly modeled as descriptive, does it possess the five
   Value characteristics (describes, immutable, conceptual whole,
   replaceable, value equality)?
3. Am I considering an Entity *only* because the data store has to
   represent it as one?
4. Do I genuinely need unique identity and a managed life cycle, or
   am I confusing those with "has a row"?

Default to Value. Reach for Entity only when individuality and a
mutable life cycle are *both* required.

## Identity-generation policy

Every Entity in the Backend Context uses **application-generated
UUIDs**. Set in the constructor; never persistence-generated; never
mutated after construction.

- **Jurisdiction** -- `JurisdictionId` (UUID), issued by ingestion
  seed or admin.
- **Material** -- `MaterialId` (UUID), issued by ingestion seed or
  admin.
- **Rule** -- `RuleId` (UUID), issued by the ingestion worker at
  extraction time.
- **Source** -- `SourceId` (UUID), issued by the ingestion worker
  at fetch time.
- **AnswerAuditRecord** -- `AnswerAuditRecordId` (UUID), issued by
  the API service at record creation.
- **IngestionReport** -- `IngestionReportId` (UUID), issued by the
  ingestion worker at run start.

**Slugs are unique attributes, not identity.** `Jurisdiction.slug =
"denver-co-us"` is a unique-indexed attribute used for URL routes
and human lookup; it is not the Entity's identity. If a slug needs
correction, model it as an explicit domain operation, not a silent
mutation (per `ddd/entities.md` Principle 3).

**Identity types are themselves Values.** Every Entity declares
its typed-id Value Object before any field. Functions take
`SourceId`, not `UUID`. The type checker catches `by_rule_id(
source_id)` mistakes at compile time.

**Identity is minted on the repo, not in the application service.**
Per `ddd/repositories.md` Principle 5, every new-Aggregate path
begins with `id = repo.next_identity()`, then the Entity's
constructor consumes that id, then `repo.save(entity)`. Today's
implementation of `next_identity()` is `uuid.uuid4()` wrapped in
the typed-id Value; the seam exists so identity strategy can
change (Snowflake, external issuance, deterministic test ids)
without touching call sites.

**Corollary -- a client never supplies an id on a write path.**
Because `save()` is an upsert by id (see "Repositories" below),
binding a wire-supplied id into the domain command would let a
caller overwrite or forge another record -- audit-record forgery,
or clobbering a `Rule`. The wire-request-to-command mapper drops
any client-sent id; ids enter only via `next_identity()`. This is
the security reason the three-category model forbids wire schemas
from carrying identity into the domain, not merely a layering
preference.

## Three-level validation

Validation answers three different questions; do not collapse them
into one method on the Entity. Per `ddd/entities.md` Principle 9:

- **Attribute validation.** A single field is sane in isolation.
  Lives in the Value's or Entity's constructor as a guard.
  *Examples:* `MaterialId.value` is a valid UUID;
  `JurisdictionSlug` is non-empty kebab-case.

- **Whole-object validation.** All of an Entity's fields are
  individually valid *and* their combination is consistent. Lives
  in a dedicated **Validator** (a Specification) sited alongside
  the Entity in its Module. The Validator collects all violations
  through a notification handler rather than throwing on the first
  failure.
  *Example:* `AnswerAuditRecordValidator` enforces INV-PROD-001
  (every `Accepted` / `Refused` carries Citations; every
  `NotCovered` / `Conflicted` does not claim authority).

- **Composition validation.** A cluster of Entities is consistent
  together. Lives in a **Domain Service** that uses repo ports to
  load what it needs.
  *Example:* "this `Rule`'s `Jurisdiction` exists in the knowledge
  base before it can be published" (Ingestion-side).

**Adversarial input bounds sit at the API boundary, not in the
domain.** The three levels above answer domain *correctness*. Size
and rate limits on untrusted request input (the free-text `/ask`
`query`) are a distinct, earlier control: the route rejects an
over-length query before retrieval or prompt composition
(INV-LLM-007). "Is this well-formed" (attribute validation) and "is
this within safe bounds for an untrusted caller" (boundary guard)
are separate questions; the second does not become the first just
because both inspect one field.

A field-level guard does not need an aggregate. A whole-object
invariant is the prototypical aggregate-promotion trigger
(see "Aggregates" below). A composition invariant is a Domain
Service, not an aggregate.

## Aggregates

The project uses **Approach C with phasing**: non-trivial aggregate
shapes (whole-object invariants enforced by a Validator, inner
Entities under one Root, multi-Aggregate transactions deliberately
avoided) are introduced only when invariants demand them.

**Every Entity addressed by a Repository is an aggregate root.**
Per `ddd/repositories.md` Principle 1, "provide repositories only
for aggregates." The single-entity aggregate -- one Entity, no
inner Entities, identity + value-equality semantics -- is the
common case at MVP. The "phasing" below is about which roots grow
*non-trivial* invariants and inner Entities, not about which
Entities are aggregates.

**Promotion to non-trivial aggregate trigger:** an Entity becomes
a non-trivial aggregate root when it must enforce a *true business
invariant* whose violation would cost money, data integrity, or
audit. The schema may or may not be able to express the invariant;
the test is the business consequence, not the schema's capability.
The natural form is a Level-2 (whole-object) check enforced by a
Validator at the Entity's constructor.

**Current non-trivial aggregate roots:**

- **`AnswerAuditRecord`** -- the user path's only non-trivial
  aggregate root. The `AnswerAuditRecordValidator` enforces
  INV-PROD-001 at construction; the application service catches
  construction failure and maps to
  `NoEvaluation(reason=LLMRejected)` after retry exhaustion. Root
  + Values shape: `AnswerAuditRecordId`, `Query`, `JurisdictionId`,
  the `EvaluatedAnswer | NoEvaluation` outcome, and timestamps. No
  inner Entities.

**Single-entity aggregate roots (today, may grow non-trivial):**

- **`Jurisdiction`**, **`Material`**, **`Rule`**, **`Source`**
  (knowledge_base Module), **`IngestionReport`** (ingestion
  Module). Each has constructor-level (Level-1) guards only;
  whole-object invariants and inner Entities are deferred to the
  Ingestion design spec, where their invariants are designed in
  context.

**Cross-Entity references go by typed-id Value, never by object
reference** (per `ddd/aggregates.md` Principle 4).
`Rule.source_ids: list[SourceId]`, never
`Rule.sources: list[Source]`. This rule applies even to Entities
not yet promoted to aggregate roots, so that later promotion does
not require refactoring out of lazy-loaded SQLAlchemy
relationships. The application service or Domain Service loads
referenced entities through their repo ports.

## Repositories

Per `ddd/repositories.md`, the Repository's interface is the only
public path from the Application layer to instances of an Aggregate.
The seam matters more than the persistence technology: domain code
talks about Aggregates, infrastructure handles bytes.

### Persistence-oriented style

The three-category type model above means domain Entities are *not*
SQLAlchemy-mapped; mutations on a domain `Rule` are not tracked by
the ORM Session. The collection-oriented style described in
`ddd/repositories.md` Principle 3 needs implicit change-tracking
that our split types deny.

We therefore use **persistence-oriented** repos: the Application
Service hands modified Entities back to the repo explicitly.

```python
# domain/shared/repo.py  -- declared once; every aggregate repo extends it
class Repo[T, ID](Protocol):
    def next_identity(self) -> ID: ...
    def save(self, entity: T, /) -> None: ...        # positional-only
    def find_by_id(self, entity_id: ID, /) -> T | None: ...  # positional-only

# domain/knowledge_base/rule_repo.py  -- finders only; base supplies the rest
class RuleRepo(Repo[Rule, RuleId], Protocol):
    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]: ...
    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[Rule]: ...
```

The positional-only markers on `save` and `find_by_id` let concrete Pg
repos and test fakes use their own parameter names (`rule`, `record`,
etc.) without suppression -- both still conform to `Repo[T, ID]`.

`save(entity)` is idempotent (upsert by id). Per
`ddd/repositories.md` Principle 2, calling it twice with the same
Entity is benign, not an error. There is no `update()` method.

### Interface in `domain/`, implementation in `infra/db/repos/`

The Protocol lives next to its Aggregate
(`domain/knowledge_base/rule_repo.py`). The implementation lives in
`infra/db/repos/` and depends on SQLAlchemy. Application Services
receive the Protocol via FastAPI `Depends` and never import the
concrete class. The domain layer never imports `sqlalchemy`. Per
`ddd/repositories.md` Principle 4 + the layering rules above.

FastAPI dependency-provider functions in `deps.py` annotate their
return type as the domain Protocol (the port), not the concrete
implementation -- this is the DIP return-side complement to the
interface-in-domain, implementation-in-infra rule above.

### Domain Service ports

A `@final` Domain Service gets a `Protocol` port so the Application
layer depends on the seam, not the concrete class. Without a port,
test doubles cannot structurally substitute a `@final` class, and
tests must carry `# pyright: ignore[reportArgumentType]` suppressions.

**Pattern:**

- Declare `class XxxServicePort(Protocol)` in
  `domain/<module>/xxx_service_port.py` alongside the concrete service.
- Application Service consumers accept `XxxServicePort`, not
  `XxxService`. Provider functions in `deps.py` return the Protocol type.
- Concrete implementations and test fakes do NOT subclass the Protocol
  -- they satisfy it structurally (matching method signatures).

**Implemented:** `RetrievalServicePort` --
`backend/src/domain/retrieval/retrieval_service_port.py:13`
(commit 0c71744). When the port was added, the two
`# pyright: ignore[reportArgumentType]` suppressions in
`tests/application/test_answer_query.py` and
`tests/api/test_ask_route.py` were removed.

### Persistence exceptions translate at the boundary

Repo implementations catch SQLAlchemy framework exceptions
(`IntegrityError`, `OperationalError`, `StaleDataError`) and
re-raise as domain or application exceptions named in the
project's vocabulary (`DuplicateRuleSlugError`,
`ConcurrentModificationError`, `RuleNotFoundError`). The
application layer never imports `sqlalchemy.exc`. Detail in
`backend/error-handling.md`.

### Transactions are owned by the Application Service

Per `ddd/repositories.md` Principle 9, the Application Service
opens and commits the transaction (FastAPI dependency yields a
Session bound to the request); repo methods participate in
whichever Session is bound; repos never begin or commit
transactions of their own. The one-Aggregate-per-transaction
discipline (`ddd/aggregates.md` Principle 1) is enforced at this
seam.

### Use-case-optimal queries are a deferral, not a default

Cross-Aggregate views (the SEO page joining `Jurisdiction`,
`Material`, `Rule`, `Source`) are composed in the Application
Service for MVP: multiple repo calls, mapped to a wire view. If
finder counts climb past the number of true Aggregate-shaped reads,
first re-examine Aggregate boundaries
(`ddd/repositories.md` Principle 8); only then consider a separate
read-model Module.

### Test seam: in-memory repos satisfy the same Protocol

Because the port is a `Protocol` in `domain/`, an in-memory
`dict[Id, Entity]` implementation is the natural seam for
Application-Service and Domain-Service tests. Repo implementation
tests run against a real Postgres (test database, cleaned per
test). Mocked Sessions and mocked repo methods are not used.

## AnswerAuditRecord: append-only audit log, not Event Sourcing

`AnswerAuditRecord` is an append-only audit entry per query. It is
the simpler shape `ddd/architecture.md` Principle 9 recommends
before reaching for Event Sourcing.

**What this gives us:**

- Audit: every user-path invocation is recorded.
- Eval replay: golden cases re-run against archived inputs and
  outputs.
- Diagnostics: validator findings, retry counts, and latency are
  stored per record.
- Feedback association: user-submitted feedback ties to the
  `AnswerAuditRecordId` it concerns.

**What we have not adopted:**

- An Event Store. `AnswerAuditRecord` rows live in Postgres
  alongside the rest of the schema.
- Snapshotting. Records are immutable; replay reads them directly.
- CQRS. The record's read shape is the same as its write shape.

If a future requirement genuinely cannot be served by append-only
audit records (e.g., "show me how the system would have answered
this query six months ago against a different rule set"), revisit.
The cost of escalation is in the open by design.

## Frontend: Smart-UI rejection

Per `ddd/architecture.md` Principle 5 and `ddd/bounded-contexts.md`,
the Presentation Context renders state and collects input. It does
not decide what counts as valid, complete, grounded, or
authoritative.

Concretely:

- The grounding validator runs in the Backend Context, not the
  frontend.
- The frontend renders `EvaluatedAnswer | NoEvaluation` and
  per-item `ItemVerdict`s; it does not classify them.
- Feedback flows annotate an `AnswerAuditRecord`, not a domain
  decision.

**The OpenAPI-generated client is an input adapter, not a
passthrough.** The wire vocabulary stops at `frontend/lib/api/`;
components consume presentation-context types translated from
wire types in that wrapper.

```text
frontend/lib/api/
├── client.ts        # generated OpenAPI client (wire types)
├── types.ts         # generated wire types (request/response)
├── citation.ts      # shared presentation value (Citation)
├── jurisdiction.ts  # jurisdiction-page types + translate + fetch
├── material.ts      # material-page types + translate + fetch
└── index.ts         # thin public surface (presentation types only)
```

The translation renames wire fields to the Presentation Context's
terms (snake_case -> camelCase) and is organized by page concept --
one module per user-facing page, mirroring the Open Host Service's
use-case-shaped resources (`ddd/integrating-bounded-contexts.md`
Principle 4) and grouping by cohesive concept rather than a
mechanical "all types" bucket (`ddd/modules.md` Principle 2). The
seam is the point: when the wire shape diverges from what a page
renders, that page's module absorbs the change and components do
not move. Shared presentation values (e.g. `Citation`) get their
own module once a second page consumes them (`ddd/modules.md`
Principle 5). The durable form of this principle -- the why,
when, and guardrails -- lives in
`.claude/rules/frontend/frontend-mental-model.md`
(Architectural commitments).

## Synchronous default, async across different lifecycles

Per `ddd/architecture.md` Principle 8:

- **Inside the Backend Context, calls are synchronous.**
  Application services call domain services directly; repo ports
  and LLM ports are invoked synchronously from inside a use case.
- **Backend → Frontend is synchronous over the Open Host Service**
  (HTTP).
- **The Ingestion worker is asynchronous because its lifecycle
  differs** from the user path's: batch / scheduled /
  minutes-to-hours latency vs interactive / sub-second. The worker
  is *not* async because async is fashionable; it is async because
  the latency budget and the operator workflow demand it.

The user path day one publishes no Domain Events. Ingestion's
day-one design will need them (`RulePublished`, `RuleSuperseded`,
`IngestionReportApplied`) to drive Vercel revalidation; that work
belongs in the Ingestion design spec.

## Cross-references

- `ddd/principles-hub.md` -- DDD foundations and shard index.
- `ddd/architecture.md` -- the architectural-style principles this
  file applies.
- `ddd/modules.md` -- Module naming, cohesive-concept grouping,
  parent/child cluster exception.
- `ddd/aggregates.md` -- aggregate-design rules cited in the
  Aggregates section.
- `ddd/repositories.md` -- Repository style choice, port shape,
  exception translation, transactions, test seams.
- `ddd/event-sourcing.md` -- the A+ES alternative we deliberately
  did not adopt; the AnswerAuditRecord section captures the
  trigger for revisiting.
- `ddd/entities.md` -- identity-generation, surrogate hiding,
  three-level validation.
- `ddd/value-objects.md` -- five characteristics, typed identity,
  Standard Types, the four diagnostic questions.
- `ddd/services.md` -- Domain Services vs Application Services;
  push multi-step composition off the client.
- `ddd/application.md` -- thin Application Services, Commands,
  view-shaped rendering, transactions and authorization at the
  Application Service boundary.
- `ddd/bounded-contexts.md` -- Backend Context vs Presentation
  Context boundary.
- `ddd/integrating-bounded-contexts.md` -- OpenAPI as Published
  Language (Principle 3); use-case-shaped wire resources
  (Principle 4); ACL framing of the frontend's `lib/api/`.
- `contracts.md` -- HTTP wire-schema discipline.
- `data-model.md` -- Ubiquitous Language and persisted schema.
- `private/invariants.md` -- numbered invariants this architecture
  protects (notably INV-PROD-001).
- `refactoring.md` -- a refactor may not invert a layer dependency
  direction or rename a port without updating all dependents.
