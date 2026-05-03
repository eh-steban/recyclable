---
paths:
  - "**"
---

# Invariants

Non-negotiable system truths. Agents must preserve them during
implementation, refactoring, review, testing, and release.

Each invariant has an ID. Any implementation plan, review finding,
test audit, or adversarial finding that touches an invariant must
cite the relevant ID. If a change exposes a durable rule with no
matching invariant, propose a new one rather than silently relying
on local judgment.

Invariants are added here, not in agent files or commit messages.
Agents reference IDs; this file owns the meanings.

## How to use this file

- **Implementation:** list the invariants your change touches in the
  plan's `## Invariants touched` section.
- **Refactoring:** preserve every invariant exactly. The refactorer
  is forbidden from changing behavior that an invariant pins down.
- **Review:** the code-reviewer and adversarial-reviewer cite
  invariant IDs on findings. A finding without an ID either describes
  a project convention (lower stakes) or a durable rule that should
  become a new invariant.
- **Tests:** the test-auditor maps every invariant to a positive
  case, an adversarial case, and a failure-mode regression case.
- **Stability:** invariants change rarely. Promotion / removal
  requires owner approval. Mark deprecated entries rather than
  deleting them.

## Numbering

| Prefix | Domain |
| :--- | :--- |
| `INV-PROD-NNN` | Product behavior and grounding contract |
| `INV-AUTH-NNN` | Permission boundaries and access control |
| `INV-DATA-NNN` | Data integrity and persistence rules |
| `INV-LLM-NNN` | LLM call shape, prompt safety, agent boundaries |
| `INV-OPS-NNN` | Deployment, rollback, and operational behavior |

Numbers are assigned monotonically within each prefix. Do not
renumber when entries are deprecated -- leave the gap.

## Per-invariant block format

Each invariant below uses a uniform set of subsections. Keep them in
this order so agents can parse and cite them mechanically:

- **Statement** -- the invariant in one or two sentences.
- **Why it matters** -- the failure cost if it breaks.
- **Violation example** -- a concrete way it would break.
- **Enforcement** -- where the rule is actually pinned (column,
  query, role, code path). For target-state invariants, label the
  enforcement clearly.
- **Required checks** -- tests or static checks that catch a
  violation. For LLM invariants, include the regression fixture.

---

## Product invariants

### INV-PROD-001 -- Every definitive answer cites a source

**Statement:** every definitive assistant answer cites at least one
source. The assistant returns "I cannot verify this" when no
grounded rule supports the claim.

**Why it matters:** the product promise is grounded answers. An
uncited claim is indistinguishable from a hallucination.

**Violation example:** Sonnet returns "Denver accepts plastic bags"
with no citation, or with a citation to a source that does not
contain that claim.

**Enforcement:** response renderer raises when `citations[]` is
empty for a non-refusal answer; refusal path is the only legal
zero-citation response.

**Required checks:** regression case for cited-vs-refusal split;
unit test asserting the renderer rejects an empty `citations[]` on
a definitive answer.

---

### INV-PROD-002 -- Jurisdiction x material is the unit of truth

**Statement:** an answer about (Denver, cardboard) is not derived
from rules in (Boulder, cardboard) or (Denver, paper). Cross-keyed
fallback is forbidden.

**Why it matters:** recycling rules vary by city and material.
Cross-pollination produces confidently wrong answers and breaks
user trust per jurisdiction.

**Violation example:** a retrieval miss for (Denver, cardboard)
silently falls back to (Boulder, cardboard) because both
jurisdictions are in Colorado.

**Enforcement:** retrieval queries filter on the exact tuple; a
miss raises a refusal at the query layer.

**Required checks:** retrieval test asserting exact-tuple match; a
miss returns a refusal, not a sibling-jurisdiction answer.

---

### INV-PROD-003 -- Postgres is the single source of truth

**Statement:** structured rules in Postgres drive both SEO pages
and assistant answers. There is no hand-written content layer that
bypasses ingestion.

**Why it matters:** two sources of truth diverge. The product
asset is the structured rule set; SEO and assistant must read the
same data.

**Violation example:** a jurisdiction page hard-codes "Denver
accepts cardboard" in MDX without a database row backing it.

**Enforcement:** SEO and assistant render paths read from the same
query layer.

**Required checks:** lint check forbidding hard-coded rule text in
route components; integration test asserting the SEO page and the
assistant return matching content for the same tuple.

---

## Permission boundaries

### INV-AUTH-001 -- Worker writes, frontend reads

**Statement:** the Python worker writes rules, sources, and traces.
The Next.js frontend reads only. The Sonnet user path performs no
`INSERT`, `UPDATE`, or `DELETE` on rules, sources, or traces.

**Why it matters:** the user path is on the request hot loop. A
write capability there is both a latency risk and an attack surface
(prompt-injection-driven mutation).

**Violation example:** a route handler on the Sonnet path mutates
a rule based on user input, even indirectly through a "feedback"
endpoint that writes to the same tables.

**Enforcement (target state):** the frontend connects as a
read-only Postgres role; the worker connects as a writer role.
Separate roles are not yet provisioned -- treat this as a target
state until the role split is in place.

**Required checks:** connection-role integration test on each
surface (will fail until the split is provisioned); CI check that
frontend code does not import write-capable repositories.

---

### INV-AUTH-002 -- Only current rules surface to users

**Statement:** SEO pages and assistant answers serve rules with
`superseded_by IS NULL`. A rule is "current" when no other rule
has superseded it.

**Why it matters:** a superseded rule is by definition no longer
correct. Surfacing it produces wrong answers and broken citations.

**Violation example:** a superseded rule reaches a user-facing
surface, or two rules for the same key are both visible because
the filter was missed.

**Enforcement:** every user-path query filters on
`superseded_by IS NULL`. When a separate draft / unpublished state
is introduced, the filter expands -- it does not weaken.

**Required checks:** regression case asserting a superseded rule
is not visible on `/jurisdiction/[slug]/material/[slug]` or
`/ask`.

---

## Data integrity invariants

### INV-DATA-001 -- Every applied rule has provenance

**Statement:** every applied rule has a non-null
`source_document_id` and a non-null extraction trace.

**Why it matters:** rules without provenance cannot be reviewed,
conflict-checked, or revoked. They contradict the grounding
promise at the data layer.

**Violation example:** an extraction with no source document
silently writes a rule and the audit trail loses one row.

**Enforcement:** NOT NULL constraints on both columns; foreign
key from rule to source_document; ingestion code raises when an
extraction has no source.

**Required checks:** ingestion test that an extraction with no
source raises before any database write.

---

### INV-DATA-002 -- One current rule per key tuple

**Statement:** at most one rule with `superseded_by IS NULL` exists
per (`jurisdiction_id`, `material_id`, `effective_date`). Conflicts
are detected at apply time, not after.

**Why it matters:** two current rules for the same key produce
non-deterministic answers and silently override each other.

**Violation example:** two ingestion runs apply rules for the
same key without superseding the prior one; queries return either
row depending on plan.

**Enforcement:** partial unique index on the three columns where
`superseded_by IS NULL`. See `rule_repo.py:54`.

**Required checks:** conflict-detection test in the apply path;
integration test that a duplicate apply either supersedes or
raises.

---

### INV-DATA-003 -- Source URLs are immutable once cited

**Statement:** replacing a URL on an existing `source_document`
row is forbidden. A changed URL requires a new row.

**Why it matters:** a user-visible citation can break or silently
re-point at different content, undermining the grounding promise.

**Violation example:** a typo fix on a URL is applied as an
`UPDATE` to the existing row; old answers' citations now resolve
to different content.

**Enforcement:** application invariant in the `source_document`
repository (and ideally a database trigger) rejecting `UPDATE` on
the URL column.

**Required checks:** regression case for the rewrite-attempt path;
unit test on the repository that the update is refused.

---

## LLM / grounding invariants

### INV-LLM-001 -- Refuse on missing evidence (Sonnet user path)

**Statement:** Sonnet user-path answers refuse with "I cannot
verify this" when no rule matches the queried (jurisdiction,
material) tuple. No fallback to nearby jurisdictions, no
probabilistic guess, no LLM-only synthesis.

**Why it matters:** the refusal path is what makes the product
honest. Silent synthesis produces confidently wrong answers under
exactly the conditions where users are most likely to trust them
(specific city, specific material, no obvious source).

**Violation example:** a query for (Denver, plastic bags) returns
a synthesized "probably accepted" answer when the database holds
no rule for that tuple.

**Enforcement:** the route handler refuses to render an answer if
grounding evidence is absent. Client-side validation is UX, not
security.

**Required checks:** regression case where the database holds no
rule for the queried tuple; assertion that the response is a
refusal, not a hedged or synthesized answer.

---

### INV-LLM-002 -- Citations are not synthesized

**Statement:** every citation rendered to a user links to a
`source_document.url` that was the actual basis for the cited
rule's extraction. The model does not author citation URLs.

**Why it matters:** a fabricated citation is a worse failure than
no citation -- it gives a hallucination the appearance of
verification.

**Violation example:** a citation URL is copied from a different
source, or invented to look plausible, or points to a page that
does not contain the cited claim.

**Enforcement:** citations are joined from the rule's
`source_document` row at render time, not produced by the model.

**Required checks:** regression case asserting every citation in
a response resolves to a row in `source_document` whose
extraction_trace produced the cited rule.

---

### INV-LLM-003 -- Opus cannot write to production rules directly

**Statement:** the Opus research loop has no direct write
capability against production rules tables. Applied ingestion
changes pass through a review-and-apply gate.

**Why it matters:** prompt injection on a fetched page or in a
crafted source can coerce an agent into writing a rule the
operator never reviewed. The gate is what makes ingestion
auditable.

**Violation example:** the agent is given a tool that performs
`INSERT INTO rules` and a poisoned source document triggers it.

**Enforcement:** the agent's tool schema exposes read tools and
proposal tools. Apply is a separate code path the agent does not
control.

**Required checks:** integration test that the apply path is the
only writer; static check that the agent's tool list does not
include direct writers.

---

### INV-LLM-004 -- User input does not control the system prompt

**Statement:** user input on the Sonnet path is delimited from
the system prompt and never concatenated as instructions. The
system prompt is not user-controllable.

**Why it matters:** direct prompt injection is the cheapest LLM
attack. A concatenation that lets a user say "ignore previous
instructions" is the textbook failure.

**Violation example:** the system prompt and user message are
joined with simple string concatenation, with no role separation
or delimiter; a crafted question overrides grounding.

**Enforcement:** the SDK's role-separated message API is used;
user input is wrapped in a delimited block; system-prompt content
never includes user-provided substrings.

**Required checks:** regression case for known prompt-injection
payloads; assertion that the assistant refuses or ignores the
injected instruction and still cites a real source.

---

### INV-LLM-005 -- Sonnet on user path, Opus on research path

**Statement:** Sonnet runs on the synchronous user path; Opus
runs on the offline research / ingestion loop. The user path
never invokes Opus.

**Why it matters:** Opus on the user path inflates latency,
cost, and variance, and exposes the user surface to agentic-loop
failure modes that are only acceptable behind the review-and-
apply gate.

**Violation example:** a "deep research" route on the user-facing
app calls Opus directly because retrieval was thin and a richer
answer was tempting.

**Enforcement:** model selection is a constant per surface, not a
per-request choice. Frontend code does not reference Opus model
IDs.

**Required checks:** static check that frontend / user-path code
does not reference Opus model IDs; regression case asserting the
user path's model is Sonnet for both retrieval and refusal flows.

---

## Operational invariants

### INV-OPS-001 -- Worker failures do not block the user path

**Statement:** an ingestion failure or worker crash does not
take the assistant offline. The Sonnet path reads from the
last-good Postgres state.

**Why it matters:** the worker is allowed to fail loudly
(ingestion is auditable, retried, reviewed). The user path is
not.

**Violation example:** a deploy couples worker readiness to the
user path's health check; a failed scrape job takes `/ask` down.

**Enforcement:** worker and frontend share a database but not a
process. The user path's health check does not depend on worker
liveness.

**Required checks:** integration test that a worker crash does
not flip the frontend's readiness probe; deploy test that the
two services restart independently.

---

### INV-OPS-002 -- Ingestion is idempotent at the source URL

**Statement:** re-ingesting the same URL upserts the existing
`source_document` row and does not duplicate rules or create
orphan extraction traces.

**Why it matters:** re-running a job inflates the ruleset; dedupe
drift produces conflicting "duplicate" rows that violate
INV-DATA-002.

**Violation example:** a retried ingestion creates a second
`source_document` row for the same URL; both rows have
extracted rules; the apply path now sees two sources for the
same fact.

**Enforcement:** upsert keyed on `source_document.url`. When
`content_hash` is added to `source_document`, strengthen the key
to `(url, content_hash)` so a re-fetch with changed content
versions cleanly rather than overwriting silently. Treat the
content_hash strengthening as a target state.

**Required checks:** integration test re-running ingestion on
the same URL twice; assertion that no duplicate rules or
extraction traces are produced.

---

### INV-OPS-003 -- Migrations are forward-and-backward safe

**Statement:** migrations are safe under live traffic. Deploys
do not assume a maintenance window.

**Why it matters:** a migration that requires offline time
either blocks a release or breaks the user path mid-deploy.

**Violation example:** a migration drops a column in the same
release as the code change that stops writing it; in-flight
requests on the old version error out.

**Enforcement:** expand-then-contract pattern. Schema-only and
backfill changes ship before code changes that depend on them;
column drops ship after the code that stopped using them.

**Required checks:** migration review checklist enforces the
pattern; CI guard that flags `DROP COLUMN` and `DROP TABLE`
migrations for human approval.
