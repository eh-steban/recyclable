---
paths:
  - "backend/**/*.py"
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
---
# Error Handling Standards

Cross-service error handling philosophy and principles.

## Philosophy

- **Fail fast, recover gracefully** -- Detect errors early, handle them
  appropriately
- **Errors are information** -- Use them for debugging and improvement
- **User-facing errors: helpful without leaking internals** -- Guide users,
  protect implementation details
- **Internal errors: detailed for debugging** -- Log full context for developers

## Error categories

| Category | Example | HTTP Status | Response Strategy |
|----------|---------|-------------|-------------------|
| Client Error | Invalid input format | 400 | Helpful message explaining the issue |
| Not Found | Resource doesn't exist | 404 | Clear "not found" message |
| Upstream Failure | External API/service down | 502/503 | Retry hint, generic message |
| Internal Error | Unexpected exception | 500 | Generic message, log full details |

## Graceful degradation patterns

### Stale-While-Error

Return cached data when fresh data is unavailable:

- Frontend implements this with `allowStaleOnError` option
- Prefer stale data over complete failure for non-critical reads

### Partial data return

When possible, return available data even if some parts fail:

- Missing optional data? Still show what's available
- Timeline failed? Still show the main resource

### Circuit Breaker (Future)

For external services with repeated failures:

- Track failure rates
- Open circuit to fail fast during outages
- Gradually test recovery

## Sensitive data rules

### NEVER log

- API keys, secrets, tokens
- Session identifiers
- User credentials (passwords, OAuth tokens)
- Full request/response bodies in production

### NEVER expose in error responses

- Stack traces
- Internal IPs or hostnames
- Database queries or connection strings
- File system paths
- Third-party API details

### ALWAYS sanitize

- User input before including in error messages
- URLs (remove query params with sensitive data)
- Resource IDs are OK to include in internal logs

## Error message guidelines

### User-facing messages

| Scenario | Good | Bad |
|----------|------|-----|
| Invalid input | "ID must be a number" | "ValueError: invalid literal for int()" |
| Not found | "Resource not found" | "NullPointerException at line 42" |
| Server error | "Something went wrong. Please try again." | "PostgreSQL connection refused at 10.0.0.5:5432" |
| Timeout | "Request timed out. The server may be busy." | "httpx.TimeoutException after 300s" |

### Internal log messages

Include actionable context:

```text
# Good
ERROR - User 42: Failed to process payment -- Stripe returned 402 (card declined)

# Bad
ERROR - Payment failed
```

## Testing requirements

Every error path should be tested. See service-specific testing rules:

- `backend/testing.md` -- API error response tests
- `frontend/testing.md` -- Error state and boundary tests
