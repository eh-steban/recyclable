---
paths:
  - "backend/**/*.py"
---

# Backend Service

Python service with two surfaces sharing one domain layer:

1. **FastAPI HTTP API** (synchronous, user-facing). Owns the Sonnet user
   path: location resolution, material normalization, rule retrieval,
   prompt composition, validator, response. Powers the frontend over
   HTTP. Latency is load-bearing -- the spec target is p50 < 3 s, p95
   < 6 s end-to-end through Sonnet.
2. **Ingestion worker** (asynchronous, internal). Source fetch,
   extraction, conflict detection, eval runs. Uses Claude **Opus** for
   the agentic research loop. Latency is not load-bearing here;
   correctness, citation fidelity, and auditability are.

Both surfaces import the same `src/domain/`. Both write through the same
`src/infra/db/` repositories. The HTTP API never touches `src/worker/`
internals; the worker never touches FastAPI request handling. Domain is
the only shared layer.

This service owns the Postgres schema. SQLAlchemy models are the
canonical schema definition; Alembic generates migrations from them.
The frontend never connects to Postgres -- it consumes the FastAPI
contract via a generated TypeScript client (see
`.claude/rules/contracts.md` for the contract-generation pipeline).

Implements domain-driven design. Tactical and strategic principles
live in `.claude/docs/ddd/` (hub: `principles-hub.md`); they are
reference docs, not auto-loaded rules -- open applicable shards on
demand via the hub.

## Structure

<!-- markdownlint-disable MD013 -->
```text
backend/
├── src/
│   ├── api/                          # FastAPI HTTP layer
│   │   ├── main.py                   # FastAPI() app + middleware + route mounting
│   │   ├── deps.py                   # Dependency providers (DB session, settings)
│   │   ├── schemas/                  # Pydantic request/response models
│   │   │   ├── ask.py                # AskRequest, Answer, Citation, Facility
│   │   │   ├── jurisdictions.py
│   │   │   ├── materials.py
│   │   │   └── rules.py
│   │   └── routes/                   # User-facing routes (thin -- delegate to use_cases)
│   │       ├── ask.py                # POST /ask -- Sonnet user path
│   │       ├── jurisdictions.py      # GET /jurisdictions/{slug}
│   │       ├── materials.py          # GET /materials, GET /materials/{slug}
│   │       └── rules.py              # GET /rules?jurisdiction=&material=
│   │
│   ├── worker/                       # Ingestion worker (async, internal)
│   │   ├── runner.py                 # Worker entry point
│   │   └── pipelines/                # Per-source ingestion pipelines
│   │
│   ├── cli/                          # CLI entry points (operator workflows)
│   │   └── ingest.py                 # `python -m src.cli ingest --source <url>`
│   │
│   ├── application/                  # Use Cases / Orchestration (called by api/ AND worker/)
│   │   ├── mappers/                  # ORM ↔ Domain model mapping
│   │   └── use_cases/                # AnswerQuery (user path), IngestSource, ExtractRules, ...
│   │
│   ├── domain/                       # Business Logic (pure, no framework deps)
│   │   ├── models/                   # Entities & Value Objects (mirrors data-model.md)
│   │   ├── services/                 # Domain Services (pure, no I/O)
│   │   └── exceptions.py
│   │
│   ├── infra/                        # Infrastructure Layer
│   │   ├── db/
│   │   │   ├── models/               # ORM table definitions (canonical schema)
│   │   │   └── repositories/         # Data access layer
│   │   └── external/
│   │       ├── source_fetcher.py     # HTTP/HTML fetch + caching
│   │       └── anthropic_client.py   # Claude SDK wrapper (Sonnet + Opus + Haiku)
│   │
│   ├── llm/                          # Prompt templates, validators, tool defs
│   │   ├── prompts/                  # Versioned prompts (ask_compose, material_normalize, ingestion_*)
│   │   ├── tools/
│   │   └── validators/               # Grounding validator (user path)
│   │
│   ├── utils/                        # Cross-cutting utilities
│   └── config.py
│
├── migrations/                       # Alembic
│
├── tests/
│   ├── api/
│   ├── application/
│   ├── domain/
│   ├── infra/
│   ├── regression/                   # See .claude/rules/llm/regression-suite.md
│   │   └── cases/
│   └── conftest.py
│
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```
<!-- markdownlint-enable MD013 -->

## Commands

```bash
# Run full backend (API + worker) locally
docker compose up backend

# FastAPI dev server only (auto-reload, localhost:8000)
cd backend && uv run uvicorn src.api.main:app --reload

# Worker only
cd backend && uv run python -m src.worker.runner

# One-off ingestion (CLI)
cd backend && python -m src.cli ingest \
  --source https://example-city.gov/recycling

# Apply an approved ingestion report
cd backend && python -m src.cli apply-report --id <uuid>

# Emit OpenAPI spec (for frontend codegen)
cd backend && uv run python -m src.api.export_openapi > openapi.json

# Run tests
cd backend && pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run regression suite (hits the local FastAPI dev server)
pytest tests/regression -v

# Linting + formatting
ruff check src/
ruff format src/

# Type checking
basedpyright src/

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Testing notes

- Test files mirror `src/` structure in `tests/`
- Use `conftest.py` for shared fixtures
- Domain tests should be pure (no mocking)
- Application tests mock infrastructure dependencies
- See `.claude/rules/backend/testing.md` for patterns
- Test-first discipline (red / green / refactor, captured red-state
  evidence): `.claude/docs/tdd.md`

## Database

- Use Alembic for migrations
- Never edit existing migrations
- Test migrations up AND down

## HTTP API conventions

- **Routes are thin.** A route handler validates input (Pydantic), calls
  a use case in `src/application/use_cases/`, maps the result to a
  response schema, returns. Domain logic does not live in routes.
- **Pydantic schemas in `src/api/schemas/`.** Request and response shapes
  are the contract. Each route declares typed inputs and outputs;
  FastAPI emits these into the OpenAPI spec automatically.
- **OpenAPI is the contract.** The frontend's TS client is generated
  from this spec (see `.claude/rules/contracts.md`). Do not hand-edit
  the OpenAPI file; update Pydantic schemas and re-emit.
- **Latency on the user path.** The Sonnet user path (`POST /ask`) is
  measured: p50 < 3 s, p95 < 6 s. Avoid synchronous I/O the user does
  not need. Cache the system prompt; do not re-query Postgres for data
  already in memory.
- **Inject dependencies via `Depends`.** Never instantiate concrete
  infrastructure (DB session, Anthropic client, repository) inside a
  use case or domain service. Tests substitute fakes via dependency
  override.

## Code quality

- Split modules at ~200-300 lines
- Use cases with >5-7 injected dependencies are a refactor signal
- Functions with >4-5 parameters are a refactor signal -- bundle into a
  dataclass or schema
