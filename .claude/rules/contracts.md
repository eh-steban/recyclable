---
paths:
  - "backend/src/domain/**"
  - "frontend/lib/domain/**"
  - "private/specs/contracts/**"
---

# Interservice Contract Standards

Rules for agents working on features that cross service boundaries.

For DDD framing of *what counts as* a contract crossing a Bounded
Context, see `.claude/rules/ddd/integrating-bounded-contexts.md`
Principle 3 (Published Language, not shared classes) and
`.claude/rules/ddd/context-maps.md` for the relationship patterns
that govern the boundary.

## What is a contract

A contract is the agreed JSON shape at a service boundary -- e.g., the
response body a backend returns to a frontend, or the payload one
microservice sends to another.

Contracts live as spec files in `private/specs/contracts/`. These files
are the single source of truth. When code and spec diverge, update the
spec first, then update the consuming service.

## Ownership

Each contract has exactly one owner agent (the service that produces the
shape) and one or more consumer agents (services that read the shape).
The owner updates the spec; consumers read it.

One block per contract. A wide table here violates the
markdown-style 80-col cap once the boundary and consumer fields
are filled in.

### `answer.md`

- **Boundary:** backend FastAPI `POST /ask` -> Next.js `/ask` UI ->
  client. The OpenAPI spec the backend emits is the Published
  Language between the two contexts.
- **Owner:** `backend-python` (the route handler that produces the
  shape).
- **Consumers:** backend regression suite
  (`backend/tests/regression/`); frontend `<AnswerCard />` through
  the consumer-side ACL at `frontend/lib/api/translate.ts`.

### `ingestion-report.md`

- **Boundary:** `backend-python` worker -> admin UI / DB.
- **Owner:** `backend-python`.
- **Consumers:** admin UI in `frontend-react`.

### `db-schema.md`

- **Boundary:** Postgres tables -> both services.
- **Owner:** `backend-python` (owns Alembic migrations).
- **Consumers:** `frontend-react` (`lib/domain/` types must match).

The `db-schema.md` contract is special: the frontend does NOT connect
to Postgres directly. The frontend's "consumption" of this contract
means its generated TS types (produced by `npm run codegen:api`) must
stay in sync with what the backend's OpenAPI spec exposes, which
reflects the schema. The worker reads + writes Postgres directly.
`.claude/rules/data-model.md` is the human-readable form; `db-schema.md`
is the per-PR contract diff.

## Contract-first rule

**A task shard that adds, removes, or renames a field crossing a service
boundary must update the contract spec before touching implementation
code.**

This applies whenever a type definition that serializes to JSON changes on
either side of a boundary -- Pydantic models on the backend, TypeScript
interfaces on the frontend, serde structs in a Rust service, etc.

## Enforcement checkpoints

When completing a shard that touches a contract, each affected agent
should verify:

**Owner agent:**

- [ ] Is the new/changed field documented in the contract spec with type,
  required/optional, and notes?
- [ ] Do existing schema tests still pass?

**Consumer agent:**

- [ ] Do the consumer's type definitions match the contract spec exactly?
- [ ] Did you read the spec, not infer field types by reading the owner's
  source code?

## Contract phase in implementation plans

Any implementation plan spanning multiple services should include a
contract phase (Phase 1 in the implementation template at
`private/templates/plans/implementation.md`) that locks the contract
before parallel work begins. This prevents owner and consumer agents
from diverging mid-flight.

## When contracts are not required

Contracts apply only to JSON at service boundaries. Internal refactors
within a single service (renaming a private struct, splitting a helper
function) do not require spec updates.

## Versioning

If the project caches data by schema version, increment the version when a
contract has a breaking change (field removed, type narrowed). Non-breaking
additions (new optional field) do not require a version bump.
