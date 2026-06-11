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
  `.claude/docs/refactoring.md` instead -- a refactor preserves
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
   `.claude/docs/refactoring.md`. Tests stay green throughout;
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
  `.claude/docs/ddd/architecture.md`.
- Bounded-context boundaries and Ubiquitous Language --
  `.claude/docs/ddd/bounded-contexts.md`.
- Service layout rules in
  `.claude/rules/{backend,frontend}/CLAUDE.md`.
- Invariants in `private/invariants.md`.

If the per-test cycles have drifted away from any of these,
correct course before continuing -- it is cheaper now than at
phase checkpoint.

## Red-state evidence

The new requirement this rule introduces. Each Phase Checkpoint
that contains implementation work records a **compact TDD
attestation** with four fields:

- **test** -- the fully-qualified test id
  (`path/to/test.py::test_name`).
- **red** -- the one-line failing-assertion message plus exit
  code. This is the proof token: it distinguishes a real
  assertion failure from an import/collection error.
- **green** -- pass confirmation, suite-count delta
  (before -> after), and exit 0.
- **guards** -- the invariant IDs (from `private/invariants.md`)
  the test exercises. This replaces the old "why this validates"
  prose.

Captured by running the test on the pre-change tree (or with
the change reverted on a scratch commit).

A checkpoint missing a red attestation is incomplete. State
this explicitly in `Deferred items` if a red record was
genuinely impossible (e.g., greenfield setup with no prior tree
to run against), same discipline as a skipped baseline in
`validation.md`.

**Auditor note:** an auditor (or `test-auditor` agent) confirms
the named test exists and the red claim is plausible --
specifically that it is an assertion-type failure, not a
collection or import error -- by re-running on the
pre-implementation tree.

### Example compact attestation (service phase)

```text
TDD (per .claude/docs/tdd.md):
- test:   tests/domain/retrieval/test_check_grounding.py::test_uncited_refused
- red:    AssertionError: citations empty on definitive answer (exit 1)
- green:  passed; suite 297 -> 298 (exit 0)
- guards: INV-PROD-001, INV-PROD-004
```

### Refactor-only collapse variant

When a phase ships no new behavioral test (pure refactor,
dependency bump, comment edit), the red step is N/A. Substitute
the compact gate line:

```text
TDD: refactor-only -- no new behavioral test; red record N/A per tdd.md.
  gate: suite green 297 -> 297; coverage 84.1 -> 84.1; assertions intact.
```

The numbers must reflect actual before/after runs, not
placeholders.

## Discipline rules

- **No production code without a failing test first.** A
  passing test written after the code is not evidence of TDD;
  it is regression coverage layered on. Both have value, but
  the four-cycle discipline requires the order.
- **Capture the red, do not summarize it.** "I saw it fail"
  without the test id, a non-zero exit, and the assertion line
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

- `.claude/docs/validation.md` -- evidence shape used by both
  red and green records.
- `.claude/docs/refactoring.md` -- governs the refactor step
  of the minute cycle, and the refactor-only path that opts
  out of red-state evidence.
- `.claude/docs/ddd/architecture.md` -- architectural
  constraints checked on the hourly cycle.
- `private/invariants.md` -- invariant IDs cited in the
  `guards:` field of compact attestations.
- `private/templates/plans/implementation.md` -- the Checkpoint
  block that consumes the compact attestation.
