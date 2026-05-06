---
paths:
  - "backend/**"
  - "frontend/**"
  - "private/specs/**"
---

# DDD shard -- context maps

Strategic-design principles for **relationships between bounded
contexts**: integration patterns, upstream/downstream direction,
translation, and cross-context state. Distilled from Vaughn
Vernon, *Implementing Domain-Driven Design*, Chapter 3 ("Context
Maps").

This shard covers **how contexts interact**. For what a bounded
context *is* and how to size one, see `bounded-contexts.md`. For
the index of shards, see `principles.md`.

## What a context map is

A Context Map captures the **existing terrain**: the bounded
contexts that exist today and the integration relationships
between them. It is not an enterprise architecture diagram, not a
deployment topology, not a future-state vision. It is a tool for
two purposes: (1) giving a team shared vocabulary about what is
actually wired up to what, and (2) forcing decisions about
**which integration pattern** governs each relationship.

The most detailed expression of a context map is the source code
of the integrations themselves. Diagrams are summaries; the code
is the truth.

## Principles

### 1. Map the existing terrain before drawing new lines

When proposing a boundary or a new integration, first describe
what is **already there** -- modules, tables, prompts, routes --
and the relationships among them. Speculative future contexts go
in a separate "where this is heading" section. Vernon: *a
Context Map captures the present, not the imagined future.*

**Apply when:** writing a new spec, splitting a module, proposing
a new service, or adding an integration with an external system.

### 2. Keep boundaries permeable but vetted

A boundary is not a wall. Things cross it -- but only on terms
the inside controls. Any value entering a context from outside
(HTTP request, ingestion source, LLM output, another module's
API) must be translated into the local model at the boundary,
never used directly downstream.

**Apply when:** adding any code that consumes data from outside
its context. The translation step is mandatory.

### 3. Pick one integration pattern explicitly per relationship

Vernon names several organizational patterns. Whenever two
contexts integrate, the spec **must** name which pattern is in
force.

- **Open Host Service + Published Language.** A context publishes
  its capabilities through a stable, documented protocol intended
  for external use. The protocol *is* the Published Language; the
  serving context *is* the Open Host. Default choice when one
  context expects multiple consumers.
- **Anticorruption Layer (ACL).** A translation layer that keeps
  foreign vocabulary out of the local model. Every external input
  (third-party API, file format, ML/LLM output, legacy system) is
  foreign and must be translated at the boundary. The translator
  lives inside the downstream context.
- **Customer-Supplier.** An asymmetric but cooperative
  relationship: the supplier's roadmap accommodates the
  customer's needs. Make the relationship explicit in a spec, not
  implicit in code.
- **Separate Ways.** Two areas have no real relationship; do not
  integrate them. Prefer this over speculative integration --
  cheaper to merge later than to split later.
- **Shared Kernel.** A small, jointly-owned set of types shared
  across contexts. Avoid by default; only acceptable when the
  cost of duplication exceeds the cost of coordinated change. If
  used, mark the shared module explicitly and document its change
  protocol.
- **Conformist.** The downstream context adopts the upstream's
  language wholesale. Acceptable only when integrating with a
  system the team cannot influence; conformism between
  internally-owned contexts is a smell.
- **Big Ball of Mud.** Name it when you see it. Do not extend it.
  Wrap it in an ACL.

### 4. Direction of dependency: upstream / downstream is a design decision

For every integration, label which side is upstream (provides
state or behavior) and which is downstream (consumes it). The
downstream context must:

- never assume the upstream context is available without an
  explicit fallback (refusal, retry, eventual consistency);
- never share the upstream's database;
- never let upstream vocabulary leak past the ACL.

### 5. Eventual consistency across contexts; transactional inside one

Inside a single bounded context, a single transaction may enforce
invariants. Across two contexts, do not span a transaction. If
state must propagate, use a Domain Event or an explicit
synchronization step, and design the receiver to tolerate
temporary disagreement.

**Apply when:** state must propagate from one context to another,
or a workflow spans both.

### 6. Make unavailability an explicit state, not an exception

When a downstream context depends on an upstream one and the
upstream might be unavailable, model the unavailability as a
domain state, not a thrown exception leaking to the user.

Vernon's example: a `DiscussionAvailability` enum with
`ADD_ON_NOT_ENABLED, NOT_REQUESTED, REQUESTED, READY`. The
"nothing here yet" case is a first-class domain outcome, not a
500.

**Apply when:** any cross-context call could fail or return
nothing. The "nothing" case must be a named domain value.

### 7. Translation maps are code, not magic

Every ACL needs a concrete translation: foreign shape → local
shape. That mapping lives in code (a function, an Adapter class)
inside the downstream context, not in the upstream system, not
in shared utilities, and not implicit in serialization.

**Apply when:** consuming any external input -- a generated
client, a third-party API response, an LLM output, a parsed file
format. The translator is code, not coincidence.

### 8. Keep the context map cheap

Vernon is emphatic: avoid ceremony. Do not build a separate
"context map document" with diagrams to maintain. If a discussion
needs a diagram, draw it in the spec it belongs to. Don't build
infrastructure to keep diagrams in sync with code; the code is
the truth.

## Cross-references

- `principles.md` -- DDD hub: index of shards.
- `bounded-contexts.md` -- principles for *defining* a single
  bounded context.
- `../contracts.md` -- the *shape* discipline for HTTP-boundary
  contracts; complementary to the *integration pattern* choice
  here.
- `../refactoring.md` -- a refactor may not move or rename an
  integration surface (the boundary between two contexts) without
  updating all dependents; that surface is a public contract in
  this sense even when both sides live in the same codebase.
