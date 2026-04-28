---
paths:
  - ".devcontainer/*"
  - "**/Dockerfile"
  - "docker-compose.yaml"
  - ".github/workflows/*"
---
# Container Architecture

Detailed documentation of container structure, optimization, and best practices.

## Container Design Philosophy

1. **Minimal production images** -- Only include runtime dependencies
2. **Security first** -- Non-root users, minimal attack surface
3. **Layer caching** -- Optimize build times with proper layer ordering
4. **Reproducibility** -- Pin versions, use lock files

## Production Containers

### Backend (Python)

**File:** `backend/Dockerfile`

**Key Features:**
- Non-root user (`lifted` UID 1000)
- Dependencies installed before code copy (better caching)
- Uvicorn ASGI server for FastAPI

**Optimization Opportunities:**
- Multi-stage build to reduce final image size
- Use `python:3.x-slim` base image
- Copy only necessary files (use `.dockerignore`)

### Frontend (Node)

**File:** `frontend/Dockerfile`

**Key Features:**
- Alpine Linux base (minimal size)
- Multi-stage build ready (named stage)
- `npm ci` for reproducible installs
- Vite dev/preview server

## Development Container

**File:** `.devcontainer/Dockerfile`

Unified container with Node.js + Python for development.

**Key Features:**
- UID 1000 matches typical host user (volume permissions)
- Both language stacks in one image
- Interactive bash shell for development

## Container User Strategy

| Container | User | UID | Rationale |
|-----------|------|-----|-----------|
| Devcontainer | `lifted` | 1000 | Matches host user for volume permissions |
| Backend | `lifted` | 1000 | Non-root |
| Frontend | `node` | 1000 | Built-in Node image user |

**Security Note:** Never run production containers as root.

## Best Practices

### Dependency Installation Order

```dockerfile
# ✅ Good - dependencies cached separately
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# ❌ Bad - dependencies reinstall on any code change
COPY . .
RUN npm ci
```

### Clean Up After Install

```dockerfile
# ✅ Good - single RUN layer, cleanup
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ❌ Bad - multiple layers, no cleanup
RUN apt-get update
RUN apt-get install -y build-essential
```

### Use .dockerignore

```
# backend/.dockerignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.egg-info/

# frontend/.dockerignore
node_modules/
dist/
.cache/
coverage/
```

## Volume Strategy

### Development Volumes

```yaml
# Code volumes (hot reload)
- ./backend:/backend
- ./frontend:/app

# Dependency caches
- /app/node_modules   # Prevents host/container conflict
```

### Production Volumes

```yaml
# Data persistence only
- postgres-data:/var/lib/postgresql/data

# No code volumes - baked into image
```

## Health Checks (Future)

```dockerfile
# Backend
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

# Frontend
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:3000/ || exit 1
```
