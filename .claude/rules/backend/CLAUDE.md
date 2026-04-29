---
paths:
  - "backend/**/*.py"
  - "backend/**/**/*.py"
  - "backend/**/**/**/*.py"
---
# Backend Service

Python research worker. Asynchronous source ingestion, extraction, conflict detection, regression-suite runs, and operator CLI/admin endpoints. **Not** on the user request path -- the user-facing `/api/ask` lives in the Next.js frontend. This service uses Claude **Opus** for the agentic research loop.

Implements domain-driven design.

## Structure

```
backend/
├── app/
│   ├── api/                          # Operator/admin HTTP routes (thin)
│   │   └── [resource].py
│   │
│   ├── cli/                          # CLI entry points (operator workflows)
│   │   └── ingest.py                 # `python -m app.cli ingest --source <url>`
│   │
│   ├── application/                  # Use Cases / Orchestration
│   │   ├── mappers/                  # ORM → Domain model mapping
│   │   └── use_cases/                # IngestSource, ExtractRules, RunRegressionSuite, ApplyIngestionReport
│   │
│   ├── domain/                       # Business Logic (pure, no framework deps)
│   │   ├── models/                   # Entities & Value Objects (mirrors data-model.md)
│   │   ├── services/                 # Domain Services (pure, no I/O)
│   │   └── exceptions.py
│   │
│   ├── infra/                        # Infrastructure Layer
│   │   ├── db/
│   │   │   ├── models/               # ORM table definitions
│   │   │   └── repositories/         # Data access layer
│   │   └── external/
│   │       ├── source_fetcher.py     # HTTP/HTML fetch + caching
│   │       └── anthropic_client.py   # Claude SDK wrapper
│   │
│   ├── llm/                          # Prompt templates, validators, tool defs
│   │   ├── prompts/
│   │   ├── tools/
│   │   └── validators/
│   │
│   ├── utils/                        # Cross-cutting utilities
│   ├── config.py
│   └── main.py                       # FastAPI app for admin endpoints (optional)
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

## Commands

```bash
# Run worker locally (from repo root)
docker compose up backend

# One-off ingestion (CLI)
cd backend && python -m app.cli ingest --source https://example-city.gov/recycling

# Apply an approved ingestion report
cd backend && python -m app.cli apply-report --id <uuid>

# Run tests
cd backend && pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run regression suite
pytest tests/regression -v

# Linting + formatting
ruff check app/
ruff format app/

# Type checking
mypy app/

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Testing Notes

- Test files mirror `app/` structure in `tests/`
- Use `conftest.py` for shared fixtures
- Domain tests should be pure (no mocking)
- Application tests mock infrastructure dependencies
- See `.claude/rules/backend/testing.md` for patterns

## Database

- Use Alembic for migrations
- Never edit existing migrations
- Test migrations up AND down

## Code Quality

- Split modules at ~200-300 lines
- Use cases with >5-7 injected dependencies are a refactor signal
- Functions with >4-5 parameters are a refactor signal -- bundle into a dataclass or schema
- Inject ALL external dependencies (DB, APIs, services) via FastAPI `Depends` -- never instantiate concrete infrastructure inside a use case or domain service
