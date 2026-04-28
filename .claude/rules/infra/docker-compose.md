---
paths:
  - ".devcontainer/*"
  - "**/Dockerfile"
  - "docker-compose.yaml"
  - ".github/workflows/*"
---
# Docker Compose Configuration

Local development orchestration with Docker Compose.

## Overview

Two Docker Compose files work together:

1. **`docker-compose.yaml`** (root) -- Production services (backend, frontend, database)
2. **`.devcontainer/docker-compose.yml`** -- Development container overlay

When using VSCode devcontainer, both are loaded together to provide:
- Unified dev environment (Node + Python)
- Production-like service definitions (database, networking)

## Production Services (docker-compose.yaml)

### Service Definitions

```yaml
services:
  app-frontend:     # React app on port 3000
  app-backend:      # FastAPI on port 8000
  app-db:           # PostgreSQL on port 5432
```

### Service Details

#### Frontend
- Hot reload with mounted source code
- Anonymous volume for `node_modules` (prevents host/container conflict)
- Vite dev server bound to `0.0.0.0`

#### Backend
- Connects to database via internal network (`app-db:5432`)
- Hot reload via uvicorn `--reload`

#### Database
- Named volume for data persistence
- Init scripts run on first startup
- Exposed port for direct access during development

### Volumes

**Persistence Strategy:**
- **Named volumes:** Data that should persist between restarts (database)
- **Bind mounts:** Code for hot reload (`./backend`, `./frontend`)
- **Anonymous volumes:** Dependencies that shouldn't sync with host (`/app/node_modules`)

## Development Container (.devcontainer/docker-compose.yml)

**Key Points:**
- Mounts entire project (not just service subdirectories)
- Runs indefinitely (`sleep infinity`) for interactive development
- Connects to database from root compose file
- Elevated privileges for debugging (ptrace, seccomp)

## Networking

All services on the same Docker network:

```
app-frontend    → app-backend:8000
app-backend     → app-db:5432
devcontainer    → app-db:5432
```

**Service Discovery:**
- Containers reference each other by service name
- Docker's embedded DNS resolves service names to container IPs

### Port Mapping

| Service | Internal | External | Purpose |
|---------|----------|----------|---------|
| Frontend | 3000 | 3000 | Browser access |
| Backend | 8000 | 8000 | API access |
| Database | 5432 | 5432 | Direct queries |

## Common Operations

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up backend

# Rebuild after dependency changes
docker-compose up --build backend

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v

# Execute command in running container
docker-compose exec backend bash
```

## Environment Variables

```bash
# .env file (not committed)
POSTGRES_USER=appuser
POSTGRES_PASSWORD=apppassword
DATABASE_URL=postgresql+psycopg://appuser:apppassword@app-db:5432/app_db
```

```yaml
# docker-compose.yaml
services:
  app-backend:
    env_file: .env
```

## Troubleshooting

### Port Already in Use

```bash
lsof -i :8000  # Find process using port 8000
```

### Database Connection Refused

```bash
docker-compose ps
docker-compose logs app-db
docker-compose restart app-db
```

### Hot Reload Not Working

```bash
docker-compose up --build [service]
docker-compose exec [service] ls -la
```

## Production Readiness Checklist

- [ ] Remove volume mounts (code baked into image)
- [ ] Use secrets for passwords (not environment variables)
- [ ] Add resource limits (memory, CPU)
- [ ] Enable health checks
- [ ] Remove exposed ports for internal services
- [ ] Add restart policies (`restart: unless-stopped`)
