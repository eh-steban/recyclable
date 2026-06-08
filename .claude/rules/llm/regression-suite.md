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

The suite has two tiers with different cost profiles.

**Offline tier (default -- free, no key required)**

```bash
# All regression tests (offline fake-LLM path)
docker compose exec app-backend pytest tests/regression -v

# Single jurisdiction filter
docker compose exec app-backend pytest tests/regression -k denver
```

The default `pytest` run is fully offline. `test_ask_offline.py` exercises
the complete `/ask` pipeline -- retrieval, grounding, audit write, wire
mapping -- using `FakeAnthropicClient` (`tests/_fakes/anthropic_client.py`)
injected via FastAPI dependency override. No API key, no network, no cost.
The out-of-jurisdiction refusal path and the grounding-validator rejection
path both have deterministic hard assertions here.

**Live eval tier (opt-in -- billable Sonnet + Haiku calls)**

```bash
RUN_LIVE_EVALS=1 ANTHROPIC_API_KEY=<key> \
  docker compose exec app-backend pytest tests/regression/test_smoke_eval.py -v
```

The live smoke eval (`test_smoke_eval.py`) is gated by the `RUN_LIVE_EVALS`
env var. Without it (or without `ANTHROPIC_API_KEY`) the module skips at
collection time. When enabled, it drives 8 cases from
`tests/regression/cases/denver-easy.yaml` against real Sonnet + Haiku:

- **6 Denver cases** (3 accepted, 2 rejected, 1 conditional) are marked
  `xfail(strict=False)` because the live normalizer fallback and LLM
  verdict are nondeterministic. These are non-gating -- they may XPASS or
  XFAIL run to run.
- **2 out-of-jurisdiction cases** (Aurora, Boulder) carry an explicit
  `location` field in the YAML. These short-circuit before the model and
  are hard assertions.

## Cost controls

LLM calls in the live eval tier cost real money. Guardrails:

- The offline tier runs by default and is completely free. Deterministic
  coverage of prompt composition, grounding, and refusal lives there.
- The live eval tier is opt-in behind `RUN_LIVE_EVALS=1`. Run it before
  promoting a change that touches the retrieval prompt, grounding
  validator, or normalizer.
- Cache prompt prefixes between cases in the same run.

There is no CI test gate today. `.github/workflows/` contains only
`commit-msg.yml` and `gitleaks.yml`. A CI job running the offline tier
is the intended next step, but it does not exist yet -- do not treat
"runs in CI" claims as current fact.

## Latency targets

The spec targets p50 < 3 s / p95 < 6 s end-to-end. These are measured in
the live eval only. The `test_latency_aggregate` test asserts them but is
also marked `xfail(strict=False)` (it depends on all 8 Denver cases
completing) and therefore non-gating.

As of 2026-06-08, measured cold-cache p50 = 4231 ms / p95 = 7467 ms --
both targets are NOT met. Latency optimization is deferred; see
`private/CONTEXT.md` backlog. The latency assertion stays non-gating until
the work is addressed.

## Promotion rules

- A case may only be added if it tests a behavior we want to preserve.
  "Aspirational" cases that fail today belong in a separate `pending/`
  directory until the behavior ships.
- A case may only be removed if the behavior it tests has been deliberately
  retired (with a learnings entry explaining why).
- Editing an expected value requires a kata link or learnings citation
  explaining the change.
