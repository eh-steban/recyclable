---
paths:
  - "backend/**/*.py"
---
# Python Coding Standards

## General

- Python 3.14+
- Use type hints everywhere
- Prefer `dataclass(frozen=True)` for immutable domain models
- Use Pydantic models for API validation and DTOs
- Formatting: 80-col line limit, enforced by `ruff format`. See
  `.claude/docs/formatting.md`.

## Imports

**All imports live at the top of the module**, outside any class or
function body. Enforced by ruff `PLC0415` (`import` should be at the
top-level of a file).

The narrow exceptions, each requiring a `# noqa: PLC0415` plus a
one-line comment explaining why:

- **CLI / plugin subcommand dispatch** -- a top-level entry point
  that loads exactly one of several heavy subcommand modules per
  invocation. Example: `src/cli/__main__.py` lazy-loads `seed.py`
  vs `verify.py`.
- **Genuine circular-import workarounds** -- the import must live
  inside the function because the modules cannot be both fully
  loaded at module-import time. State the cycle in the noqa comment.
- **Optional heavy dependency** -- the function is only called when
  the dependency is present, and importing it at module top would
  block startup. State which dependency.

"It felt convenient" and "I want to scope the import to the test"
are not exceptions. Lift the import.

## Naming Conventions

| Type | Convention | Example |
| ------ | ------------ | --------- |
| Files | snake_case | `create_order.py`, `user_repo.py` |
| Classes | PascalCase | `UserRepo`, `OrderService` |
| Functions | snake_case | `calculate_total_price` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |

## Domain Services

Name domain services so that `Class.method()` reads naturally as an action:

```python
# ✅ Good - reads as "OrderService calculate" or "calculate order total"
class OrderService:
    @staticmethod
    def calculate_total(order: Order) -> Decimal:
        ...

# ✅ Good - reads as "UsersService aggregate"
class UsersService:
    @staticmethod
    def aggregate(raw_data: list[RawUser]) -> dict[int, UserStats]:
        ...

# ❌ Bad - redundant naming
class OrderTotalCalculator:
    def calculate_order_total(...)  # "order total" appears twice
```

**Guidelines:**

- Class name = noun (what data you're working with)
- Method name = verb (what action you're performing)
- Use plural form to distinguish services that work with multiple models
  (`UsersService` vs `UserService`)
- Suffix with `Service` to indicate it's a service class

## Domain Models

```python
from dataclasses import dataclass

# Immutable where possible
@dataclass(frozen=True)
class OrderItem:
    product_id: int
    quantity: int
    unit_price: Decimal
```

## Dependency Injection

Use constructor injection for infrastructure concerns:

```python
class OrderRepo:
    def __init__(self, db: Database):
        self.db = db
```

## API Design

- Follow REST conventions
- Use Pydantic models for request/response validation
- Return proper HTTP status codes
- Include pagination for list endpoints
