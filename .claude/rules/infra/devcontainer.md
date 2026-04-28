---
paths:
  - ".devcontainer/*"
  - "**/Dockerfile"
  - "docker-compose.yaml"
  - ".github/workflows/*"
---
# Development Container (Devcontainer)

Unified development environment with Node.js and Python.

## Overview

The devcontainer provides a **consistent development environment** for all team members, eliminating "works on my machine" issues.

**Key Features:**
- Node.js + Python in one container
- VSCode extensions pre-installed
- Database access via shared Docker network
- Consistent formatting and linting

## Architecture

### Stack

```
ubuntu:22.04
├── Node.js         # Frontend development
├── Python          # Backend development
├── PostgreSQL client  # Database operations
└── Build tools     # gcc, make, curl, git
```

### Why Unified?

**Pros:**
- Single container for entire monorepo
- No context switching between services
- Shared tools (git, formatters, linters)
- Faster iteration

**Cons:**
- Larger image size
- Longer initial build time

**Trade-off:** Development experience wins. Production containers remain optimized.

## Configuration

### devcontainer.json Key Settings

- **dockerComposeFile:** Merges production services with devcontainer overlay
- **workspaceFolder:** VSCode opens at repo root (monorepo pattern)
- **remoteUser:** Non-root user for safety
- **postCreateCommand:** Automatic dependency installation

## User and Permissions

### UID Strategy

```dockerfile
# Use UID 1000 to match typical host user
RUN useradd -m -u 1000 -s /bin/bash lifted
```

**Why UID 1000?**
- Most Linux users have UID 1000
- Files created in container match host permissions
- No ownership conflicts on mounted volumes

**Check Your UID:**
```bash
id -u  # Should output 1000
```

If different, modify `.devcontainer/Dockerfile`:
```dockerfile
RUN useradd -m -u YOUR_UID -s /bin/bash lifted
```

## Volumes and Persistence

### Source Code Volume

```yaml
volumes:
  - ../project:/workspaces/project:cached
```

**`:cached` flag:** Optimizes I/O on macOS/Windows.

### Node Modules

**Not mounted** -- `npm install` runs in container after creation.

**Why not mount?**
- Native modules may differ between host and container
- Avoids platform-specific binary conflicts

## Development Workflows

### Starting Services

#### Option 1: Manual (Recommended for Development)

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev -- --host 0.0.0.0
```

**Pros:** Full control, separate logs, easy to restart individual services.

#### Option 2: Production Containers

```bash
docker-compose up backend frontend
```

**Pros:** Production-like environment.
**Cons:** Harder to debug, logs mixed together.

### Database Operations

```bash
# Connect to database
psql postgresql://appuser:apppassword@app-db:5432/app_db

# Run migrations
cd backend && alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"
```

### Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm run test
```

## Rebuilding the Devcontainer

### When to Rebuild

Rebuild when you change:
- `.devcontainer/Dockerfile`
- `.devcontainer/devcontainer.json`
- System dependencies (apt packages)

**Don't rebuild for:**
- Application code changes (hot reload handles this)
- Python/npm dependency changes (reinstall inside container)

### How to Rebuild

```
VSCode Command Palette → "Dev Containers: Rebuild Container"
```

## Customization

### Adding System Dependencies

```dockerfile
# .devcontainer/Dockerfile
RUN apt-get update && apt-get install -y \
    your-package-here \
    && rm -rf /var/lib/apt/lists/*
```

### Adding VSCode Extensions

```json
// .devcontainer/devcontainer.json
"extensions": [
  "your-extension-id"
]
```

## Troubleshooting

### Container Won't Start

```bash
docker ps
docker-compose ps
docker-compose logs devcontainer
```

### Dependencies Not Installing

```bash
cd backend && pip3 install --user -r requirements.txt
cd frontend && npm install
```

### Database Connection Refused

```bash
docker-compose up app-db
docker network ls
```

### File Permission Issues

```bash
id -u  # Check your UID -- should be 1000
# If not, modify .devcontainer/Dockerfile with your UID
```

## Security Considerations

### Non-Root User

Always develop as `lifted` user (UID 1000), never root.

### Exposed Ports (Development Only)

- 3000 (frontend)
- 8000 (backend)
- 5432 (database)

### Secrets

**Never commit:**
- `.env` files
- Database passwords (use environment variables)
- API keys
