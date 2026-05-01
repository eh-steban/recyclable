---
paths:
  - "backend/**/*.py"
  - "backend/**/**/*.py"
  - "backend/**/**/**/*.py"
  - "backend/**/**/**/**/*.py"
  - "frontend/src/**/*.ts"
  - "frontend/src/**/*.tsx"
  - "frontend/src/**/**/*.ts"
  - "frontend/src/**/**/*.tsx"
  - "parser/src/*.rs"
  - "parser/src/**/*.rs"
---
# Observability Standards

Cross-service logging, monitoring, and observability guidelines.

## Current State (Phase 1: Simple Logging)

- Plain text logs to stdout
- No external dependencies
- Suitable for docker-compose and k8s log aggregation
- Manual log inspection via `docker logs` or `kubectl logs`

## Log levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| DEBUG | Development troubleshooting | Variable values, flow tracing, SQL queries |
| INFO | Normal operations worth noting | Request received, resource created, user logged in |
| WARNING | Recoverable issues | Cache miss, retry attempt, deprecated usage |
| ERROR | Failures requiring attention | External service down, data error, DB error |

### Level selection guide

- If it helps debug during development only → DEBUG
- If you'd want to know it happened in production → INFO
- If something is wrong but we recovered → WARNING
- If something failed and needs fixing → ERROR

## What to log

### Always log

- Request start with identifiers (resource_id, user_id)
- Operation completion with duration
- Error context (type, message, relevant IDs)
- Data sizes for performance profiling
- External service calls (URL, status, duration)

### Contextual logging

Include enough context to debug without additional queries:

```text
# Good
INFO - User 42: Order processed successfully in 1.2s

# Bad
INFO - Order processed
```

## What NOT to log

- Passwords, API keys, tokens, secrets
- Full request/response bodies (unless DEBUG level)
- Personal identifiable information (emails, real names)
- Session data or authentication tokens
- Credit card numbers or financial data

## Correlation ID pattern

Track requests across services:

1. Generate UUID at API gateway (backend receives request)
2. Pass via `X-Correlation-ID` header to downstream services
3. Include in all log lines for that request

```text
# Backend
INFO - [corr:abc-123] User 42: Processing order

# Downstream service
INFO - [corr:abc-123] [process_order] Validating payment
```

## Service-specific guidelines

See detailed logging guidelines:

- `backend/observability.md` -- Python logging setup
- `frontend/observability.md` -- Browser console logging

## Long-term roadmap

### Phase 2: Structured logging (3-6 months)

- JSON format for all services
- Consistent field names: `timestamp`, `level`, `service`, `correlation_id`,
  `message`
- Environment-based log level configuration (`LOG_LEVEL` env var)

### Phase 3: Centralized logging (6-12 months)

- ELK stack (Elasticsearch, Logstash, Kibana) or similar
- Log aggregation from all services
- Searchable, filterable logs

### Phase 4: Metrics and tracing (12+ months)

- Prometheus metrics (request latency, error rates, queue depths)
- Distributed tracing (OpenTelemetry)
- Error tracking service (Sentry)

## Performance considerations

- Logging should not significantly impact request latency
- Use async logging where possible
- Avoid logging in hot paths (tight loops)
- Sample high-volume events if needed
