---
paths:
  - ".devcontainer/*"
  - "**/Dockerfile"
  - "docker-compose.yaml"
  - "docker-compose.yml"
---

# Container Architecture

Container structure, optimization, and best practices for both local
Compose parity and the prod targets (Vercel, Railway, Neon).

## Design philosophy

1. **Minimal production images** -- only runtime dependencies in `runner`
   stages.
2. **Security first** -- non-root users, no secrets baked in.
3. **Layer caching** -- dependencies copied before source.
4. **Reproducibility** -- pin versions, use lock files (`package-lock.json`,
   `requirements.txt`).
5. **Multi-stage** -- shared `builder` for compile, separate `dev`
   (hot reload) and `runner` (prod).

## Production containers

### Frontend (Next.js)

**File:** `frontend/Dockerfile`
**Stages:** `deps` → `dev` | `builder` → `runner`
**Production deploy:** Vercel (Vercel ignores this Dockerfile and builds
Next.js itself).

The `runner` stage exists for prod-parity testing and any future
self-host. It expects `next.config.ts` to set `output: 'standalone'`
so only the standalone bundle ships.

### Backend (Python worker)

**File:** `backend/Dockerfile`
**Stages:** `builder` → `dev` | `runner`
**Production deploy:** Railway (uses `runner` stage, respects `$PORT`).

Key features:

- Venv copied across stages -- runner has no compilers.
- Non-root `appuser` (UID 1000).
- `HEALTHCHECK` against `/health`.
- Single uvicorn process; one-off CLI invoked via `docker compose run`
  or Railway's "run command" override.

## Development container

**File:** `.devcontainer/Dockerfile`
Unified Node + Python image, entered via `./bin/dev` (or any tool that
speaks the open Devcontainer spec).

Features:

- UID 1000 matches typical host user (volume permissions).
- Both language stacks for cross-service editing.
- Claude Code CLI baked in.

## User strategy

| Container | User | UID | Rationale |
|-----------|------|-----|-----------|
| Devcontainer | `lifted` | 1000 | Matches host user for volume permissions |
| Backend runner | `appuser` | 1000 | Non-root |
| Frontend runner | `node` | 1000 | Built-in Node image user |

Never run production containers as root.

## Best practices

### Dependency installation order

```dockerfile
# ✅ Good - dependencies cached separately
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# ❌ Bad - dependencies reinstall on any code change
COPY . .
RUN npm ci
```

### Clean up after install

```dockerfile
# ✅ Good - single RUN layer, cleanup
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*
```

### Use BuildKit cache mounts

```dockerfile
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

Speeds up rebuilds without inflating final image size.

### Use .dockerignore

`frontend/.dockerignore` and `backend/.dockerignore` exist -- update them
when adding new caches or build artifacts.

## Volume strategy

### Development

```yaml
- ./frontend:/app           # source (hot reload)
- /app/node_modules         # anonymous, container-only
- /app/.next                # anonymous, container-only
- ./backend:/app            # source (hot reload)
```

### Production

- No source bind mounts -- code is baked into images.
- Postgres persistence is managed by Neon, not local volumes.
- Vercel handles its own caching.

## Healthchecks

Both production stages include a `HEALTHCHECK`. Keep them simple (single
curl/wget) -- complex healthchecks become their own debug surface.

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD curl --fail http://localhost:${PORT}/health || exit 1
```

The Next.js app should expose a trivial `/api/health` route handler that
does not touch the DB. The worker should expose a `/health` route that
does -- if the DB is unreachable, Railway should restart the worker.

## Build-time secrets

Never `COPY .env` into an image. Use:

- Vercel project env settings.
- Railway service env variables.
- BuildKit `--secret` for build-time-only values, never runtime.

If you find yourself wanting to bake an API key into a layer, stop -- you
are about to leak it to anyone with `docker history`.
