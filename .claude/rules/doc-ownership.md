---
paths:
  - ".claude/**/*.md"
  - "private/**/*.md"
  - "**/CLAUDE.md"
---

# Documentation Ownership

Single source of truth for **who can write to which markdown / config
files** in this repo. This is about *documentation* ownership, not code
ownership or interservice contract ownership (see `contracts.md` for that).

**Last reconciled:** 2026-07-01

> Why this doc exists: ownership rules used to be scattered across
> `CLAUDE.md`, `knowledge-management.md`, `agents/spec-writer.md`, and a
> buried `skills/context-audit/references/ownership-map.md`. They drifted
> from each other. This file is now the single source -- everything else
> points here.

---

## How to read this

Every file under `.claude/` and `private/` falls into one of four
ownership classes:

- **Spec-writer owned**
  - *Who writes:* only the `spec-writer` agent (or its tools:
    `/consolidate-learnings`, `/kata-check`).
  - *Auto-apply:* yes, after user approval.
- **Service agent owned**
  - *Who writes:* only the named service agent (`backend-python`,
    `frontend-react`, etc.).
  - *Auto-apply:* yes, within that service's scope.
- **Append-only by service agents**
  - *Who writes:* service agents may append to a specific section;
    `spec-writer` curates.
  - *Auto-apply:* append yes; promote spec-writer only.
- **Owner-only**
  - *Who writes:* the human project owner (architectural / workflow
    decisions).
  - *Auto-apply:* no -- flag as "owner review needed".

If a file is not listed, treat it as **shared** -- any agent may edit,
with normal review gates.

---

## Spec-writer owned

- `private/product/strategy/vision.md` -- strategic direction.
- `private/product/strategy/current-options.md` -- active bets and
  outcomes.
- `private/product/strategy/parking-lot.md` -- spec-writer governs
  promotion / removal. Service agents may **append** new entries (see
  Append-only section below).
- `private/product/experiments/*/kata.md` -- Product Kata experiment
  files.
- `private/product/experiments/*/learnings.md` -- experiment outcome
  writeups.
- `private/specs/*.md` -- feature specs and task shards.
- `private/templates/katas/*.md` -- Kata template scaffolded by
  `/new-experiment`.
- `private/learnings.md` (above `## Drafts`) -- promoted, vetted
  learnings only.
- `private/learnings-index.md` -- updated only during
  `/consolidate-learnings`.
- `private/CONTEXT.md` -- written by `/switch-machine`, read by owner
  at session start.
- `private/invariants.md` -- non-negotiable system truths. Promotion,
  removal, or renumbering requires owner approval. Lives in `private/`
  (not `.claude/rules/`) because invariants encode proprietary product
  decisions that should not appear in the eventually-public repo tree.
- `.claude/rules/**/*.md` -- service rules, mental models, this file.
  Each rule declares its scope via a `paths:` glob list in frontmatter;
  service agents use this to decide which rules to read for a given
  task (see `.claude/agents/<agent>.md` "Loading rules on demand").
  When adding or moving a rule, keep `paths:` accurate -- stale globs
  cause agents to load the wrong rules or miss relevant ones.
- `.claude/knowledge-management.md` -- knowledge system process doc.
- `.claude/docs/ddd/**/*.md` -- the DDD shards (hub
  `principles-hub.md`); reference docs opened on demand via the hub,
  not auto-loaded.
- `.claude/docs/user-story-breakdown/**/*.md` -- the work-breakdown
  shards (hub `principles-hub.md`); reference docs opened on demand via
  the hub, not auto-loaded. Same treatment as the DDD shards.
- `.claude/docs/tdd.md`, `.claude/docs/validation.md`,
  `.claude/docs/refactoring.md`, `.claude/docs/formatting.md`,
  `.claude/docs/error-handling.md`, `.claude/docs/observability.md` --
  cross-cutting process and philosophy docs opened on demand by name.
  These and the DDD shards moved out of `.claude/rules/` so they stop
  auto-loading on every file read; same spec-writer ownership as the
  rules they came from. (`.claude/docs/infra/git.md` predates this move
  and keeps its existing ownership.)

## Append-only by service agents

- `private/learnings.md`
  - *Section:* `## Drafts` only.
  - *Format:*
    `### [Draft] [Topic] -- [agent: name, date: YYYY-MM-DD]`.
- `private/product/strategy/parking-lot.md`
  - *Section:* any of the categorized sections (Jurisdictions,
    Materials, Source documents, Other).
  - *Format:*
    `- [Label] -- one-line description. Source: [pointer]. Found: YYYY-MM-DD.`

Service agents may NOT touch any other section of `learnings.md`, the
index, the rules tree, or strategy files (other than appending to
`parking-lot.md` as above). `spec-writer` reviews drafts during
`/consolidate-learnings` and either promotes or discards. `spec-writer`
is the only agent that removes or promotes parking-lot entries.

## Service agent owned

Each service agent owns its own service directory's documentation.
The agent name maps to the directory:

- `backend-python` -- owns `backend/**/*.md` (except `backend/CLAUDE.md`,
  which is owner-only).
- `frontend-react` -- owns `frontend/**/*.md` (except
  `frontend/CLAUDE.md`, which is owner-only).
- `e2e-testing` -- owns `e2e/**/*.md` if present.

## Owner-only (flag, do not auto-apply)

These encode architectural or workflow decisions that require human
judgment.

| File / Pattern | Reason |
| --- | --- |
| `CLAUDE.md` (repo root, if present) | Project-wide conventions |
| `.claude/CLAUDE.md` | Project-wide conventions and pointers |
| `{service}/CLAUDE.md` | Service-specific conventions |
| `.claude/agents/*.md` | Agent responsibilities, tools, boundaries |
| `.claude/commands/*.md` | Workflow trigger definitions |
| `.claude/skills/**/SKILL.md` | Skill packages driven by external inputs |
| `.claude/settings.json`, `.claude/settings.local.json` | Configuration |

Agents proposing changes to these files should output the diff and stop,
not apply.

## Shared / no single owner

- `private/plans/` -- written by Claude's plan feature.
- Anything not listed above under `private/` or `.claude/` -- shared;
  normal review gates apply.

---

## How to update this doc

This doc is itself spec-writer owned (`.claude/rules/**/*.md`). When you
add a new file pattern or change ownership:

1. Edit this file (via spec-writer agent, or with explicit user approval).
2. Update the **Last reconciled** date at the top.
3. If the change affects the public-facing summary in
   `.claude/CLAUDE.md` ## Shared File Ownership, update that pointer if
   its phrasing is now wrong (it should remain a *pointer*, not a
   duplicate table).
4. If the change affects how the `context-audit` skill categorizes
   findings, the skill's `references/ownership-map.md` should already
   point here -- no separate update needed.

**Anti-pattern:** copy-pasting ownership rules into other docs. Other docs
should point here. The whole reason this file exists is to stop that drift.

---

## Pointers from other docs

These files point to this one and should not duplicate ownership tables:

- `.claude/CLAUDE.md` ## Shared File Ownership
- `.claude/knowledge-management.md` ## Ownership and write protocol
- `.claude/agents/spec-writer.md` ## Shared File Ownership
- `.claude/skills/context-audit/references/ownership-map.md`
- `private/product/strategy/current-options.md` (footer, removed --
  ownership is encoded here, not in per-file footers)
