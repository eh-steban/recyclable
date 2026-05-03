---
allowed-tools: Read, Glob, Grep, Bash
description: Audit Claude process files for broken references and missing enforcement.
---

# Process Doctor

Audit `.claude/` and repository workflow files for broken references,
process drift, and missing enforcement. Read-only -- this command reports
findings and a patch plan; it does not modify files.

Use this command:

- After adding, renaming, or removing any agent, skill, command, or rule
- After `/consolidate-learnings` if any rules or agent files were
  touched (`/consolidate-learnings` delegates reference-integrity
  checks here rather than duplicating them)
- Before starting a new experiment or spec
- When agentic-dev-enforcement-plan phases land, to verify wiring
- Periodically (monthly) to detect drift

## Inputs

- `.claude/` tree
- `.gitignore`
- `.github/workflows/` (if present)
- `.github/PULL_REQUEST_TEMPLATE.md` (if present)
- `agentic-dev-enforcement-plan.md` (for current phase expectations)

## Checks

Run each check below. For every miss, record an entry under the matching
severity heading.

### Reference integrity

- Every agent name referenced in `.claude/CLAUDE.md`, `.claude/commands/*.md`,
  and `.claude/rules/**/*.md` resolves to a file in `.claude/agents/`.
- Every command name referenced (e.g. `/kata-check`, `/quick-fix`) resolves
  to a file in `.claude/commands/`.
- Every rule file referenced by path (e.g.
  `.claude/rules/backend/CLAUDE.md`) exists.
- Every skill referenced resolves to `.claude/skills/<name>/SKILL.md`.
- `paths:` glob lists in rule frontmatter point at directories or files
  that exist. Stale globs cause agents to load the wrong rules or miss
  relevant ones, so flag mismatches as WARNING.

### Ignore hygiene

- `.gitignore` is non-empty.
- `.gitignore` covers: `.env*`, secrets, local config, build output,
  cache directories, `.mcp.json`, `node_modules`, `__pycache__`,
  `.venv`, `dist`, `build`, `.next`, `.cache`.

### Enforcement scaffolding (per agentic-dev-enforcement-plan)

- `.claude/rules/invariants.md` exists.
- `.claude/agents/refactorer.md`, `code-reviewer.md`,
  `adversarial-reviewer.md`, and `test-auditor.md` each contain a
  reference to `.claude/rules/invariants.md`.
- Implementation, fix, and refactor plan templates include a
  `Behavior Preservation Contract` block.
- Plan templates and the PR template include a `Validation Evidence`
  block requiring exact command, exit code, and output excerpt.
- `.github/PULL_REQUEST_TEMPLATE.md` includes `Agent Run Log` and
  `Merge Readiness` sections.
- `.github/workflows/quality-gate.yml` exists (parked until CI lands;
  flag as SUGGESTION while parked).

### Agent wiring

- `code-reviewer` recommends `adversarial-reviewer` for changes touching
  auth, user data, LLM grounding/refusal, migrations, external input,
  background jobs, or destructive operations.
- `refactorer` requires Behavior Preservation Contract baseline before
  refactoring.
- `test-auditor` includes an `Invariant Coverage Matrix` section.

### Documentation ownership

- Every file in `.claude/agents/`, `.claude/commands/`, and
  `.claude/skills/**/SKILL.md` is listed as owner-only in
  `.claude/rules/doc-ownership.md` (or the table acknowledges the
  pattern).
- `paths:` frontmatter on rule files matches the directory tree.

### Honesty and stop conditions

- `.claude/CLAUDE.md` "Honesty and stop conditions" section is present.
- Each agent file inherits or restates the relevant honesty rules.

## Useful commands

```bash
# Reference integrity sweep
agents='refactorer|code-reviewer|adversarial-reviewer|test-auditor'
agents="$agents|backend-python|frontend-react|spec-writer"
agents="$agents|e2e-testing|e2e-playwright"
grep -RIn --include='*.md' -E "\b($agents)\b" .claude
grep -RIn --include='*.md' \
  -E '\.claude/(agents|commands|rules|skills)/[A-Za-z0-9_./-]+' .claude

# Stale path detection
grep -RIn --include='*.md' \
  -E '(parser/src|e2e-playwright|mental-model)' .claude

# Ignore hygiene
test -s .gitignore && echo "ok" || echo "empty"
ignore_re='^(\.env|\.mcp\.json|node_modules|__pycache__'
ignore_re="$ignore_re|\.venv|dist|build|\.next|\.cache)"
grep -E "$ignore_re" .gitignore

# Enforcement scaffolding presence
test -f .claude/rules/invariants.md && echo "ok" || echo "missing"
test -f .github/PULL_REQUEST_TEMPLATE.md && echo "ok" || echo "missing"
test -f .github/workflows/quality-gate.yml && echo "ok" || echo "missing"
```

## Output format

CRITICAL

- `[Issue]`: `[Evidence path or grep hit]` -- Fix: `[concrete edit]`

WARNING

- `[Issue]`: `[Evidence path or grep hit]` -- Fix: `[concrete edit]`

SUGGESTION

- `[Issue]`: `[Evidence path or grep hit]` -- Fix: `[concrete edit]`

PATCH PLAN

Ordered list of edits to make, smallest blast radius first. Each entry
names the file, the change, and which check it resolves.

NON-ISSUES CHECKED

- `[Area]`: `[Why no issue was found]`

## Severity guide

- **CRITICAL**: a referenced agent/command/rule/skill does not exist; an
  ignore pattern is missing for a known secret-bearing file; an
  enforcement file required by an already-landed phase is missing.
- **WARNING**: stale references that still resolve but are misleading;
  drift between docs (e.g. `paths:` glob does not match actual tree);
  enforcement file present but not wired into required agents.
- **SUGGESTION**: enforcement scaffolding for phases not yet landed;
  ownership table out of date; cosmetic process inconsistencies.

If audit turns up no concrete findings, say so directly. Empty findings
are valid output -- do not pad to look thorough.
