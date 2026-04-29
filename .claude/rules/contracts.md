---
paths:
  - "backend/app/domain/**"
  - "frontend/lib/domain/**"
  - "private/specs/contracts/**"
---
# Interservice Contract Standards

Rules for agents working on features that cross service boundaries.

## What Is a Contract

A contract is the agreed JSON shape at a service boundary -- e.g., the response body a backend returns to a frontend, or the payload one microservice sends to another.

Contracts live as spec files in `private/specs/contracts/`. These files are the single source of truth. When code and spec diverge, update the spec first, then update the consuming service.

## Ownership

Each contract has exactly one owner agent (the service that produces the shape) and one or more consumer agents (services that read the shape). The owner updates the spec; consumers read it.

| Contract | Boundary | Owner | Consumer |
|----------|----------|-------|----------|
| `answer.md` | Postgres / DB layer -> Next.js `/api/ask` -> client | `frontend-react` (the route handler that produces the shape) | client `<AnswerCard />`; regression suite (`backend-python`) |
| `ingestion-report.md` | `backend-python` worker -> admin UI / DB | `backend-python` | admin UI in `frontend-react` |
| `db-schema.md` | Postgres tables -> both services | `backend-python` (owns Alembic migrations) | `frontend-react` (`lib/domain/` types must match) |

The `db-schema.md` contract is special: it is the only "shape" that both services consume directly (Next.js reads tables for the user path, the worker reads + writes for ingestion). `.claude/rules/data-model.md` is the human-readable form; `db-schema.md` is the per-PR contract diff.

## Contract-First Rule

**A task shard that adds, removes, or renames a field crossing a service boundary must update the contract spec before touching implementation code.**

This applies whenever a type definition that serializes to JSON changes on either side of a boundary -- Pydantic models on the backend, TypeScript interfaces on the frontend, serde structs in a Rust service, etc.

## Enforcement Checkpoints

When completing a shard that touches a contract, each affected agent should verify:

**Owner agent:**
- [ ] Is the new/changed field documented in the contract spec with type, required/optional, and notes?
- [ ] Do existing schema tests still pass?

**Consumer agent:**
- [ ] Do the consumer's type definitions match the contract spec exactly?
- [ ] Did you read the spec, not infer field types by reading the owner's source code?

## Phase 0 in Implementation Plans

Any implementation plan spanning multiple services should include a Phase 0 that locks the contract before parallel work begins. This prevents owner and consumer agents from diverging mid-flight.

## When Contracts Are Not Required

Contracts apply only to JSON at service boundaries. Internal refactors within a single service (renaming a private struct, splitting a helper function) do not require spec updates.

## Versioning

If the project caches data by schema version, increment the version when a contract has a breaking change (field removed, type narrowed). Non-breaking additions (new optional field) do not require a version bump.
