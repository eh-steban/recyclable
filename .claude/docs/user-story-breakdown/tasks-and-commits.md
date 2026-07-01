---
# No auto-load. Load from `principles-hub.md` when breaking a story into
# tasks or wiring the review gate.
---

# Tasks and commits

This shard is specific to this repo. The industry sources (see the hub) name
**Task** in the hierarchy but give it no guidance -- all their rules are
about stories. This is where a story becomes code: how it decomposes into
tasks, and how those tasks land in history.

## What a task is

A **task** is the technical sub-unit of a story (a step, `N.k`, in a plan).
Unlike a story, a task is **not** independently valuable and **not**
independently shippable -- it is one move down the stack inside the slice
(domain -> infra -> application -> API -> UI). Do not apply INVEST to a
task, and do not dress a task up as a story ("As a developer, I want a
repo"). Tasks have no user; stories do.

The story stays a vertical slice. Its tasks are the horizontal layers
*inside* that slice -- which is fine, because the slice as a whole still
ships value. Horizontal is only a smell at the story boundary, never inside
one.

## What makes a good task

- **Green in isolation.** After the task's commit, the tree compiles and the
  task's own targeted tests pass -- even though the story's end-to-end demo
  only lights up at the last task. "Green at every commit" is what makes the
  history bisectable and each commit reviewable on its own.
- **One coherent commit.** A task maps to exactly one commit: a single
  layer-crossing or component, not a grab-bag.
- **A clean file set.** Order tasks so each touches an additive or disjoint
  set of files. Clean boundaries keep each commit legible and keep the
  cumulative story diff easy to read at the gate.

## Ordering tasks

Tasks walk down the stack within the story, ordered so each ends at a green,
committable state that the next builds on. For a gated read surface, the
reviewable chain is typically: contract (if any) -> domain type -> repo /
persistence -> application use case -> API route -> UI. Each link is a
coherent diff a reviewer can hold in one pass.

The **contract task** (`N.1`, only when the story crosses a service
boundary) is exempt from the red/green record -- its spec diff is the
artifact -- but it is still its own commit and still blocks the rest of the
story.

## Commit-per-task, non-blocking

Commit each task the moment it is green, as the work proceeds. These commits
are **non-blocking**: you do not stop for review at each one. They accrue on
the branch during the story so that:

- each commit is genuinely green in isolation (it was built and verified
  that way, not carved out of a finished tree afterward), and
- the granular, bisectable history already exists by the time the story is
  done -- nothing to reconstruct.

Reviewing as commits land is available but optional. The only thing that
*halts* progress is the story gate.

## The story gate

One blocking review per story (phase), at the end:

1. The story's work is complete; its per-task commits are already on the
   branch, each green.
2. Present the **full cumulative diff** for the story for one holistic
   review -- the reviewer sees the whole slice at once, not only the
   per-task pieces.
3. The reviewer ticks the story's user-review checkbox. That tick is the
   single blocking gate (per the checkpoint protocol in the plan template).
4. Only then does the story count as done and the next story begins.

This gives both wins at once: granular, verified, bisectable history from
commit-per-task, and a single whole-slice review a human signs off on. See
`../tdd.md` for the per-task green record and
`private/templates/plans/implementation.md` for the checkpoint the gate
lives in.
