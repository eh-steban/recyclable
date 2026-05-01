---
name: context-audit
description: This skill should be used when the user asks to "audit project
  files", "check context health", "review .claude configuration", "scan for
  stale docs", or mentions "context audit" or "project memory optimization".
  Scans all .claude/ files and private/ documentation files, evaluates quality
  against type-specific rubrics, detects cross-file issues, and produces a
  categorized report with ownership-aware recommendations. This skill can write
  to spec-writer-owned files after approval.
---

Audit, evaluate, and improve all project configuration and documentation files
-- not just CLAUDE.md files, but agents, rules, commands, skills, and
knowledge management files.

## Scan scope

Discover all auditable files using these patterns:

```text
# CLAUDE.md index files
find . -name "CLAUDE.md" -not -path "*/node_modules/*"

# Agent definitions
find .claude/agents -name "*.md"

# Slash commands
find .claude/commands -name "*.md"

# Skills
find .claude/skills -name "SKILL.md"

# Rules and mental models
find .claude/rules -name "*.md"

# Knowledge management
.claude/knowledge-management.md

# Private documentation (if accessible)
find private -name "*.md" -not -path "*/experiments/*" 2>/dev/null
```

Classify each discovered file into one of these types:

- `claude-md` -- CLAUDE.md index/pointer files
- `agent` -- .claude/agents/*.md definitions
- `command` -- .claude/commands/*.md slash commands
- `skill` -- .claude/skills/**/SKILL.md packages
- `rule` -- .claude/rules/**/*.md standards and mental models
- `knowledge` -- knowledge-management.md, learnings.md, learnings-index.md

## Audit workflow

### Phase 1: Individual file audit

For each file, load the appropriate rubric from references/:

- `claude-md` → See [references/quality-criteria-claude-md.md][qc-claude-md]
- `agent` → See [references/quality-criteria-agents.md][qc-agents]
- `command` → See [references/quality-criteria-commands.md][qc-commands]
- `skill` → See [references/quality-criteria-skills.md][qc-skills]
- `rule` → See [references/quality-criteria-rules.md][qc-rules]
- `knowledge` → See [references/quality-criteria-knowledge.md][qc-knowledge]

[qc-claude-md]: references/quality-criteria-claude-md.md
[qc-agents]: references/quality-criteria-agents.md
[qc-commands]: references/quality-criteria-commands.md
[qc-skills]: references/quality-criteria-skills.md
[qc-rules]: references/quality-criteria-rules.md
[qc-knowledge]: references/quality-criteria-knowledge.md

Score each file against the rubric. Scores are per-criterion, not an overall
number.

### Phase 2: Cross-file analysis

After individual audits, perform these cross-file checks:

**Duplication detection:**

- Identify instructions, rules, or knowledge that appears verbatim (or
  near-verbatim) in multiple files. Flag which file should be the canonical
  source and which should use pointers.
- Common pattern to catch: root CLAUDE.md duplicating content from rules/
  files instead of pointing to them.

**Orphaned pointers:**

- Every file path reference (e.g., `.claude/rules/backend/testing.md`) must
  resolve to a real file. Flag dead links.
- Every anchor reference in learnings-index.md (e.g.,
  `learnings.md#some-anchor`) must resolve to an actual heading in the target
  file.

**Ownership violations:**

- Check the ownership map: See [references/ownership-map.md][ownership-map]
- Flag if a service agent's recent git history shows writes to files it
  shouldn't own.

[ownership-map]: references/ownership-map.md

**Budget overruns:**

- Check each file against its budget:
  See [references/context-budgets.md][context-budgets]
- Estimate token count (lines × ~10 tokens/line as rough heuristic).

[context-budgets]: references/context-budgets.md

**Consistency checks:**

- Agent definitions: do all service agents have matching section structures?
  (Before Starting Work, Testing, Observability, Shared File Rules)
- Rules files: do all services have the same set of rule types?
  (mental model, testing, observability -- flag missing ones)
- Commands: do file path references use `private/` paths consistently?

### Phase 3: Report

ALWAYS output the report BEFORE making any changes.

```text
## Project Health Report

### Summary
- Files scanned: X
- Files passing: X
- Files needing updates: X
- Cross-file issues found: X

### SPEC-WRITER ACTIONABLE (can apply after approval)
Changes to files owned by spec-writer: rules, learnings, knowledge-management.

For each finding:
- [File path]: [Issue] → [Proposed change]

### OWNER REVIEW NEEDED (flagged, not auto-applied)
Changes to files owned by the project owner: agents, commands, skills,
CLAUDE.md. Customize this section label in your project's copy of this skill.

For each finding:
- [File path]: [Issue] → [Recommendation]

### CROSS-FILE ISSUES
- [Duplication/Orphan/Violation]: [Details]

### FILE-BY-FILE DETAIL
Per-file scores and criterion-level notes (collapsible in long reports).
```

### Phase 4: Apply

After the project owner approves:

- Apply changes to spec-writer-owned files using Edit tool
- For owner-only files, output the recommended diffs but do NOT apply
- Preserve existing content structure -- targeted edits only, not rewrites
