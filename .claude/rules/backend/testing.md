---
paths:
  - "backend/tests/**/*.py"
  - "backend/conftest.py"
---
# Backend Testing Standards

## Test isolation and the shared DB setup

Each test category owns its own DB fixture tier. Mixing tiers is
the primary source of deadlocks and flaky-state failures in this
suite; do not promote a fixture to a wider scope without reviewing
this section.

### Logic tests -- in-memory, no Postgres

Domain, application, and route-logic tests use the
function-scoped in-memory repo fixtures from `tests/conftest.py`:
`mem_jurisdiction_repo`, `mem_material_repo`, `mem_rule_repo`,
`mem_source_repo`, and `mem_answer_audit_record_repo`. Fake LLMs
replace the `AnthropicClient` at construction. No Postgres
connection is needed or opened.

Example: `tests/application/test_answer_query.py` drives the real
`AnswerQuery` use case, `RetrievalService`, and
`GroundingValidator` end-to-end without touching the database.

### DB-interaction tests -- function-scoped rollback

Tests that exist specifically to prove DB interaction (repository
round-trips, and the `/ask` integration test that proves the
`AnswerAuditRecord` actually persists) use a function-scoped
rollback fixture. The fixture opens a connection-level transaction
at the start of each test and rolls it back on teardown -- no
DELETE cleanup required, and test-only rows never persist.

Two fixtures implement this pattern:

- `db_session` (`tests/conftest.py`) -- general repository tests.
- `regression_db_session` (`tests/regression/conftest.py`) --
  seeded regression tests; also overrides the FastAPI `get_db`
  dependency so the `/ask` route participates in the same
  connection-level transaction.

This works because the `/ask` write path only flushes, never
commits. The rollback on teardown leaves the database clean.

### CLI tests -- TRUNCATE between tests

CLI tests must issue real commits to verify seed idempotency and
atomicity. They use the function-scoped `clean_db` fixture from
`tests/cli/conftest.py`, which TRUNCATEs all seed tables before
and after each test.

### Migration tests -- module-scoped engines, named exception

Real DDL (CREATE TABLE, ALTER TABLE) cannot live inside a
rolled-back transaction. Each migration test module therefore
builds its own module-scoped engine and restores the schema to
`head` in teardown. Those engines carry a `lock_timeout` setting
so a blocked DDL statement fails fast rather than hanging.

Migration tests are the only permitted consumer of module-scoped
DB engines.

### The load-bearing rule: no session-scoped DB transaction

**A session-scoped DB transaction is forbidden in the default
suite.**

A session-scoped transaction holds connection locks across all
tests in the session. When a migration test's DDL -- which
acquires an ACCESS EXCLUSIVE lock -- runs while such a transaction
is open, it blocks indefinitely. A session-scoped rollback fixture
in this suite previously caused exactly this deadlock.

The only session-scoped DB usage permitted is behind the opt-in
`RUN_LIVE_EVALS` live eval, which runs in isolation from the
default suite.

Cross-reference: the `db_engine` fixture in `tests/conftest.py`
carries `NullPool` and a `lock_timeout=5000` ms setting for the
same reason -- a lingering pooled connection with an open
transaction would produce the same deadlock vector.

### Randomized execution order

The suite uses `pytest-randomly` (a backend dev dependency), so test
execution order is shuffled on every run. Each run prints a line like
`Using --randomly-seed=<N>` in the pytest header -- that seed makes the
shuffle reproducible.

Order-independence is what the existing DB-isolation discipline
(rollback, TRUNCATE, and module-scoped engines described above) buys:
no test should leave state that a later test depends on. Randomized
order surfaces hidden violations of that discipline.

To replay a failing run exactly:

```bash
# Pin the seed from the failing run's header
pytest -p randomly --randomly-seed=<N>

# Or replay the most recent run without looking up the seed
pytest -p randomly --randomly-seed=last
```

## Domain tests

Unit test all domain entities, value objects, and domain services:

- Test business rules and invariants
- No mocking of domain internals
- Examples: validation rules, calculation logic, state transitions

```python
# Good domain test
def test_order_item_rejects_negative_quantity():
    with pytest.raises(ValueError):
        OrderItem(product_id=1, quantity=-1, unit_price=Decimal("9.99"))

def test_discount_calculation_applies_percentage():
    result = OrderService.apply_discount(subtotal=Decimal("100"), percent=20)
    assert result == Decimal("80")
```

## Application tests

Test use cases with mocked infrastructure:

- Mock repositories and external services
- Verify DTOs and data transformations
- Test the orchestration logic

```python
def test_get_user_returns_mapped_domain_model(mock_repo, mock_mapper):
    mock_repo.get_by_id.return_value = some_orm_model

    result = GetUserUseCase(mock_repo, mock_mapper).execute(42)

    mock_mapper.to_domain.assert_called_once()
```

## Integration tests

Focus areas:

- Repository implementations against test database
- API endpoints end-to-end
- External API client behavior

## Coverage goals

| Layer | Target |
| ------- | -------- |
| Domain | 90%+ |
| Application | 80%+ |
| Infrastructure | Critical paths |

## Error path testing

Every error path should be tested. API endpoints must have tests for each
error category.

### Required error tests

| Scenario | Status Code | Test Pattern |
| ---------- | ------------- | -------------- |
| Invalid input | 400 | Validation failures |
| Resource not found | 404 | Missing entity |
| External service failure | 502/503 | Dependency timeout/error |
| Database error | 500 | Connection failure |

### Mocking external failures

```python
import pytest

@pytest.fixture
def mock_external_failure(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="http://external-service/endpoint",
        status_code=500,
        json={"error": "Internal error"},
    )
    yield

@pytest.mark.asyncio
async def test_external_failure_returns_502(async_client, mock_external_failure):
    response = await async_client.get("/resource/123")
    assert response.status_code == 502
    assert "upstream" in response.json()["detail"].lower()
```

### Exception behavior tests

```python
def test_not_found_exception_includes_resource_id():
    with pytest.raises(EntityNotFoundException) as exc_info:
        raise EntityNotFoundException("User 42 not found")

    assert "42" in str(exc_info.value)
```

### Edge case testing

| Scenario | Expected |
| ---------- | ---------- |
| Empty list response | 200 with empty arrays |
| Malformed external response | 500 with logged error |
| Concurrent access | Consistent state, no data corruption |
