---
# No auto-load. Load from `principles-hub.md` when slicing a plan's stories.
---

# Stories and INVEST

A **story** (a phase in a plan) describes a change in system behavior from
the perspective of a user: something they want to do that is not possible
today. It sits in the solution space, not the problem space. In this repo a
story is the unit that ships a usable, demoable increment.

## The three questions

Every story answers three things. The classic `As a [role], I want
[action] so that [value]` format is one way to capture them; the format
matters less than answering all three.

1. **Who** is it for? (role / persona)
2. **What** do they want to do that is not possible today?
3. **Why** do they want it? (the value)

A short title often carries the "what," with the "why" in notes. If you
cannot state the "what" without naming a layer ("the repos exist," "the
schema is migrated"), it is not a story -- it is a task, or a horizontal
slice. Re-slice it.

## INVEST

Every story ready to build passes the INVEST checklist (Bill Wake, 2003).
There is deliberate tension between the attributes: as stories get smaller,
independence and value get harder to hold. INVEST matters most near
delivery; further out, negotiability and value dominate.

- **I**ndependent -- can be prioritized and built in any order.
  Dependencies bottleneck and delay value.
- **N**egotiable -- not a rigid contract; details emerge through
  conversation. Builds shared understanding and allows learning.
- **V**aluable -- delivers a visible increment of value. Stops technical
  tasks from masquerading as stories.
- **E**stimable -- can be sized relative to other stories. Needed for
  planning and prioritization.
- **S**mall -- fits comfortably in one increment. Frequent feedback,
  lower risk.
- **T**estable -- has clear acceptance criteria. Keeps vague aspirations
  out of the work.

## Stories are vertical slices, not horizontal layers

A **vertical slice** touches every layer it needs (UI -> logic -> database,
across services when required) and produces observable value when shipped.
A **horizontal slice** is one layer -- "build the API this phase, the UI
next" -- which produces shippable code but no shippable value.

Do **not** split stories by architectural layer. It fails Valuable and
Independent. Working in vertical slices means value and feedback arrive
sooner, low-value work gets caught before it is built, and progress is
measured by working software.

**The walking skeleton is thick.** The first story is normally the largest,
because the thinnest end-to-end path still needs the migration, the core
type, the adapter, and the entry point all at once. Slicing does not remove
that cost; it front-loads it so every later story is a thin increment on a
running system.

## Adaptation for this repo (solo-dev-plus-agent)

The source practices assume a team on sprints. Two re-anchorings:

- **Small** is not "6-10 per sprint" (there is no sprint). Anchor it to
  *reviewable in one sitting* -- a diff a human can hold in one pass. When a
  story exceeds that, split it (`splitting-patterns.md`).
- **Estimable** carries little weight without sprint planning. Do not
  agonize over relative sizing; use it only as a smell -- a story you cannot
  size at all is a candidate for a spike (Pattern 9).

**Independence vs. the walking skeleton.** Our phases are deliberately
sequential: later stories build on the skeleton. That reads as a violation
of *Independent*, but it is a recognized split -- Pattern 6 (Major Effort
First) and Pattern 5's note that a follow-on story "builds on the first."
Story 1 is the foundational effort; later stories are the variations that
become trivial once the infrastructure exists. Record the dependency
explicitly (the plan's "Depends on" line); do not pretend the stories are
independent when they are not.

**Equal-sized stories vs. the walking skeleton.** `splitting-patterns.md`
prefers equal-sized stories. The walking-skeleton rule consciously
overrides that for Story 1 only. This is a trade named in the plan's Scope,
not a smell.
