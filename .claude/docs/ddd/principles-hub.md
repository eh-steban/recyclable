---
# No auto-load. Reference explicitly from specs or agent prompts that need DDD context.
---

# DDD principles -- hub

Navigation only. Load a shard when its topic governs the current task.
Default: do not preload shards. If unsure which applies, ask before reading.

## When to load a shard

- Modifying domain or application code -> relevant tactical shard.
- Designing cross-service boundaries -> strategic shards.
- Writing a spec that names a bounded context -> `bounded-contexts.md`, `context-maps.md`.
- Reasoning about DDD itself (anemic model, DDD-Lite, Ubiquitous Language) -> `foundations.md`.

## Scope by service

- **Strategic shards** apply to both backend and frontend.
- **Tactical shards** apply to the backend only. Frontend agents should not load tactical shards.

## Strategic shards

- [`foundations.md`](foundations.md) -- Ch. 1. Pillars, anemic model, DDD-Lite, recurring challenges.
- [`bounded-contexts.md`](bounded-contexts.md) -- Ch. 2. Defining a single context.
- [`context-maps.md`](context-maps.md) -- Ch. 3. Relationships between contexts.
- [`architecture.md`](architecture.md) -- Ch. 4. Architectural styles inside a context.
- [`integrating-bounded-contexts.md`](integrating-bounded-contexts.md) -- Ch. 13. Cross-context integration.

## Tactical shards (backend only)

- [`entities.md`](entities.md) -- Ch. 5.
- [`value-objects.md`](value-objects.md) -- Ch. 6.
- [`services.md`](services.md) -- Ch. 7.
- [`domain-events.md`](domain-events.md) -- Ch. 8.
- [`modules.md`](modules.md) -- Ch. 9.
- [`aggregates.md`](aggregates.md) -- Ch. 10.
- [`factories.md`](factories.md) -- Ch. 11.
- [`repositories.md`](repositories.md) -- Ch. 12.
- [`application.md`](application.md) -- Ch. 14.
- [`event-sourcing.md`](event-sourcing.md) -- Appendix A.

## Interactions with other rules

- `../../rules/contracts.md` -- HTTP boundary shape; the DDD shards govern why that boundary exists.
- `../refactoring.md` -- contract-change rules. A cross-context integration surface counts as a public contract even when both sides live in this repo.
- `private/invariants.md` -- wins on conflict. Flag and escalate when a DDD principle conflicts with a numbered invariant.

## When to revisit

Update the hub when a shard is added, split, renamed, or when a principle proves vacuous in practice. Update via the `spec-writer` agent or explicit user approval, per `.claude/rules/doc-ownership.md`.
