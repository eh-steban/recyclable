---
paths:
  - "backend/app/**/*.py"
---
# Backend Error Handling

Python/FastAPI error handling patterns and standards.

## Exception hierarchy

```text
Exception
├── DomainException (base for domain errors)
│   ├── EntityNotFoundException
│   ├── DataProcessingException
│   └── DataIntegrityException
├── ExternalServiceException (base for external failures)
│   └── ExternalAPIError
└── ValidationException (base for input validation)
```

## HTTP status code mapping

| Exception | Status | Client Message |
|-----------|--------|----------------|
| ValidationException | 400 | Describe the validation error |
| EntityNotFoundException | 404 | "Resource not found" |
| ExternalAPIError | 502 | "Upstream service unavailable" |
| DataIntegrityException | 500 | "Data processing error" |
| SQLAlchemyError | 500 | "Database error" |
| Unhandled Exception | 500 | "Internal server error" |

## API route error handling pattern

```python
from fastapi import HTTPException
from app.domain.exceptions import DomainException, ExternalServiceException
from app.utils.logger import get_logger

logger = get_logger(__name__)

@router.get("/{resource_id}")
async def get_resource(resource_id: int, ...):
    try:
        result = await use_case.execute(resource_id)
        return result

    except DomainException as e:
        # Domain errors - expected failures, log at WARNING
        logger.warning("Domain error for resource_id=%s: %s", resource_id, e)
        raise HTTPException(status_code=_map_status(e), detail=str(e))

    except ExternalServiceException as e:
        # External failures - log with context
        logger.error(
            "External service error for resource_id=%s: %s", resource_id, e
        )
        raise HTTPException(status_code=502, detail="Upstream service error")

    except HTTPException:
        # Re-raise FastAPI exceptions as-is
        raise

    except Exception as e:
        # Unexpected errors - full stack trace, generic response
        logger.exception("Unhandled error for resource_id=%s", resource_id)
        raise HTTPException(status_code=500, detail="Internal server error")
```

## Repository error handling

Convert infrastructure exceptions to domain exceptions at the repository
boundary:

```python
from sqlalchemy.exc import SQLAlchemyError
from app.domain.exceptions import DataIntegrityException

class UserRepository:
    def get_by_id(self, user_id: int) -> UserModel | None:
        try:
            return self.session.query(UserModel).filter_by(id=user_id).first()
        except SQLAlchemyError as e:
            logger.error("Database error fetching user %s: %s", user_id, e)
            raise DataIntegrityException(f"Failed to fetch user {user_id}")
```

## External service error handling

```python
import httpx
from app.domain.exceptions import ExternalAPIError

async def call_external_service(url: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout calling external service: %s", url)
        raise ExternalAPIError("External service timeout")
    except httpx.HTTPStatusError as e:
        logger.error(
            "External service error: %s - %s",
            e.response.status_code,
            e.response.text[:200],
        )
        raise ExternalAPIError(
            f"External service returned {e.response.status_code}"
        )
```

## Error response format

```python
# All error responses follow this structure
{
    "detail": "Human-readable error message"
}

# For validation errors (422), FastAPI provides:
{
    "detail": [
        {
            "loc": ["body", "field_name"],
            "msg": "value is not a valid integer",
            "type": "type_error.integer"
        }
    ]
}
```

## Exception best practices

1. **Define exceptions in domain layer** -- Keep `app/domain/exceptions.py` as
   the source of truth
2. **Include context in exception messages** -- `f"User {user_id} not found"`
   not just `"Not found"`
3. **Don't catch too broadly** -- Avoid bare `except:` clauses
4. **Re-raise HTTPException** -- Don't wrap FastAPI exceptions in your handlers
5. **Log before raising** -- Ensure errors are logged even if response fails
