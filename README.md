# Recyclable

Recycling Law Assistant -- grounded, source-cited recycling Q&A. Two cooperating systems share one Postgres knowledge base:

- **`frontend/`** -- Next.js App Router app. SEO-crawlable jurisdiction/material pages and an interactive assistant. Claude **Sonnet** on the user path.
- **`backend/`** -- Python research worker. Asynchronous source ingestion, extraction, regression-suite runs. Claude **Opus** for the agentic research loop.

See `recycling-agent-experiment-spec.md` for the full strategy doc, and `private/product/strategy/vision.md` for the working vision.

## Quick Start

```bash
cp .env.example .env
# edit .env -- ANTHROPIC_API_KEY is required
docker compose up
```

- Frontend: http://localhost:3000
- Worker admin: http://localhost:8000
- Postgres: `localhost:5432` (user `recyclable`, db `recyclable`)

