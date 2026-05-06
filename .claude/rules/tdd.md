---
paths:
  - "backend/**/*.py"
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "frontend/**/*.js"
  - "frontend/**/*.jsx"
---

# Test-Driven Development

How agents write code in this repo: tests first, in nested cycles.
Adapted from Robert Martin, *The Cycles of TDD* (2014). Service
agents (`backend-python`, `frontend-react`) load this on any
implementation task. Quick-fix work (typos, config, one-line
edits) may skip it -- see "Scope" below.

If you are implementing or fixing behavior, this file is the
contract for how that work is sequenced.

## Why this exists

"I followed TDD" is unverifiable in retrospect: a green test
written after the production code looks identical to a green
test written before it. Without the failing-first step, there
is no proof the test exercises the new behavior at all -- it
might pass against the *prior* code too. This file forbids the
hand-wave by requiring a captured red-state record alongside
the green-state record `validation.md` already mandates.

## Scope

- **Required for:** any change that adds, modifies, or removes
  testable behavior. This is the default path for service agent
  work.
- **Skippable for:** quick-fixes per `.claude/CLAUDE.md`
  (typos, config bumps, comment edits, formatting). State the
  skip and the reason, same discipline as `validation.md`.
- **Refactor-only changes** are governed by
  `.claude/rules/refactoring.md` instead -- a refactor preserves
  behavior, so the existing test suite *is* the red-green
  evidence (baseline green, post-change green). No new red step
  is required.

## The four cycles

Each cycle nests inside the one above it. Higher cycles run
less often; lower cycles run continuously inside them.

### 1. Three Laws (seconds)

The innermost loop. Iterate dozens of times per single test:

1. **Write no production code except to pass a failing test.**
2. **Write only enough test code to fail** -- a compilation /
   import / assertion failure all count.
3. **Write only enough production code to pass that failure.**

The discipline is mechanical, not aspirational. If you find
yourself writing production code that no test currently
demands, stop and write the test first.

### 2. Red / Green / Refactor (minutes)

Around each completed unit test:

1. **Red.** Run the test; capture its failure. The captured
   output is required evidence (see "Red-state evidence" below).
2. **Green.** Make it pass with the simplest production change
   that works. Duplication and ugliness are tolerated here --
   this step optimizes for *correctness*, not *structure*.
3. **Refactor.** With the test green, clean the code under
   `.claude/rules/refactoring.md`. Tests stay green throughout;
   if they go red, revert the refactor step, do not edit the
   tests to fit. Refactor scope is "code touched in green,"
   not "the whole file."

### 3. Specific / Generic (~10 minutes)

A directional rule that catches over-fitting:

> **As the tests get more specific, the production code gets
> more generic.**

If a new test forces a production change that handles only
that test (a `case` arm, a hard-coded branch, a one-shot flag),
you are headed the wrong way. Back up and find the more
general shape that subsumes it. Getting "stuck" -- where the
next test demands a near-total rewrite -- is the signal that
recent steps were too specific.

### 4. Architectural check (hourly)

Every hour or so, step out of the per-test loop and check the
shape of what you have built so far against the architectural
constraints that govern it:

- DDD layering (domain pure, no leakage into infra/api) -- see
  `.claude/rules/ddd/architecture.md`.
- Bounded-context boundaries and Ubiquitous Language --
  `.claude/rules/ddd/bounded-contexts.md`.
- Service layout rules in
  `.claude/rules/{backend,frontend}/CLAUDE.md`.
- Invariants in `private/invariants.md`.

If the per-test cycles have drifted away from any of these,
correct course before continuing -- it is cheaper now than at
phase checkpoint.

## Red-state evidence

The new requirement this rule introduces. Each Phase Checkpoint
that contains implementation work records *two* validation
records, both following the four-field shape in
`.claude/rules/validation.md`:

1. **Red record** -- proves the new test failed before the
   production change. Captured by running the test on the
   pre-change tree (or with the change reverted on a scratch
   commit). Exit code must be **non-zero**, and the "Why this
   validates" line names the assertion or symbol that produced
   the failure.
2. **Green record** -- the existing post-change record. Exit
   code zero, output excerpt showing the same test now passing.

A checkpoint with only a green record is incomplete: it does
not prove the test exercises the change. State this explicitly
in `Deferred items` if a red record was genuinely impossible
(e.g., greenfield setup with no prior tree to run against),
same discipline as a skipped baseline in `validation.md`.

### Example red record

```text
**Command:** `cd backend && uv run pytest tests/domain/test_rule_eval.py -k pizza_box`

**Exit code:** `1`

**Output excerpt:**

  tests/domain/test_rule_eval.py::test_pizza_box_rejected FAILED
  >   assert outcome.refused is True
  E   AttributeError: 'RuleOutcome' object has no attribute 'refused'

**Why this validates:** the assertion fails because
`RuleOutcome.refused` does not yet exist; the test is
exercising the not-yet-implemented refusal path on the
food-contamination case (INV-PROD-002).
```

The matching green record paired with this would show exit
code `0` and `test_pizza_box_rejected PASSED` after the
production change.

## Discipline rules

- **No production code without a failing test first.** A
  passing test written after the code is not evidence of TDD;
  it is regression coverage layered on. Both have value, but
  the four-cycle discipline requires the order.
- **Capture the red, do not summarize it.** "I saw it fail"
  without a recorded command + non-zero exit + assertion line
  is the same hand-wave `validation.md` forbids for green runs.
- **One failing test at a time.** If multiple tests are red
  simultaneously, you have left the inner cycle. Drive one to
  green, then write the next.
- **Refactor with the suite green, never red.** A red refactor
  cannot be distinguished from a behavior change.
- **Do not edit tests to fit a refactor or fix.** Tests may
  be updated for renamed internals, but assertions stay
  equivalent or stronger. Loosening an assertion to make a
  failure go away is the same anti-pattern flagged in
  `refactoring.md` and `validation.md`.
- **Hold the discipline under pushback.** If a reviewer
  questions a captured red record, the record is the evidence;
  do not soften it to be agreeable.

## Cross-references

- `.claude/rules/validation.md` -- evidence shape used by both
  red and green records.
- `.claude/rules/refactoring.md` -- governs the refactor step
  of the minute cycle, and the refactor-only path that opts
  out of red-state evidence.
- `.claude/rules/ddd/architecture.md` -- architectural
  constraints checked on the hourly cycle.
- `private/invariants.md` -- invariant IDs cited in
  red-record "Why this validates" lines.
- `private/templates/plans/implementation.md` -- the Checkpoint
  block that consumes the red + green pair.
