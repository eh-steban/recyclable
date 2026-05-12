---
paths:
  - "private/product/experiments/**/*.md"
  - "private/templates/katas/**/*.md"
---

# Experiment Style

Style rules for kata files (`private/product/experiments/NN-name/kata.md`)
and the kata template (`private/templates/katas/kata.md`). Companion to
`markdown-style.md`.

A kata is the **planning artifact** for a Product Kata experiment. It
encodes the hypothesis, the outcome that would prove or disprove it, and
the per-step gates. It is read at the start of every working session
inside an active experiment, by every agent and reviewer involved. Two
qualities matter: it stays short, and it stays outcome-shaped.

This rule names what belongs in a kata and what does not.

## What belongs in a kata

- **Hypothesis** -- the falsifiable claim the experiment tests.
- **Target condition** -- measurable predicates that, taken together,
  decide success vs failure. Each predicate is independent of how the
  system was built (a reviewer can evaluate it without reading the
  source tree).
- **Current condition** -- quantified baseline ("0 jurisdictions
  supported," not "no jurisdictions yet").
- **Definition of done** -- the demoable end state.
- **First obstacle** -- the single thing blocking progress now.
- **Steps** -- one per week, each describing the **outcome** at end of
  week, plus a pass-condition predicate.
- **Anti-goals** -- what the experiment will not do. Anti-goals may
  name technologies *as boundary constraints* ("no agent framework --
  direct SDK calls"); this is acceptable because it pins the shape of
  what we're testing.
- **Open questions** -- unresolved questions about the *experiment
  itself*, each with a default disposition so work can proceed.

## What does NOT belong in a kata

- **Framework, library, or SDK choices.** "Stand up Next.js App
  Router," "use FastAPI," "wrap the Anthropic SDK" -- all belong in
  the design doc. The kata says what capability exists at end of
  week, not what we built it with.
- **Source-tree paths.** `lib/llm/validator.ts`,
  `backend/src/domain/retrieval/` -- the kata does not pin the file
  layout. The spec may name files as constraints; the kata does not.
- **Architectural patterns.** "SSG with `generateStaticParams`,"
  "persistence-oriented repository," "FastAPI dependency injection"
  -- design doc, not kata.
- **Implementation verbs without an outcome.** "Implement validator,"
  "build retriever," "wire the LLM client" -- name the *result*
  ("the validator hard-blocks unsourced definitive answers"), not
  the activity.
- **Field-level contracts.** Wire schema shapes, request/response
  fields, JSON keys -- spec or contract, not kata.
- **Phase / shard / commit ordering.** Implementation plan, not kata.

## Outcome-shape, by example

### Bad (implementation-shaped)

```text
### Step 2 -- Sonnet user path with grounding validator (target: end of week 2)

- Stand up Next.js App Router app with `/api/ask` route handler.
- Implement: location resolver (Denver-only), material normalizer
  (alias table + Sonnet classifier), structured rule retrieval, Sonnet
  answer composition with strict JSON schema.
- Implement `/recycling/colorado/denver` and
  `/recycling/colorado/denver/[material]` as SSG pages with
  `generateStaticParams` and `revalidate = false`.
- Build minimal `/ask` UI with location input, ask box, answer card.
```

Problems: names a framework (Next.js App Router); names how-to
(`generateStaticParams`, `revalidate = false`); spells "implement /
build / stand up" without saying what's true at end of week.

### Good (outcome-shaped)

```text
### Step 2 -- Sonnet user path with grounding validator (target: end of week 2)

- The user-path retrieval flow is reachable end-to-end: a request
  carrying a location and a question returns a cited answer or a
  grounded refusal.
- Crawlable surfaces exist for the seeded Denver jurisdiction and
  per-material pages, rendered from the same knowledge base the
  assistant cites.
- An interactive `/ask` surface lets a reviewer exercise the loop
  without curl.
- **Pass condition:** smoke-eval suite (8 cases) passes; 100%
  citation coverage on definitive answers; 0 unsourced definitive
  answers; 100% out-of-jurisdiction refusal; p50 < 3 s, p95 < 6 s.
```

The technology stack, the route handler shape, the page-render
strategy, and the file paths are all design-and-spec concerns. The
kata only says what's true at end of week 2.

## Surfaces and gates: the gray area

Routes and CLI commands are **observable surfaces** -- a reviewer can
hit them. Naming them in a kata is fine when they describe what's true
externally:

```text
- `/recycling/colorado/denver/[material]` renders for the seeded
  materials and matches the assistant's disposition.
```

This is outcome-shape. The kata says "this URL exists and returns the
right thing"; the spec says "Next.js App Router, SSG with
`generateStaticParams`, served by Vercel."

The dividing line: external observability is fair game; internal
implementation is not.

## When a kata drifts

If a kata starts naming frameworks or file paths in steps, two
moves restore it:

1. **Replace the verb.** "Implement X" becomes "X exists and does Y."
2. **Push the how down.** Move the framework / pattern / path to the
   design doc for that step. The kata links to the design doc;
   it does not duplicate it.

A kata that re-drifts twice in a row is a signal the team is doing
design-time work in the kata. Pause and write a design doc.

## Cross-references

- `markdown-style.md` -- general markdown discipline.
- `private/templates/katas/kata.md` -- the kata template.
- `private/templates/plans/spec-design.md` -- the design template,
  where the implementation choices the kata excludes are debated.
- `.claude/agents/spec-writer.md` -- the agent that owns kata files
  per `doc-ownership.md`; this rule is one of the standards it
  applies.
- `.claude/commands/new-experiment.md` -- the command that scaffolds
  a new kata from the template.
- `.claude/commands/kata-check.md` -- weekly review of an active
  kata; checks the kata is still outcome-shaped along with progress.
