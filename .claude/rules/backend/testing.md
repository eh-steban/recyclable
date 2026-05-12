---
paths:
  - "backend/tests/**/*.py"
  - "backend/conftest.py"
---
# Backend Testing Standards

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
