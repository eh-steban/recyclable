---
paths:
  - "backend/**/*.py"
  - "backend/**/**/*.py"
  - "backend/**/**/**/*.py"
---
# Backend Service

Python/FastAPI service implementing domain-driven design.

## Structure

```
backend/
├── app/
│   ├── api/                          # HTTP Layer (thin routes)
│   │   └── [resource].py
│   │
│   ├── application/                  # Use Cases / Orchestration
│   │   ├── mappers/                  # ORM → Domain model mapping
│   │   └── use_cases/
│   │
│   ├── domain/                       # Business Logic (pure, no framework deps)
│   │   ├── models/                   # Entities & Value Objects
│   │   ├── services/                 # Domain Services (pure, no I/O)
│   │   └── exceptions.py
│   │
│   ├── infra/                        # Infrastructure Layer
│   │   ├── db/
│   │   │   ├── models/               # ORM table definitions
│   │   │   └── repositories/         # Data access layer
│   │   └── external/                 # External API clients
│   │
│   ├── utils/                        # Cross-cutting utilities
│   ├── config.py
│   └── main.py
│
├── tests/                            # Mirrors app/ structure
│   ├── api/
│   ├── application/
│   ├── domain/
│   ├── infra/
│   └── conftest.py
│
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Commands

```bash
# Run locally (from repo root)
docker-compose up backend

# Run tests
cd backend && pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

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
