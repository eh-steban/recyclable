---
paths:
  - ".devcontainer/*"
  - "**/Dockerfile"
  - "docker-compose.yaml"
  - "docker-compose.yml"
---
# Docker Compose Configuration

Local development orchestration with Docker Compose. **Local only** -- production runs on Vercel + Railway + Neon, not on Compose.

## Files

| File | Purpose |
|---|---|
| `docker-compose.yaml` (repo root) | Prod-shape local stack: web + worker + Postgres |
| `.devcontainer/docker-compose.yml` | Dev-container overlay (Node + Python + DB client); entered via `./bin/dev` |
| `.devcontainer/Dockerfile` | Devcontainer image |

The root file is what `docker compose up` uses by default. The devcontainer file is loaded by `./bin/dev` (and by any Devcontainer-spec-aware tool) when entering the unified dev container.

## Production Services (`docker-compose.yaml`)

```yaml
services:
  app-frontend:    # Next.js on port 3000 (target: dev)
  app-backend:     # Python worker / admin API on port 8000 (target: dev)
  app-db:          # Postgres 16 on port 5432
```

### Hot Reload

- `app-frontend` mounts `./frontend` and isolates `/app/node_modules` + `/app/.next` so the host's `node_modules` cannot collide with the container's.
- `app-backend` mounts `./backend` for hot reload via uvicorn `--reload`.

### Healthchecks

- `app-db` exposes `pg_isready` so dependent services wait for it via `depends_on.condition: service_healthy`.
- App Dockerfiles include `HEALTHCHECK` for prod-parity testing.

### Volumes

| Type | Use |
|---|---|
| Named volume (`app-db-data`) | Postgres persistence between restarts |
| Bind mount (`./frontend`, `./backend`) | Hot reload |
| Anonymous volume (`/app/node_modules`, `/app/.next`) | Container-only, prevents host/container conflict |

### Environment

Read from `.env` at repo root (gitignored). Template in `.env.example`. `ANTHROPIC_API_KEY` is **required** -- compose will fail loudly if missing rather than starting silently broken.

## Networking

Default bridge network. Service-to-service:

```
app-frontend  -> app-backend:8000   (rare; only admin endpoints)
app-frontend  -> app-db:5432        (primary user path)
app-backend   -> app-db:5432        (ingestion writes)
```

The user-path `/api/ask` lives in `app-frontend` (Next.js) and reads Postgres directly. `app-backend` is for ingestion + admin only.

## Common Operations

```bash
# Start all services
docker compose up

# Start specific service
docker compose up app-frontend

# Rebuild after dependency changes
docker compose up --build app-backend

# View logs
docker compose logs -f app-frontend

# Stop all services
docker compose down

# Stop and remove volumes (fresh DB)
docker compose down -v

# Run a one-off worker command
docker compose run --rm app-backend python -m app.cli ingest --source <url>

# Open psql against the local DB
docker compose exec app-db psql -U recyclable -d recyclable
```

## Production Mapping (Reference)

The local Compose shape mirrors the prod topology, but each service deploys to a different platform:

| Local Compose | Prod | Build From |
|---|---|---|
| `app-frontend` | Vercel | Repo root, Vercel auto-detects Next.js (ignores `frontend/Dockerfile`) |
| `app-backend` | Railway | `backend/Dockerfile` target `runner` |
| `app-db` | Neon | Managed; not built |

Differences from local:
- Vercel handles SSG + edge caching automatically. Recycling pages are statically generated and revalidated only when the ingestion-apply action fires (via `revalidatePath`) -- no time-based ISR.
- Railway sets `$PORT` -- `runner` stage respects it.
- Neon connection string includes `?sslmode=require` -- env var difference only.
- No bind mounts in prod; code is baked into images.

## Troubleshooting

### Port Already in Use

```bash
lsof -i :3000  # or :8000, :5432
```

### Frontend Cannot Reach DB

- Check `DATABASE_URL` in env. From inside the container the host is `app-db`, **not** `localhost`.
- `docker compose ps` -- is `app-db` healthy?

### Hot Reload Not Working

- Frontend: ensure `./frontend` is mounted; `next.config.ts` may need adjustments on WSL2.
- Backend: uvicorn `--reload` requires source mount; verify with `docker compose exec app-backend ls /app`.

### Permission Issues on Mounted Volumes

```bash
id -u  # should be 1000 to match container user
```
If different, either run `chown -R 1000:1000 ./frontend ./backend` or rebuild images with your UID.
