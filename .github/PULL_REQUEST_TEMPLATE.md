## Summary

[1-3 sentences on what changed and why. Link the implementation /
fix / refactor plan in `private/plans/`.]

## Invariants touched

> List the IDs from `.claude/rules/invariants.md` this change
> preserves, alters, or proposes. A change with zero invariant
> impact should say so explicitly -- "no invariants touched" --
> not leave the section blank.

- `[INV-XXX-NNN]` -- [how this change relates: preserved /
  enforced / proposed]

## Validation Evidence

> Shape and discipline live in `.claude/docs/validation.md`. Paste
> the four-field record(s) from the plan's Checkpoint(s) -- do not
> summarize as "tests pass."

**Command:** `[exact bash invocation]`

**Exit code:** `[integer]`

**Output excerpt:**

```text
[relevant lines]
```

**Why this validates:** [cite invariant IDs, the changed behavior,
and the error path or regression case exercised.]

## Agent Run Log

> One block per agent. Mark `Required?` `yes` if the change falls
> in that agent's trigger surface (see
> `private/plans/implementation/agentic-dev-enforcement.md` Phase 5
> for the trigger matrix). Mark `skipped (reason)` under Result
> when an agent was deliberately not run.

### implementation

- **Required?** yes
- **Purpose:** build change
- **Inputs used:** plan / spec / invariants
- **Commands run:** [fill in]
- **Result:** [fill in]
- **Follow-ups:** [fill in]

### refactorer

- **Required?** yes / no
- **Purpose:** preserve behavior, reduce complexity
- **Inputs used:** diff + invariants + validation evidence
- **Commands run:** [fill in]
- **Result:** [fill in]
- **Follow-ups:** [fill in]

### code-reviewer

- **Required?** yes
- **Purpose:** broad correctness, security, convention review
- **Inputs used:** diff + invariants + validation evidence
- **Commands run:** [fill in]
- **Result:** [fill in]
- **Follow-ups:** [fill in]

### adversarial-reviewer

- **Required?** yes / no
- **Purpose:** attack assumptions and invariants
- **Inputs used:** diff + invariants + reviewer output
- **Commands run:** [fill in]
- **Result:** [fill in]
- **Follow-ups:** [fill in]

### test-auditor

- **Required?** release / monthly / risky
- **Purpose:** audit invariant test coverage
- **Inputs used:** tests + invariants
- **Commands run:** [fill in]
- **Result:** [fill in]
- **Follow-ups:** [fill in]

## Merge Readiness

- [ ] Invariants touched are listed by ID (or "none" stated
      explicitly).
- [ ] Validation Evidence includes exact commands, exit codes, and
      output excerpts -- "tests pass" alone is rejected.
- [ ] Refactorer ran or was explicitly skipped with reason.
- [ ] Code-reviewer ran.
- [ ] Adversarial-reviewer ran for changes touching auth, user
      data, LLM grounding / refusal, migrations, external input,
      background jobs, or destructive operations -- or was
      explicitly skipped with reason.
- [ ] Test-auditor ran for releases, critical-invariant changes,
      or test-heavy changes -- or was explicitly skipped with
      reason.
- [ ] CI passed.
- [ ] Follow-ups captured in a tracked issue, plan, or
      `private/product/strategy/parking-lot.md`.

## Test plan

- [ ] [What you verified manually, beyond CI]
- [ ] [Edge cases or regression scenarios checked]
