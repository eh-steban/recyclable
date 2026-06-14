---
paths:
  - "backend/**"
---

# Backend Mental Model

Architecture constraints and load-bearing decisions for the Python
research worker. This document describes how the worker is shaped and
why -- not what specific files or APIs exist (those live in code and
in `.claude/rules/architecture.md`).

This is a stub. Fill in as constraints stabilize. Until then, treat
unwritten sections as "no committed constraint -- ask before
introducing one."

## Role of the worker

The backend is a Python research worker. It is not on the user request
path. It runs ingestion, extraction, conflict detection, and eval runs.
Latency is not load-bearing; correctness, citation fidelity, and
auditability are.

The user-facing assistant lives in the frontend and calls Sonnet
synchronously. The worker calls Opus for the agentic research loop.

## Architectural commitments

- **DDD layering.** `domain/` is pure business logic with no framework
  imports. `infra/` adapts external systems (Postgres, HTTP, LLM SDK).
  `api/` exposes use cases. `cli/` is the operator entry point.
  Domain logic must not leak into `infra/` or `api/`.
- **Postgres is the product asset.** Structured rules drive both SEO
  pages and assistant answers. There is no separate hand-written
  content layer. Schema changes are reviewed against
  `.claude/rules/data-model.md`.
- **Fail fast at boundaries.** Validate inputs at the system edge
  (HTTP, CLI, ingestion). Refuse to extract or answer when evidence
  is missing rather than synthesizing a guess.
- **Ingestion is auditable.** Every applied rule traces back to a
  source document and an extraction trace. Mistakes are reviewable;
  silent overrides are not allowed.

## Non-commitments (for now)

- Specific ORM, queue, or scheduler choices are not load-bearing yet.
  When one is chosen, capture the decision here.
- Concurrency model for the ingestion loop is not yet decided.
- Multi-tenant boundaries are not yet defined.

## Common gotchas

- **Out-of-jurisdiction sentinel.** `uuid.UUID(int=0)` (all-zero UUID) is the
  project-wide sentinel for "no real jurisdiction resolved" on the user path.
  It is minted as the named constant `_OOJ_JURISDICTION_ID` in
  `application/answer_query.py` and re-materialized ad hoc in the
  `SqlAnswerAuditRecordRepo` row-hydration path when the ORM
  `jurisdiction_id` column is `NULL`. Treat an all-zero `JurisdictionId` as
  a domain-level "no jurisdiction" marker; never seed a real jurisdiction
  with this id.

- **Anthropic SDK 0.102.0 import paths and cache usage.** The correct
  import paths are `anthropic.types.Message` and
  `anthropic.types.MessageParam`. The `messages.create()` call accepts
  `timeout=<float>` directly. Prompt caching: add
  `"cache_control": {"type": "ephemeral"}` inside a system-block dict.
  Cache hit data lives in `response.usage.cache_creation_input_tokens`
  and `response.usage.cache_read_input_tokens` (both may be `None` or
  `0` when not cached -- not a structured field on `Message`).
  The `_call_with_retry` wrapper should return `Any`; annotate the
  assigned variable as `Message` for downstream type safety.

- **Custom HTTP error codes need a manual route check, not a Pydantic
  constraint.** A Pydantic field constraint (e.g. `max_length`) makes
  FastAPI return 422 before the handler runs. To return the contract's
  400 with a custom `error` body, omit the constraint and check in the
  handler -- `if len(body.query) > _MAX_QUERY_LEN: return
  JSONResponse(400, {"error": "query_too_long"})` (`ask.py:50-54`). The
  422 and 400 paths are mutually exclusive; the constraint always
  intercepts first. The cap also has a domain guard in
  `Query.__post_init__` (`query.py:24`), `QUERY_MAX_LENGTH = 150`
  (INV-LLM-004).

## Alembic and SQLAlchemy conventions

**Adding a PostgreSQL ENUM column in Alembic.** Create the type before
adding the column. Use
`postgresql.ENUM(...).create(op.get_bind(), checkfirst=True)` first,
then pass `sa.Enum(..., name=type_name, create_type=False)` when
calling `op.add_column`. The `create_type=False` flag tells SQLAlchemy
not to attempt creation again -- without it the migration fails with
"type already exists." In the downgrade path, drop the column before
`DROP TYPE IF EXISTS <name>` so there are no dependent objects.

**`ON CONFLICT DO UPDATE` targeting a partial unique index requires
`index_where=`, not `where=`.** When using
`insert().on_conflict_do_update()` against a partial unique index,
pass `index_where=` alongside `index_elements=` to identify the partial
index. Without it SQLAlchemy cannot resolve the conflict target.

**`ON CONFLICT DO UPDATE WHERE` guards `updated_at` churn.** Passing
`where=<ORM column comparison>` to `on_conflict_do_update()` makes the
`SET` clause fire only when data actually changed. For multi-column
guards combine with `|` (OR). For nullable columns use
`is_not(None)` / `is_(None)` because `NULL != NULL` is not true in SQL.

## Seed loaders

**Key in-memory entity maps by stable unique key (URL or slug -- not
display name or UUID).** Titles are mutable free-text; URLs for source
documents and slugs for jurisdictions and materials are the right lookup
keys. The loader resolves every cross-reference in-memory by these keys
and mints a fresh `uuid4` for any entity whose fixture omits an explicit
`id` (`_seed_parse.py:317-319`), so primary keys are per-environment, not
fixed -- nothing references a seeded row by a hardcoded UUID. Keying by
natural key surfaces a bad reference at the `EntityNotFoundError` boundary
instead of assigning a wrong FK. Caveat: because ids regenerate each run
and the upserts do not set `id` on conflict, re-seeding into an
already-populated database is the known soft spot for FK integrity --
seeding targets a clean or freshly-migrated DB. Verify idempotency with
`SELECT count(*)` row counts and `updated_at` snapshots, not
`pg_stat_user_tables.n_tup_ins` (cumulative; reflects out-of-band writes).

**YAML folded scalar (`>-`) collapses newlines to spaces.** When
storing multi-line source text in YAML using `>-` (folded, strip), YAML
collapses internal newlines to single spaces and strips the trailing
newline. This happens to align with the quote-integrity normalizer's
whitespace-collapse step (`re.sub(r'\s+', ' ', s)`), so 80-column-wrapped
`>-` blocks and single-line quote strings normalize to the same
representation. Seed YAML may be wrapped for readability at 80 columns
without breaking quote integrity, provided wraps fall at whitespace
boundaries (YAML guarantees this for scalar folding).

## Domain dataclass gotchas

**`frozen=True, slots=True` dataclasses have no `__dict__`, so
`getattr(instance, "_private_attr", None)` always returns the
default silently.** Any field the repo's `save()` reads must be a
first-class `field(default=None)` dataclass field -- not a private
attribute set via a workaround. The slots block the hack without
raising; the error surfaces later as missing data in the repo.

## Open questions

- Where does conflict detection live -- domain service or use case?
- How are extraction confidence scores represented on the data model?
- What is the failure mode when a source document is fetched but
  extraction yields zero rules?

When one of these is decided, promote the resolution into
`Architectural commitments` above and remove it from this list.
