---
paths:
  - "backend/src/**/*.py"
---
# Backend Observability

Python/FastAPI logging and monitoring guidelines. Cross-service
logging and observability standards (log levels, correlation IDs,
what-not-to-log) live in `.claude/docs/observability.md`.

## Logger setup

Use a centralized logger singleton pattern:

```python
from app.utils.logger import get_logger

logger = get_logger(__name__)
```

Initialize the logger once in `main.py` via a `LoggerManager` or equivalent.

## Log format

```text
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

Example output:

```text
2024-01-15 10:30:45 - app.api.users - INFO - User 42 created successfully
```

## Log level usage

```python
# DEBUG - Development troubleshooting (not in production)
logger.debug("Query params: %s", params)

# INFO - Normal operations worth noting
logger.info("User %s: Request processed in %.2fs", user_id, duration)

# WARNING - Recoverable issues
logger.warning(
    "Cache miss for resource %s, fetching from source", resource_id
)

# ERROR - Failures (use logger.exception for stack traces)
logger.error("External API failed: %s", error_message)
logger.exception("Unexpected error processing resource %s", resource_id)
```

## Required log points

### API routes

```python
@router.get("/{resource_id}")
async def get_resource(resource_id: int):
    logger.info("Resource %s: Request received", resource_id)

    # ... processing ...

    logger.info(
        "Resource %s: Response size %s bytes", resource_id, len(response_json)
    )
    return response
```

### External service calls

```python
logger.info("Calling external service: %s", url)
start = time.time()
response = await client.post(url, json=payload)
duration = time.time() - start
logger.info(
    "External service response: status=%s, duration=%.2fs",
    response.status_code,
    duration,
)
```

### Repository operations

```python
# DEBUG level for routine queries
logger.debug("Fetching resource %s from database", resource_id)

# ERROR level for failures
logger.error(
    "Database error fetching resource %s: %s", resource_id, str(e)[:200]
)
```

## What NOT to log

- API keys, tokens, passwords
- Full request bodies (use DEBUG if needed)
- User session data
- SQL queries with user data (sanitize first)

## Correlation IDs (Future)

```python
# middleware.py
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get(
        "X-Correlation-ID", str(uuid.uuid4())
    )
    with logger.contextualize(correlation_id=correlation_id):
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

## Environment configuration (Future)

```python
# config.py
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain")  # "plain" or "json"
```
