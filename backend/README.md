# Recyclable Backend

Python research worker for the Recycling Law Assistant. Handles asynchronous source ingestion, rule extraction, and eval runs. Calls Claude Opus for the agentic research loop. Not on the user request path.

## Quick Start

See the repo-root `docker-compose.yaml` to run the full local stack. For one-off CLI commands:

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

## What This Is

Phase A of experiment `01-grounded-retrieval`. Establishes the 7-table knowledge-base schema and the seed/verify CLI. See `private/product/experiments/01-grounded-retrieval/kata.md` for the full experiment context.
