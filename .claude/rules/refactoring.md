---
paths:
  - "backend/**/*.py"
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.js"
  - "frontend/**/*.jsx"
---

# Refactoring rules

What counts as a refactor in this repo, what is allowed, and what is
forbidden by default. The refactorer agent reads this on every run.
Other agents (code-reviewer, adversarial-reviewer) reference it to
flag out-of-scope refactoring inside non-refactor changes.

A refactor improves internal design while preserving behavior
exactly. If a change must alter behavior, it is not a refactor --
escalate to an implementation or fix plan.

## Hard rules

- If baseline validation fails, stop and report the failure. Do not
  refactor on a red baseline unless explicitly instructed.
- If behavior preservation cannot be proven with existing tests,
  either add a characterization test first or stop and report the
  risk. Do not refactor on an unverifiable baseline.
- Preserve every invariant in `private/invariants.md` exactly.
  A refactor is forbidden from changing behavior that an invariant
  pins down. If a refactor would touch one, it is not a refactor.
- Preserve public APIs, response shapes, status codes, error
  behavior, database writes, authorization behavior, LLM
  grounding / refusal behavior, logging behavior, migrations,
  prompts, validators, and regression cases.
- Do not add features.
- Do not add dependencies.
- Do not introduce speculative abstractions.
- Do not perform formatting-only churn outside touched code.
- Prefer small, mechanical, reviewable transformations over broad
  rewrites.
- Keep the final diff smaller and easier to review than the
  implementation diff would have been without refactoring.
- If project conventions conflict with generic clean-code advice,
  follow project conventions.

## Decision rules

- If a refactor would require guessing about product intent, do not
  do it.
- If a smell exists but was not touched by the implementation and
  does not block the change, report it under `FOLLOW-UPS NOT DONE`
  instead of modifying it. The refactor's scope is the
  implementation's blast radius, not the whole codebase.
- If a refactor would make the diff substantially larger without
  clear maintainability payoff, do not do it.
- If a refactor breaks tests, fix the refactor immediately or
  revert that step. Do not modify tests to fit the refactor. Tests
  may be updated for renamed internals only when behavior
  assertions stay equivalent or stronger.

## Refactoring targets

Focus only on code touched by, adjacent to, or made worse by the
implementation. Prioritize:

- Long methods or functions that now mix multiple responsibilities.
- Duplicated logic introduced or amplified by the implementation.
- Complex conditionals that obscure business rules or error
  handling.
- Primitive obsession, long parameter lists, or data clumps that
  make misuse likely.
- Feature envy, misplaced domain logic, or DDD layer leakage
  (domain logic in `infra/` or `api/`, infrastructure concerns in
  `domain/`).
- Dead code, speculative generality, unnecessary comments, or
  stale TODOs introduced by the change.
- Naming that hides intent or makes future edits error-prone.

## Allowed refactors

- Extract function, method, component, or helper.
- Inline unnecessary wrapper or middleman.
- Rename local private symbols for intent.
- Replace duplicated literals with well-named constants when it
  clarifies domain meaning.
- Replace nested conditionals with guard clauses.
- Consolidate duplicate conditional fragments.
- Introduce a small parameter object or value object only when it
  removes a repeated data clump and matches existing project
  conventions.
- Remove dead code introduced by the change.
- Move logic to the correct DDD layer when the existing pattern is
  clear.
- Split files, classes, or components only when the current unit
  has crossed a meaningful responsibility boundary.

## Forbidden by default

- Prompt changes.
- Validator changes.
- Regression case changes.
- Migration changes.
- Public contract changes (response shapes, status codes, route
  paths, event payloads).
- Renaming public symbols unless all call sites and external
  contracts are verified.
- Large rewrites.
- New frameworks or architectural patterns.
- Broad cleanup outside the implementation scope.
- Modifying tests only to make a refactor fit.

## DDD principles as refactor constraints

The DDD shards under `.claude/rules/ddd/` (hub:
`principles-hub.md`) define what counts as a domain-layer
boundary. Several principles act as explicit constraints on what
"behavior-preserving" means. A change that crosses one of these is
not a refactor:

- **Aggregate boundaries are not refactor-movable.** Splitting,
  merging, or relocating an Aggregate, or moving an invariant
  across Aggregates, is a design change. Cite `aggregates.md`
  Principles 1, 4.
- **Repository implementation swaps are refactor-safe only if the
  public interface is unchanged.** Hibernate → SQLAlchemy, MongoDB
  → Postgres, in-memory → real store: all fine *iff* the interface
  in the domain Module stays byte-identical. Renaming a finder
  method or changing its return shape is a contract change. Cite
  `repositories.md` Principle 1; `event-sourcing.md` "What this
  shard does NOT govern" if A+ES is involved.
- **Open Host Service / Published Language renames are contract
  changes.** Renaming a field on the wire format or a resource path
  is never a refactor. Cite `integrating-bounded-contexts.md`
  Principle 3; `context-maps.md`.
- **Bounded Context boundary moves are never refactors.** Moving a
  concept from one context to another, splitting a context, or
  merging two contexts is a strategic design change. Escalate to
  spec, not refactor. Cite `bounded-contexts.md`.
- **Domain Event schema changes are not refactors.** Adding a field
  is safe under tag-based serialization (Protocol Buffers, Avro);
  renaming or removing one is a versioned migration, not a
  refactor. Cite `event-sourcing.md` Principle 10 if A+ES is in
  use; `domain-events.md` for general Event evolution.

## SOLID at refactor scope

The five principles, scoped to what counts as behavior-preserving.
Where a DDD shard already encodes a principle in depth, this section
states the refactor-time rule and points there for the deeper
treatment. Canonical definitions:
[SOLID](https://en.wikipedia.org/wiki/SOLID).

- **S -- Single Responsibility.** A unit has one reason to change.
  Trigger: a function or class the implementation just made longer
  because it now mixes two concerns (parsing + I/O, retrieval +
  formatting, validation + persistence). Allowed: extract method,
  class, or component to separate them. Do not split a unit that
  already has one reason to change "for symmetry."

- **O -- Open/Closed.** Open for extension, closed for modification.
  At refactor scope this is mostly a *constraint*: do not edit a
  stable abstraction (a port, a Strategy, a Factory) to shoehorn a
  new case. A new case is an implementation change -- escalate. A
  refactor may expose an existing seam more cleanly; it may not
  rewrite a closed contract.

- **L -- Liskov Substitution.** A subtype must be usable wherever
  its supertype is, with no caller checking which one it holds.
  Trigger: an override that strengthens a precondition, weakens a
  postcondition, throws an exception the base type does not declare,
  or relies on runtime type discrimination at the callsite. A
  refactor may not introduce such an override, and may not remove a
  type-discriminating check unless no caller depended on it. The
  polymorphic-Aggregate / Repository case is covered in
  `ddd/repositories.md` Principle 1.

- **I -- Interface Segregation.** Clients should not depend on
  methods they do not use. Trigger: a port has grown a method only
  one consumer calls, or a domain Entity exposes methods only the
  persistence layer needs. Splitting an internal interface is
  allowed when the externally visible contract is unchanged.
  Splitting an interface that crosses a Bounded Context, or removing
  a method from an Open Host Service or Published Language, is a
  contract change.

- **D -- Dependency Inversion.** High-level code depends on
  abstractions; abstractions do not depend on details. The domain
  owns the interface; infrastructure provides the implementation.
  Trigger: an import of `infra/` (or a framework type) from inside
  `domain/`, or a port inlined at its callsite. A refactor may not
  invert this direction. Deeper treatment in `ddd/architecture.md`
  Principle 2 and `architecture.md` "Layers + DIP".

## Use by other agents

- **Refactorer agent (Phase 6):** reads this file at the start of
  every run; its `BEHAVIOR PRESERVATION` output section is the
  enforcement point.
- **Code-reviewer:** flags changes inside an implementation or fix
  PR that match the "Forbidden by default" list as out-of-scope
  refactors. The implementer is asked to either move them to a
  separate refactor plan or remove them from the change.
- **Adversarial-reviewer:** uses the "Hard rules" list as a
  baseline; a finding that reveals a refactor changed an invariant
  is escalated to CRITICAL.
