# Knowledge Management System

This document defines how to capture, organize, and reference knowledge
across the project. It prevents valuable discoveries from being lost and
enables Claude instances to discover relevant knowledge when needed.

**Key principle:** Learnings load on-demand based on what you're working on,
not all at once. Use `private/learnings-index.md` to find what's relevant.

---

## Quick start: where does this discovery go?

### Decision matrix

| Discovery Type | Destination | When to Use | Size |
|---|---|---|---|
| Cross-project pattern (appears 2+ times) | `private/learnings.md` | "We keep making this mistake" across services | 20-40 lines |
| Service-specific architecture constraint | `.claude/rules/[service]/[service]-mental-model.md` | Full explanation unique to one service | 200-400 lines |
| Feature-specific requirement/assumption | `private/specs/NNN-feature.md` → Assumptions section | This feature depends on X being true | 5-15 lines |
| Experiment outcome/validation | `private/product/experiments/NNN/learnings.md` | After experiment reaches terminal status | 20-50 lines |
| Code-level implementation detail | Inline code comment | Points to where detailed info lives | 1-3 lines |

### Quick decision flow

```text
You discover something important
    ↓
Have you seen this pattern 2+ times?
    → Yes → Does it affect multiple services?
            ↳ Yes → private/learnings.md (link to mental model)
            ↳ No  → .claude/rules/[service]/[service]-mental-model.md
    → No  → Is it service-specific architecture?
            ↳ Yes → .claude/rules/[service]/[service]-mental-model.md
            ↳ No  → Is it feature-specific?
                    ↳ Yes → private/specs/NNN-feature.md → Assumptions
                    ↳ No  → Inline code comment
```

---

## When to check `private/learnings.md`

Don't load all learnings at once. Instead, check the index BEFORE:

- Starting work on any feature in a domain area previously worked on
- Making storage or data architecture decisions
- Debugging issues that seem architectural or cross-service
- Implementing anything that touches integration boundaries

**Process:**

1. Read `private/learnings-index.md` (find relevant topic)
2. If a learning applies, load that entry from `private/learnings.md`
3. Follow links to mental models for deeper context

---

## The five tiers explained

### Tier 1: `private/learnings.md` (cross-project discoveries)

**What goes here:** Discoveries that affect multiple services or prevent
repeated mistakes

**Characteristics:**

- Pattern has appeared 2+ times (or would save 2+ hours if next person
  knows about it)
- Affects 2+ services or critical to understanding system
- High-impact insight (prevents debugging cycles)
- Cross-project (not specific to one feature or experiment)

**Lifespan:** Permanent reference material
**Maintenance:** Update when new pattern identified (check quarterly for
stale entries)
**Discovery mechanism:** Use `private/learnings-index.md` to find relevant
learnings

**Ownership and write protocol:** See `.claude/rules/doc-ownership.md` for
the canonical table. The relevant rule for this file: service agents append
to `## Drafts` using
`### [Draft] [Topic] -- [agent: agent-name, date: YYYY-MM-DD]`;
`spec-writer` reviews during `/consolidate-learnings` and promotes or
discards.

**When to add:**

- "We keep forgetting this" (pattern appears 2nd time)
- "This affects multiple services" (architectural constraint crossing
  boundaries)
- "This would save someone hours" (expensive learning cycle preventable
  with upfront context)

**When NOT to add:**

- One-off bug fixes (belongs in commit message)
- Single-feature assumptions (belongs in spec)
- Service-only gotchas (belongs in mental model)
- Implementation details (belongs in code)

---

<!-- markdownlint-disable-next-line MD013 -->
### Tier 2: `.claude/rules/[service]/[service]-mental-model.md` (service-specific architecture)

**What goes here:** Deep dives into service-specific architecture, gotchas,
and patterns

**Characteristics:**

- Non-obvious architectural constraint in one service
- Expensive debugging cycle if not documented
- Patterns emerging from service-specific code review
- Data flow or encoding quirk unique to this service

**Lifespan:** Permanent reference material (updated when architecture changes)

**When to create:**

- You've debugged the same issue in one service 2+ times
- Architectural decision seems counterintuitive (needs explanation)
- Data encoding or structure is non-standard
- Interaction between subsystems within one service is complex

**Content structure:**

1. Core Concept -- What makes this service unique
2. Architecture Constraints -- Decisions that seem odd but are necessary
3. Data Flow/Assumptions -- How data moves through the service
4. Common Gotchas -- Mistakes developers make and why they're wrong
5. Debugging Checklist -- How to verify things are working correctly

---

### Tier 3: `private/specs/NNN-feature.md` → Assumptions + Related Docs (feature-specific)

**What goes here:** Dependencies and constraints specific to this feature

**When to add:**

- Specifying any new feature (Assumptions section is mandatory)
- Documenting data requirements (Related Docs links everything)
- Explicitly noting dependencies between services

**Key principle:** Every spec assumption should cite where that knowledge
lives (learnings.md, mental model, interview notes, etc.)

---

### Tier 4: `private/product/experiments/NNN/learnings.md` (experiment outcomes)

**What goes here:** What you learned from completing an experiment

**When to create:**

- After `/kata-check` confirms experiment reached terminal status
- Only for Product Kata experiments (not every debugging session)

---

### Tier 5: Code comments (implementation details)

**What goes here:** Pointers to foundational knowledge, implementation gotchas

**Format:**

```python
# CRITICAL: [Brief explanation of non-obvious behavior]
# See .claude/rules/[service]/[service]-mental-model.md for full details
```

---

## Learnings entry format template

```markdown
## [Title: Concise statement of the discovery]

**Date discovered:** [Month Year, Context where discovered]
**Impact:** [Which services/teams affected -- be specific]
**Status:** [active | deprecated | investigating | pattern-identified | validated]

[One paragraph explaining the core insight]

**Key Takeaway:**
[One sentence: The actionable insight or rule of thumb]

**Related Docs:**
- [Link to detailed mental model if exists]
- [Link to specs that depend on this]

**When to Reference:**
[Bullet list of situations where this learning applies]

**Prevention:**
[Checkmarks for how to prevent forgetting this]
```

---

## Anti-patterns: what NOT to do

### ✗ Duplicate between tiers

- Don't repeat mental model content in learnings.md (link instead)
- Don't put code comments that could be learnings.md entries

### ✗ Add every little thing

- One-off bugs → code comments, not learnings
- Single-feature implementation → belongs in spec/code, not learnings
- General framework knowledge → not learnings

### ✗ Forget to link

- Learnings with no source (no link to mental model or spec)
- Specs not citing applicable learnings in Assumptions
- Code comments pointing to non-existent docs

### ✗ Let Learnings.md grow unmaintained

- Run `/consolidate-learnings` weekly if ## Drafts has pending entries
- Review quarterly for stale/deprecated entries

---

## Maintenance schedule

| Tier | When to Update | Action |
|---|---|---|
| `private/learnings.md` ## Drafts | When pattern discovered | Append draft finding |
| `private/learnings.md` (promoted) | Weekly via /consolidate-learnings | Promote, deduplicate, prune |
| `private/learnings-index.md` | During /consolidate-learnings | Add/update index entries |
| `.claude/rules/**/*.md` | When learnings graduate | Capture permanent patterns |
| Service mental models | After debugging reveals pattern | Create or enhance |
| Spec assumptions | When creating spec | Document dependencies |
| Code comments | Every PR touching that code | Keep current |

For ownership of each tier, see `.claude/rules/doc-ownership.md`.
