# Documentation Ownership

Single source of truth for **who can write to which markdown / config files** in this repo. This is about *documentation* ownership, not code ownership or interservice contract ownership (see `contracts.md` for that).

**Last reconciled:** 2026-04-30

> Why this doc exists: ownership rules used to be scattered across `CLAUDE.md`, `knowledge-management.md`, `agents/spec-writer.md`, and a buried `skills/context-audit/references/ownership-map.md`. They drifted from each other. This file is now the single source -- everything else points here.

---

## How to read this

Every file under `.claude/` and `private/` falls into one of four ownership classes:

| Class | Who writes | Auto-apply? |
|---|---|---|
| **Spec-writer owned** | Only the `spec-writer` agent (or its tools: `/consolidate-learnings`, `/kata-check`) | Yes, after user approval |
| **Service agent owned** | Only the named service agent (`backend-python`, `frontend-react`, etc.) | Yes, within that service's scope |
| **Append-only by service agents** | Service agents may append to a specific section; `spec-writer` curates | Append: yes. Promote: spec-writer only |
| **Owner-only** | The human project owner (architectural / workflow decisions) | No -- flag as "owner review needed" |

If a file is not listed, treat it as **shared** -- any agent may edit, with normal review gates.

---

## Spec-writer owned

| File / Pattern | Notes |
|---|---|
| `private/product/strategy/vision.md` | Strategic direction |
| `private/product/strategy/current-options.md` | Active bets and outcomes |
| `private/product/strategy/parking-lot.md` | Spec-writer governs promotion / removal. Service agents may **append** new entries (see Append-only table below). |
| `private/product/experiments/*/kata.md` | Product Kata experiment files |
| `private/product/experiments/*/learnings.md` | Experiment outcome writeups |
| `private/specs/*.md` | Feature specs and task shards |
| `private/learnings.md` (above `## Drafts`) | Promoted, vetted learnings only |
| `private/learnings-index.md` | Updated only during `/consolidate-learnings` |
| `private/CONTEXT.md` | Written by `/switch-machine`, read by owner at session start |
| `.claude/rules/**/*.md` | Service rules, mental models, this file |
| `.claude/knowledge-management.md` | Knowledge system process doc |

## Append-only by service agents

| File | Section | Format |
|---|---|---|
| `private/learnings.md` | `## Drafts` only | `### [Draft] [Topic] -- [agent: name, date: YYYY-MM-DD]` |
| `private/product/strategy/parking-lot.md` | Any of the categorized sections (Jurisdictions, Materials, Source documents, Other) | `- [Label] -- one-line description. Source: [pointer]. Found: YYYY-MM-DD.` |

Service agents may NOT touch any other section of `learnings.md`, the index, the rules tree, or strategy files (other than appending to `parking-lot.md` as above). `spec-writer` reviews drafts during `/consolidate-learnings` and either promotes or discards. `spec-writer` is the only agent that removes or promotes parking-lot entries.

## Service agent owned

Each service agent owns its own service directory's documentation. The agent name maps to the directory:

| Agent | Owns |
|---|---|
| `backend-python` | `backend/**/*.md` (except `backend/CLAUDE.md` -- that's owner-only) |
| `frontend-react` | `frontend/**/*.md` (except `frontend/CLAUDE.md` -- owner-only) |
| `e2e-playwright` | `e2e/**/*.md` if present |

## Owner-only (flag, do not auto-apply)

These encode architectural or workflow decisions that require human judgment.

| File / Pattern | Reason |
|---|---|
| `CLAUDE.md` (repo root, if present) | Project-wide conventions |
| `.claude/CLAUDE.md` | Project-wide conventions and pointers |
| `{service}/CLAUDE.md` | Service-specific conventions |
| `.claude/agents/*.md` | Agent responsibilities, tools, boundaries |
| `.claude/commands/*.md` | Workflow trigger definitions |
| `.claude/skills/**/SKILL.md` | Skill packages driven by external inputs |
| `.claude/settings.json`, `.claude/settings.local.json` | Configuration |

Agents proposing changes to these files should output the diff and stop, not apply.

## Shared / no single owner

| File / Pattern | Access pattern |
|---|---|
| `private/plans/` | Written by Claude's plan feature |
| Anything not listed above under `private/` or `.claude/` | Shared; normal review gates apply |

---

## How to update this doc

This doc is itself spec-writer owned (`.claude/rules/**/*.md`). When you add a new file pattern or change ownership:

1. Edit this file (via spec-writer agent, or with explicit user approval).
2. Update the **Last reconciled** date at the top.
3. If the change affects the public-facing summary in `.claude/CLAUDE.md` ## Shared File Ownership, update that pointer if its phrasing is now wrong (it should remain a *pointer*, not a duplicate table).
4. If the change affects how the `context-audit` skill categorizes findings, the skill's `references/ownership-map.md` should already point here -- no separate update needed.

**Anti-pattern:** copy-pasting ownership rules into other docs. Other docs should point here. The whole reason this file exists is to stop that drift.

---

## Pointers from other docs

These files point to this one and should not duplicate ownership tables:

- `.claude/CLAUDE.md` ## Shared File Ownership
- `.claude/knowledge-management.md` ## Ownership and write protocol
- `.claude/agents/spec-writer.md` ## Shared File Ownership
- `.claude/skills/context-audit/references/ownership-map.md`
- `private/product/strategy/current-options.md` (footer, removed -- ownership is encoded here, not in per-file footers)
