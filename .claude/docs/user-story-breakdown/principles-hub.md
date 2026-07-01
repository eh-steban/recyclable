---
# No auto-load. Reference explicitly from the plan template, specs, or
# agent prompts that break work into stories and tasks.
---

# User story breakdown -- hub

Navigation only. Load a shard when its topic governs the current task.
Default: do not preload shards. If unsure which applies, ask before reading.

How we slice work into deliverable increments: the work hierarchy, what
makes a good story, acceptance criteria, and how to split a story that is
too big. Adapted for this repo's plan structure (`private/plans/`) from a
consolidated set of industry practices -- INVEST (Bill Wake, 2003),
Given-When-Then (Dan North, 2003), Richard Lawrence's story-splitting
patterns, and Dave Snowden's Cynefin. See "Sources" below.

## The work hierarchy

Five nested levels. The generic agile names on the left; how each binds to
this repo on the right.

| Level | Generic definition | In this repo |
| :--- | :--- | :--- |
| Theme | Strategic objective / business area | `private/product/strategy/` |
| Epic | Large goal, too big for one iteration | An experiment (`exp-02`) |
| Feature | A capability within an epic | A plan under `private/plans/` |
| **Story** | A user need that delivers value | A **phase** in a plan |
| **Task** | A technical step of a story | A **step**; one commit |

The two bold rows are where day-to-day plan work happens: a plan is a list
of **stories** (phases), each story is a list of **tasks** (steps), and
each task lands as one green commit. An experiment groups several plans the
way an epic groups several features.

## When to load a shard

- Writing or slicing a plan's stories (phases) -> `stories-and-invest.md`.
- Deciding when a story is "done" / writing checks -> `acceptance-criteria.md`.
- A story feels too big to deliver in one increment ->
  `splitting-patterns.md`.
- Unsure how knowable the work is, or guarding against backlog smells ->
  `context-and-antipatterns.md`.
- Breaking a story into tasks / commits, or wiring the review gate ->
  `tasks-and-commits.md`.

## Shards

- [`stories-and-invest.md`](stories-and-invest.md) -- the three questions,
  the INVEST checklist, and the vertical-slice rule. Start here.
- [`acceptance-criteria.md`](acceptance-criteria.md) -- the 3 C's and the
  Given-When-Then format; how criteria become checks.
- [`splitting-patterns.md`](splitting-patterns.md) -- Lawrence's 9 splitting
  patterns, how to evaluate a split, and the meta-pattern.
- [`context-and-antipatterns.md`](context-and-antipatterns.md) --
  Cynefin-informed splitting and the anti-patterns table.
- [`tasks-and-commits.md`](tasks-and-commits.md) -- this repo's task layer:
  a task as a green, committable unit; commit-per-task; the story gate.

## Quick reference

```text
HIERARCHY:    Theme -> Epic -> Feature -> Story -> Task
              strategy  experiment  plan   phase   step/commit

STORY FORMAT: As a [role], I want [action] so that [value]

INVEST CHECK: Independent . Negotiable . Valuable . Estimable . Small .
              Testable

AC FORMAT:    Given [state] / When [action] / Then [outcome]

SPLIT ORDER:  1 Workflow Steps    2 Operations (CRUD)  3 Business Rules
              4 Data Variations   5 Entry Methods       6 Major Effort First
              7 Simple + Complex  8 Defer NFRs           9 Spike (last)

EVALUATE:     pick the split that reveals deletable work AND produces
              equal-sized stories
META-PATTERN: find complexity -> identify variations -> reduce to one slice
```

## Interactions with other rules

- `private/templates/plans/implementation.md` -- the plan template
  instantiates this hierarchy: plan = feature, phase = story, step = task.
- `../tdd.md` -- a story's acceptance criteria drive its behavior checks;
  each task ships green. Given-When-Then maps onto the checkpoint's
  behavior checks and increment demo.
- `private/invariants.md` -- wins on conflict. A splitting choice never
  overrides a numbered invariant.

## Adaptation note (solo-dev-plus-agent)

The source practices assume a team on sprints. Two criteria are re-anchored
here (details in `stories-and-invest.md`): **Small** means "reviewable in
one sitting," not "6-10 per sprint"; **Estimable** matters less with no
sprint planning. The walking-skeleton rule (Story 1 is deliberately the
largest) is a conscious override of "equal-sized stories," justified by
splitting Pattern 6 (Major Effort First).

## Sources

Derived from a personal practice doc consolidating: Bill Wake, INVEST
(2003); Dan North, Behavior-Driven Development / Given-When-Then (2003);
Richard Lawrence, story-splitting patterns (Humanizing Work); Dave Snowden,
Cynefin. The work-facing original lives outside this repo.

## When to revisit

Update the hub when a shard is added, split, or renamed, or when a
principle proves vacuous in practice. Update via the `spec-writer` agent or
explicit user approval, per `.claude/rules/doc-ownership.md`.
