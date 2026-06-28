---
paths:
  - "backend/src/domain/models/**/*.py"
  - "backend/src/infra/db/models/**/*.py"
  - "backend/migrations/**"
  - "frontend/lib/domain/**/*.ts"
  - "frontend/lib/db/**/*.ts"
---

# Data Model -- Recycling Knowledge Base

Postgres is the product asset. Both the SEO pages and the assistant read
from these tables. The research worker writes to them through ingestion
reports + human approval. Schema changes are coordinated -- bump migration,
update both `frontend/lib/domain/` types and
`backend/src/domain/models/`, run regression suite.

## Entities

### `jurisdictions`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `name` | text | Display name ("City and County of Denver") |
| `slug` | text unique | URL slug ("denver") |
| `type` | text | `city` \| `county` \| `state` |
| `country` | text | ISO 3166-1 alpha-2 ("US") |
| `supported_status` | text | `supported` \| `coming_soon` \| `unsupported` |
| `created_at`, `updated_at` | timestamptz | |

### `materials`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `canonical_name` | text | "Glass beverage bottle" |
| `slug` | text unique | "glass-bottles" |
| `category` | text | "glass" \| "plastic" \| "metal" \| "paper" \| "organic" \| "hazardous" \| "electronic" \| "textile" \| "other" |
| `parent_id` | uuid null | For hierarchy ("plastic" → "PET bottle") |

### `material_aliases`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `material_id` | uuid FK | |
| `alias` | text | "milk jug", "wine glass", "bubble mailer" |
| `weight` | int default 1 | Higher = stronger match |

### `source_documents`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `jurisdiction_id` | uuid FK | |
| `url` | text | |
| `title` | text | |
| `authority_level` | int | 1 = official municipal, 2 = official facility, 3 = state agency, 4 = directory, 5 = nonprofit, 6 = blog. Lower = more authoritative. |
| `fetched_at` | timestamptz | |
| `effective_date` | date null | Date the source claims its info applies from |
| `source_text` | text | Raw extracted text (chunked separately if needed) |
| `source_text_hash` | text | sha256 for change detection |
| `last_reviewed_at` | timestamptz | When a human last vetted this source |

### `rules`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `jurisdiction_id` | uuid FK | |
| `material_id` | uuid FK | |
| `disposition` | text | `curbside_recycle` \| `dropoff` \| `compost` \| `landfill` \| `hazardous_waste` \| `donate` \| `unknown` |
| `accepted_status` | text | `accepted` \| `rejected` \| `conditional` \| `unknown` |
| `preparation_steps` | text[] | "Empty and rinse", "Remove cap", ... |
| `exceptions` | text[] | "Window glass not accepted" |
| `warnings` | text[] | "Do not bag" |
| `source_document_id` | uuid FK | Which source justifies this rule |
| `source_quote` | text | Exact span from the source backing this rule |
| `confidence` | text | `high` \| `medium` \| `low` |
| `effective_from` | date null | |
| `superseded_by` | uuid null FK | Soft history -- never delete a rule, point to its replacement |

Constraint: `(jurisdiction_id, material_id, superseded_by IS NULL)` is
unique. Only one active rule per (jurisdiction, material).

### `facilities`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `jurisdiction_id` | uuid FK | |
| `name` | text | |
| `address` | text | |
| `geo_point` | geography(Point, 4326) null | PostGIS optional |
| `hours` | jsonb | Structured hours by day |
| `accepted_materials` | uuid[] | FK array to `materials.id` |
| `restrictions` | text[] | "Residents only", "Photo ID required" |
| `source_document_id` | uuid FK | |

### `answer_audit_records`

> Renamed from `answer_traces` in migration 0001 (in place) to align with
> the `AnswerAuditRecord` Ubiquitous Language per `architecture.md` and
> the Step 2 design (D6). Column shape below is the Step 1 shape; the
> Step 2 implementation reshapes the columns to the AnswerAuditRecord
> schema.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `user_query` | text | |
| `jurisdiction_id` | uuid null FK | Null if location resolution failed |
| `normalized_materials` | uuid[] | Material candidates after normalization |
| `retrieved_rule_ids` | uuid[] | |
| `retrieved_source_ids` | uuid[] | |
| `prompt_name` | text | "ask_compose" |
| `prompt_version` | int | |
| `model_id` | text | "claude-sonnet-4-6" |
| `raw_model_output` | jsonb | Pre-validation |
| `final_answer` | jsonb | Post-validation |
| `validator_result` | jsonb | `{ ok, issues[] }` |
| `confidence` | text | |
| `latency_ms` | int | |
| `cache_hit` | bool | |
| `created_at` | timestamptz | |

### `feedback`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `trace_id` | uuid FK | |
| `kind` | text | `helpful` \| `wrong` \| `outdated` \| `missing_source` |
| `note` | text null | Free-text |
| `created_at` | timestamptz | |

### `escalations`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `trace_id` | uuid null FK | If triggered by a low-confidence answer |
| `query` | text | |
| `requested_jurisdiction` | text | Whatever the user asked about |
| `kind` | text | `unsupported_jurisdiction` \| `unknown_material` \| `low_confidence` \| `user_flag` |
| `status` | text | `open` \| `claimed` \| `resolved` \| `dismissed` |
| `created_at` | timestamptz | |

### `ingestion_reports`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `jurisdiction_id` | uuid FK | |
| `seed_url` | text | |
| `source_document_ids` | uuid[] | Sources discovered/used |
| `proposed_rule_changes` | jsonb | Array of `{ op: 'add'\|'update', rule: ... }` |
| `conflicts` | jsonb | Array of `{ existing_rule_id, proposed, source_document_id, source_quote, reason }` |
| `missing_fields` | jsonb | Fields the agent could not extract |
| `status` | text | `draft` \| `pending_review` \| `approved` \| `rejected` |
| `reviewer_id` | text null | |
| `prompt_name`, `prompt_version`, `model_id` | as above | |
| `trace_id` | uuid FK | Run-trace for this ingestion run |
| `created_at`, `decided_at` | timestamptz | |

### `regression_cases`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid PK | |
| `query` | text | |
| `jurisdiction_id` | uuid FK | |
| `expected_material_id` | uuid null | |
| `expected_status` | text | accepted_status |
| `expected_disposition` | text | |
| `must_cite_source` | bool | |
| `refusal_required` | bool default false | |
| `notes` | text null | |

Cases may live as JSON files under `backend/tests/regression/cases/` and
be loaded into this table for runs against deployed instances. Either form
is the source of truth -- pick one per project and stick to it.

## Why structured rules + source chunks

Vector chunks alone miss exact accepted/rejected distinctions. Structured
rules alone struggle to explain nuanced source text. Storing both lets
retrieval combine precision (filter to `(jurisdiction, material, accepted)`)
with explanation (cite the source quote that supports it).

## When pgvector

Skip pgvector for 01. Add it only if 01 step 2 regression failures clearly
trace to retrieval miss on materials whose aliases are absent from
`material_aliases`. If added, embed `source_documents.source_text` chunks
and use vector search as a fallback after structured rule lookup, never as
the primary path.

## Migration discipline

- Every schema change is an Alembic migration (backend) -- never edit
  existing migrations.
- Every migration tested up AND down.
- Frontend `lib/domain/` types updated in the same PR as the migration.
- Regression suite re-run before merge.
- For breaking changes, bump the contract version in
  `private/specs/contracts/`.
