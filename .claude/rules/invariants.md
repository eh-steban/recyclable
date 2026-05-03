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
- **Tests:** the test-auditor's `Invariant Coverage Matrix` maps
  every invariant to a positive case, an adversarial case, and a
  failure-mode regression case.
- **Stability:** invariants change rarely. Promotion / removal of
  an invariant requires owner approval. Mark deprecated entries
  rather than deleting them.

## Numbering

| Prefix | Domain |
|---|---|
| `INV-PROD-NNN` | Product behavior and grounding contract |
| `INV-AUTH-NNN` | Permission boundaries and access control |
| `INV-DATA-NNN` | Data integrity and persistence rules |
| `INV-LLM-NNN` | LLM call shape, prompt safety, agent boundaries |
| `INV-OPS-NNN` | Deployment, rollback, and operational behavior |

Numbers are assigned monotonically within each prefix. Do not
renumber when entries are deprecated -- leave the gap.

---

## Product invariants

| ID | Invariant | Why it matters | Violation example | Required checks |
|---|---|---|---|---|
| INV-PROD-001 | Every definitive assistant answer cites at least one source. The assistant returns "I cannot verify this" when no grounded rule supports the claim. | The product promise is grounded answers. An uncited claim is indistinguishable from a hallucination. | Sonnet returns "Denver accepts plastic bags" with no citation, or with a citation to a source that does not contain that claim. | Regression case for cited-vs-refusal split; CI check that response renderer raises when `citations[]` is empty for a non-refusal answer. |
| INV-PROD-002 | Jurisdiction x material is the unit of truth. An answer about (Denver, cardboard) is not derived from rules in (Boulder, cardboard) or (Denver, paper). | Recycling rules vary by city and material. Cross-pollination produces confidently wrong answers and breaks user trust per jurisdiction. | A retrieval miss for (Denver, cardboard) silently falls back to (Boulder, cardboard) because both jurisdictions are in Colorado. | Retrieval tests must assert exact jurisdiction match; a miss raises refusal, not a fallback. |
| INV-PROD-003 | Postgres is the single source of truth for rules. There is no hand-written content layer that bypasses ingestion. | Two sources of truth diverge. The product asset is the structured rule set; SEO pages and assistant answers must read the same data. | A jurisdiction page hard-codes "Denver accepts cardboard" in MDX without a database row backing it. | SEO and assistant render paths read from the same query layer. Lint check forbids hard-coded rule text in route components. |

## Permission boundaries

| ID | Boundary | Allowed | Forbidden | Enforcement point | Required tests |
|---|---|---|---|---|---|
| INV-AUTH-001 | Worker writes, frontend reads. | The Python worker writes rules, sources, traces. The Next.js frontend reads only. | The Sonnet user path performs `INSERT`, `UPDATE`, or `DELETE` on rules, sources, or traces. | Database role: frontend connects as a read-only role; worker connects as a writer role. | Connection-role integration test on each surface (will fail until separate roles are actually provisioned -- target state); CI check that frontend code does not import write-capable repositories. |
| INV-AUTH-002 | Only current rules surface to users. A rule is "current" when `superseded_by IS NULL`. | SEO pages and assistant answers serve rules with `superseded_by IS NULL`. | A superseded rule reaches a user-facing surface, or two rules for the same key are both visible. | Query layer: every user-path read filters on `superseded_by IS NULL`. When draft / unpublished state is introduced as a separate column, the same invariant applies -- expand the filter, do not weaken it. | Regression case asserting a superseded rule is not visible on `/jurisdiction/[slug]/material/[slug]` or `/ask`. |

## Data integrity invariants

| ID | Invariant | Failure mode | Required DB / API checks |
|---|---|---|---|
| INV-DATA-001 | Every applied rule has a non-null `source_document_id` and a non-null extraction trace. | Rules without provenance cannot be reviewed, conflict-checked, or revoked. | NOT NULL constraints on both columns; foreign key from rule to source_document; ingestion test that an extraction with no source raises before write. |
| INV-DATA-002 | At most one current rule exists per (`jurisdiction_id`, `material_id`, `effective_date`). "Current" means `superseded_by IS NULL`. Conflicts are detected at apply time, not after. | Two current rules for the same key produce non-deterministic answers and silently override each other. | Partial unique index on the three columns where `superseded_by IS NULL` (matches `rule_repo.py:54`); conflict-detection test in the apply path. |
| INV-DATA-003 | Source URLs are immutable once cited. Replacing a URL on an existing source_document row is forbidden; create a new row. | A user-visible citation can break or silently re-point at different content, undermining grounding. | Database trigger or application invariant rejecting `UPDATE` on `source_document.url`; regression case for the rewrite-attempt path. |

## LLM / grounding invariants

| ID | Invariant | Refusal or downgrade rule | Regression fixture |
|---|---|---|---|
| INV-LLM-001 | Sonnet user-path answers refuse with "I cannot verify this" when no rule matches the queried (jurisdiction, material) tuple. | No fallback to nearby jurisdictions, no probabilistic guess, no LLM-only synthesis. | Regression case where the database holds no rule for the queried tuple; assertion that the response is a refusal, not a hedged answer. |
| INV-LLM-002 | Citations rendered to users link to a `source_document.url` that was the actual basis for extraction. Citations are not synthesized by the model. | A citation URL is fabricated, copied from another source, or points to a page that does not contain the cited claim. | Regression case asserting every citation in a response resolves to a row in `source_document` whose extraction_trace produced the cited rule. |
| INV-LLM-003 | The Opus research loop cannot directly write to production rules tables. Applied ingestion changes pass through a review-and-apply gate. | A poisoned source document or prompt-injected page coerces the agent into writing a rule the operator never reviewed. | The agent's tool schema has no direct `INSERT` on rules; integration test that the apply path is the only writer. |
| INV-LLM-004 | User input on the Sonnet path is delimited from the system prompt and never concatenated as instructions. The system prompt is not user-controllable. | Direct prompt injection overrides grounding, exfiltrates the system prompt, or coerces tool use. | Regression case for known prompt-injection payloads; assertion that the assistant refuses or ignores the injected instruction and still cites a real source. |
| INV-LLM-005 | Model routing: Sonnet runs on the synchronous user path; Opus runs on the offline research/ingestion loop. The user path never invokes Opus. | Opus on the user path inflates latency, cost, and variance, and exposes the user surface to agentic-loop failure modes that are only acceptable behind the review-and-apply gate. | Static check that frontend / user-path code does not reference Opus model IDs; regression case asserting the user path's model selection is Sonnet for both retrieval and refusal flows. |

## Operational invariants

| ID | Invariant | Deployment or rollback concern | Observability requirement |
|---|---|---|---|
| INV-OPS-001 | Worker failures do not block the user path. The Sonnet path reads from the last-good Postgres state. | An ingestion failure or worker crash takes the assistant offline. | Worker and frontend share a database but not a process. Health check on the user path does not depend on worker liveness. |
| INV-OPS-002 | Ingestion is idempotent at the `source_document` level. Re-ingesting the same URL upserts the existing row and does not duplicate rules or create orphan traces. | Re-running a job inflates the ruleset; dedupe drift produces conflicting "duplicate" rows. | Upsert keyed on `source_document.url`; integration test re-running ingestion on the same URL twice. (When `content_hash` is added to `source_document`, strengthen the key to `(url, content_hash)` so a re-fetch with changed content versions cleanly rather than overwriting silently -- target state.) |
| INV-OPS-003 | Migrations are forward-and-backward safe under live traffic. No maintenance windows assumed. | A migration that requires offline time blocks a production deploy or breaks the user path mid-deploy. | Migration review checklist: no `DROP COLUMN` in same release as the code that stops writing it; expand-then-contract pattern. |
