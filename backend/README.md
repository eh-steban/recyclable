# Recyclable Backend

Python research worker for the Recycling Law Assistant. Handles asynchronous
source ingestion, rule extraction, and eval runs. Calls Claude Opus for the
agentic research loop. Not on the user request path.

## Quick Start

See the repo-root `docker-compose.yaml` to run the full local stack. For
one-off CLI commands:

```bash
# Seed a dataset
python -m app.cli seed --dataset denver-easy

# Verify a seeded dataset
python -m app.cli verify --dataset denver-easy

# Run migrations
alembic upgrade head
alembic downgrade base
```

## Environment

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `ANTHROPIC_API_KEY` | Anthropic API key (ingestion only) |
| `LOG_LEVEL` | Log level |

## Seed datasets

Seed datasets live under `backend/seeds/<dataset>/`. The `denver-easy`
dataset is the Phase C seed for experiment `01-grounded-retrieval`:

| File | Description |
| :--- | :---------- |
| `jurisdiction.yaml` | Denver jurisdiction row |
| `source_documents.yaml` | 4 denvergov.org recycling pages (authority_level 1-2) |
| `materials.yaml` | 8 materials with aliases (6 accepted, 2 rejected) |
| `rules.yaml` | 8 active rules, each with a verbatim source_quote |
| `regression_cases.yaml` | 8 eval cases (accepted/rejected/conditional/OOJ) |

## What This Is

Experiment `01-grounded-retrieval`, Step 1. Establishes the 7-table
knowledge-base schema, a seed/verify CLI, and the first Denver dataset.
The `denver-easy` seed proves the pipeline before any LLM retrieval
code is written. See
`private/product/experiments/01-grounded-retrieval/kata.md` for the full
experiment context and
`private/specs/01-data-spine.md` for the acceptance criteria.
