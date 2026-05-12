---
paths:
  - "backend/tests/regression/**/*.py"
  - "frontend/tests/regression/**/*.ts"
  - "private/specs/regression-cases/**/*"
---

# Regression Suite Conventions

The regression suite (the spec calls these "evals") is the single quality
gate every change must clear. It catches answer correctness drift, citation
gaps, and confidence-grading drift. Without a passing suite, no change
ships.

## Three levels of checks

Per the project's interview-prep frame:

1. **Final answer quality** -- correct disposition, clear next step,
   source citation present.
2. **Trajectory / tool correctness** -- right tools called, right
   jurisdiction filter applied, retrieval set contains the expected rule.
3. **Single-step behavior** -- material normalization picks the right
   canonical material, location resolver returns the right jurisdiction,
   validator catches missing citations.

A single test case may assert across multiple levels. Keep assertions
explicit so a failure points at which level broke.

## Case definition

```ts
type RegressionCase = {
  id: string;
  query: string;
  jurisdiction: string;
  expected: {
    material_slug: string;
    short_answer: 'yes' | 'no' | 'conditional' | 'unknown';
    disposition:
      | 'curbside_recycle'
      | 'dropoff'
      | 'compost'
      | 'landfill'
      | 'hazardous_waste'
      | 'donate'
      | 'unknown';
    must_cite_source: boolean;
    refusal_required: boolean;       // true for unsupported jurisdictions
  };
  notes?: string;
};
```

Cases live in `backend/tests/regression/cases/` as JSON or YAML, one file
per jurisdiction.

## Required cases (Day 1)

- "Can I recycle glass bottles in Denver?" → yes, curbside, citation
  required.
- "Can I recycle wine glasses in Denver?" → no, distinguished from glass
  bottles.
- "Where can I recycle plastic bags in Denver?" → not curbside; suggest
  verifying drop-off.
- "Can I recycle pizza boxes in Denver?" → conditional on cleanliness if
  source supports it; otherwise unknown.
- "What do I do with propane tanks?" → not curbside; hazardous handling.
- "Can I recycle batteries?" → ambiguous → clarifying question required.
- "I live in Aurora, can I recycle glass?" → refusal_required = true (no
  Aurora coverage in 01).
- "Where can I recycle hard-to-recycle materials in Denver?" →
  directory/facility source or limitation.

## Metrics

Prototype:

- Answer correctness rate (cases passing level 1).
- Citation coverage (% of definitive answers carrying a source).
- Unsupported answer rate (definitive answer with no retrieval evidence --
  target 0).
- Clarifying-question precision (% of clarifying questions that are
  actually warranted).
- Retrieval hit rate (% of cases where the expected rule was in the
  retrieved set).
- Average latency (p50, p95).
- Cache hit rate on stable-prefix calls.

Product (post-launch):

- Successful task completion (user reaches an answer they act on).
- "Wrong/outdated" feedback rate.
- Repeat usage by household.

## Running

```bash
# Backend (full suite)
cd backend && pytest tests/regression -v

# Single jurisdiction
cd backend && pytest tests/regression -k denver

# CI mode (no LLM calls; verifies fixtures and validator only)
cd backend && pytest tests/regression --no-llm

# Against deployed instance
cd backend && pytest tests/regression \
  --target https://recyclable.vercel.app
```

## Cost controls

LLM calls in the regression suite cost real money. Guardrails:

- Default: run only changed-jurisdiction cases on local pre-commit.
- Full suite: required on PR, runs in CI with a budget-capped API key.
- Cache prompt prefixes between cases in the same run.
- A `--no-llm` mode runs everything except the model call (validator,
  retrieval, schema checks) -- catches most regressions for free.

## Promotion rules

- A case may only be added if it tests a behavior we want to preserve.
  "Aspirational" cases that fail today belong in a separate `pending/`
  directory until the behavior ships.
- A case may only be removed if the behavior it tests has been deliberately
  retired (with a learnings entry explaining why).
- Editing an expected value requires a kata link or learnings citation
  explaining the change.
