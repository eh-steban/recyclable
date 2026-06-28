---
paths:
  - "private/plans/discovery/**"
  - "private/plans/spikes/**"
  - "private/plans/fix/**"
  - "private/plans/implementation/**"
  - "private/specs/**"
  - "private/product/experiments/**"
---

# Research Standards

Guidelines for any agent performing research -- fetching upstream sources,
extracting recycling rules, answering domain questions, or reverse
engineering undocumented behavior.

Follow the project Writing Style (`.claude/CLAUDE.md`) in all research
output.

## Core rules

- **Say "I don't know" when uncertain.** An honest gap is more useful
  than a confident guess. Flag the gap and suggest how to fill it
  (fetch a source, query Postgres, run a regression case).
- **Verify with citations.** Every factual claim must name its source
  (file path, URL, ordinance section, line number, or column name).
  Don't assert what a rule says without pointing to where it's
  established.
- **Use direct quotes for factual grounding.** When a rule, statute, or
  field name is drawn from source code or docs, quote it verbatim
  rather than paraphrasing. This is especially important for legal
  text -- paraphrase invites hedging.
- **Refuse over guess on user-facing answers.** If grounded evidence is
  missing for a Sonnet-path question, return "I cannot verify this"
  rather than synthesize. See `.claude/rules/llm/CLAUDE.md` for the
  refusal contract.

## Confidence labeling

Tag interpretations explicitly:

| Label | Meaning |
| --- | --- |
| `confirmed` | Directly observed in a primary source (ordinance text, official municipal page, schema column, code path) |
| `inferred` | Strongly implied by neighboring rules, field names, or context |
| `hypothesis` | Plausible guess -- needs validation (re-fetch, second source, regression case) |

Example:

```text
- Denver curbside cardboard accepted -- confirmed:
  "Corrugated cardboard is accepted in purple recycle carts"
  (denvergov.org/recycling, fetched 2026-04-30)
- Denver pizza box acceptance -- inferred: cardboard is accepted and
  the page does not call out food contamination; needs explicit check
- Boulder glass program status -- hypothesis: program may be on hold
  based on a 2024 news mention; not confirmed against the city site
```

## Citation format

| Source type | Format |
| --- | --- |
| Local file | `path/to/file.py:42` |
| Database column or row | `table.column` or `table#id=...` |
| Municipal ordinance | `Jurisdiction Code <section>` plus URL with fetch date |
| Web source | Full URL plus `Last fetched: YYYY-MM-DD` |
| PDF / scanned document | Document title, page number, URL, fetch date |
| Postgres schema | `schema.table.column` (link to data-model.md when relevant) |

When citing a fetched web page, prefer a stable archival URL
(`web.archive.org` snapshot or a content hash) when the source is
volatile. Note "live URL -- may change" if archival is not yet captured.

## Scope discipline

- Answer the question asked -- don't expand scope to adjacent
  jurisdictions or materials unless directly relevant.
- If a question can't be answered without fetching live data, say so
  before fetching. The user may already have the source loaded.
- When a question spans multiple jurisdictions or materials, answer
  each combination separately with its own citations. A single
  blended answer hides which claim came from which source.
- For ingestion-time research (Opus loop), record provenance per
  claim. Downstream extraction relies on it for conflict detection.

## Reading agenda discipline

When a research task requires reading many sources:

- State the agenda before reading -- which sources, in what order, and
  what each one is expected to confirm or deny.
- After each source, record what you actually learned (not what you
  expected). Surprises matter more than confirmations.
- Stop when the question is answered. Reading further is scope creep.
