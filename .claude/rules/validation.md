---
paths:
  - "backend/**/*.py"
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.js"
  - "frontend/**/*.jsx"
  - "private/plans/**"
---

# Validation evidence

How agents prove a change works. This file defines the **shape** of
a validation evidence record and the **discipline** for filling it
in. Plans, agent outputs, and PR descriptions instantiate this shape
with their own concrete content -- they do not duplicate the
discipline section.

If you are writing a plan or agent output that claims a change is
validated, this file is the contract.

## Why this exists

"Tests pass" is a claim, not evidence. An agent that summarizes
validation as "tests pass" cannot be distinguished from an agent
that did not run them. Pasting the exact command, exit code, and a
relevant output excerpt makes the claim falsifiable. This file
forbids the hand-wave.

## Required fields

Every validation evidence record carries four fields, in this order:

1. **Command** -- the exact bash invocation. No paraphrase. No
   alias. Copy-paste reproducible.
2. **Exit code** -- the integer the runner returned. `0` means
   success; any non-zero value is a failure that must be addressed
   before the record counts as evidence.
3. **Output excerpt** -- a short snippet of the runner's output
   that proves the command did what it claims (test count, key
   assertion line, error path message). Truncate to the relevant
   lines; do not paste 500-line dumps.
4. **Why this validates** -- one or two sentences naming what the
   evidence proves. Cite invariant IDs from
   `private/invariants.md` when applicable, the changed
   behavior, and the error path or regression case the run
   exercised.

A record missing any field is not evidence; it is a claim.

## Discipline rules

- **Never summarize as "tests pass."** Paste the four fields.
  "Tests pass" without command + exit code is an unverifiable
  assertion.
- **If validation was not run, say so directly.** State which
  command was not run and why. A skipped step with a written reason
  is honest; a skipped step without one is dishonest.
- **Ambiguous output is not success.** If the runner's exit code is
  zero but the output shows skipped tests, retried failures, or
  flaky reruns, the record must say so under "Why this validates."
- **Re-run after fix-ups.** If you ran the suite, then made an
  edit (formatting, comment, anything), the prior evidence is
  stale. Re-run before claiming the change is validated.
- **Pre-existing failures do not count as evidence for this
  change.** If the suite was red before your change for unrelated
  reasons, name those failures and exclude them from the record;
  do not let a green run on a different scope stand in.
- **Skipped baseline requires a written reason.** If a plan
  declares it does not need a baseline run (e.g., the change is
  greenfield with no prior behavior to compare against), state
  that reason in the plan's validation block; do not omit the
  baseline silently.
- **Hold the discipline under pushback.** Do not soften an
  ambiguous result to look thorough. If a reviewer pushes back
  without new evidence, hold the finding.

## Where this is required

- **Implementation plan phases** -- every Checkpoint at phase end.
  See `private/templates/plans/implementation.md` "## Phase N --
  Checkpoint." The Checkpoint's slots match this shape.
- **Fix plans** -- the Verification block. See
  `private/templates/plans/fix.md` "## Verification."
- **Refactor plans** -- baseline + post-change records, both using
  this shape. See `.claude/rules/refactoring.md` for the
  refactor-specific framing.
- **Agent outputs** -- any agent that runs validation as part of
  its work emits a record in this shape (refactorer, code-reviewer
  for verified findings, test-auditor for measured metrics).
- **PR descriptions / merge checklists** -- the merge gate cites
  the records from the plan. Phase 5 of the agentic-dev-enforcement
  plan defines the PR template that consumes this shape.

## Example

```text
**Command:** `cd backend && uv run pytest tests/regression -k denver_cardboard`

**Exit code:** `0`

**Output excerpt:**

  tests/regression/test_denver_cardboard.py::test_accepted PASSED
  tests/regression/test_denver_cardboard.py::test_pizza_box_rejected PASSED
  ============================== 2 passed in 0.84s ==============================

**Why this validates:** exercises INV-PROD-001 (cited-or-refusal)
and INV-PROD-002 (jurisdiction x material exact match) for the
Denver cardboard tuple after the seed change; pizza box case
covers the food-contamination negative path.
```

## Cross-references

- `private/invariants.md` -- invariant IDs cited in "Why
  this validates"
- `.claude/rules/refactoring.md` -- refactor-specific use of this
  shape (baseline + post-change records)
- `private/templates/plans/implementation.md` and `fix.md` --
  templates whose Checkpoint / Verification slots match this
  shape
