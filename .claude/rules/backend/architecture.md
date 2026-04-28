---
paths:
  - "backend/**/*.py"
  - "backend/**/**/*.py"
  - "backend/**/**/**/*.py"
---
# Backend Architecture Rules

## DDD Layer Structure

```
backend/
├── app/
│   ├── api/              # HTTP layer (thin routes)
│   ├── application/      # Use cases, orchestration
│   │   ├── mappers/      # ORM → Domain model mapping
│   │   └── use_cases/    # Application use cases
│   ├── domain/           # Pure business logic
│   │   ├── models/       # Entities, value objects
│   │   ├── services/     # Domain services (pure, no I/O)
│   │   └── exceptions.py
│   ├── infra/            # Infrastructure
│   │   ├── db/
│   │   │   ├── models/       # ORM table definitions
│   │   │   └── repositories/ # Data access layer
│   │   └── external/     # External API clients
│   └── utils/            # Cross-cutting utilities
```

## Layer Dependency Rules

| Layer | Can Import |
|-------|------------|
| `api/` | `application/`, `domain/models/`, `utils/` |
| `application/use_cases/` | `application/mappers/`, `domain/`, `infra/`, `utils/` |
| `application/mappers/` | `domain/models/`, `infra/db/models/`, `utils/` |
| `domain/models/` | Nothing (pure data structures) |
| `domain/services/` | `domain/models/`, `utils/` |
| `infra/db/models/` | `utils/` only |
| `infra/db/repositories/` | `infra/db/models/`, `utils/` |
| `infra/external/` | `domain/models/`, `utils/` |
| `utils/` | Nothing (pure utilities) |

## Key Patterns

### Domain vs Application Services

- **Domain services** (`domain/services/`): Pure business logic, no I/O, no framework dependencies
- **Application services** (`application/`): Orchestration, use cases, coordinates domain + infra

### Repository Return Types

Repositories return ORM models. Mapping to domain models happens in `application/mappers/`.

```python
# ✅ Repository returns ORM model
class UserRepository:
    def get_by_id(self, user_id: int) -> UserModel | None:
        ...

# ✅ Mapper converts ORM → Domain
class UserMapper:
    def to_domain(self, orm: UserModel) -> User:
        ...

# ✅ Use case orchestrates repo + mapper
class GetUserUseCase:
    def execute(self, user_id: int) -> User:
        orm_model = self.repo.get_by_id(user_id)
        return self.mapper.to_domain(orm_model)
```

### Service Naming Convention

Domain services follow the `Class.verb()` pattern so the call reads naturally:

```python
# ✅ Good - reads as "OrderService calculate"
class OrderService:
    @staticmethod
    def calculate_total(order: Order) -> Decimal:
        ...

# ❌ Bad - redundant naming
class OrderTotalCalculator:
    def calculate_order_total(...)  # "order total" appears twice
```

**Guidelines:**
- Class name = noun (what data you're working with), suffixed with `Service`
- Method name = verb (what action you're performing)
- Use plural form for services handling multiple items (`UsersService` vs `UserService`)
