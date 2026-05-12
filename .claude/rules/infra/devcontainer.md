---
paths:
  - ".devcontainer/**"
---

# Development Container (Devcontainer)

Unified development environment with Node.js (24) and Python (3.14).
One container, full monorepo. Follows the open
[Devcontainer spec][devcontainer-spec] -- editor-agnostic. The user enters
the container via `./bin/dev` from a tmux/nvim setup; other editors that
speak the spec (JetBrains Gateway, GitHub Codespaces, etc.) can also
consume `.devcontainer/devcontainer.json` directly.

[devcontainer-spec]: https://containers.dev/

## Entry point

The canonical way to enter the container is `./bin/dev` from the repo
root. The script is idempotent: if the container is already running it
just `exec`s into it; if not, it brings it up first.

```bash
./bin/dev              # interactive bash shell
./bin/dev pytest -q    # one-shot command
./bin/dev --rebuild    # rebuild image, then enter
```

Editor-aware tools (the open-source `devcontainer` CLI, GitHub Codespaces,
JetBrains Gateway, etc.) can also consume
`.devcontainer/devcontainer.json` directly. Both paths land in the same
container.

## Files

| File | Purpose |
| --- | --- |
| `.devcontainer/Dockerfile` | Devcontainer image |
| `.devcontainer/docker-compose.yml` | Devcontainer service definition |
| `.devcontainer/devcontainer.json` | Devcontainer spec manifest (editor-agnostic; consumed by the open-source `devcontainer` CLI, JetBrains, GitHub Codespaces, etc.) |
| `.devcontainer/setup.sh` | postCreateCommand hook |

## Architecture

```text
ubuntu:22.04
├── Node.js 24       # Frontend (Next.js)
├── Python 3.14      # Worker
├── PostgreSQL client
├── Claude Code CLI  # Persistent auth + history
└── Build tools
```

### Why unified

Single container for the whole monorepo, no context switching, shared
git/lint/format tools, faster iteration. Production images stay slim
(separate `frontend/` and `backend/` Dockerfiles).

## Compose file layering

`devcontainer.json` references `.devcontainer/docker-compose.yml` for the
devcontainer service. The root `docker-compose.yaml` is a separate concern
-- run it manually for the prod-shape stack.

To get the devcontainer talking to the local Postgres, either:

- Run `docker compose up app-db` from the host before entering the
  devcontainer, **or**
- Add the root compose file to `dockerComposeFile` in `devcontainer.json`
  and depend on `app-db`.

## User and permissions

```dockerfile
# UID 1000 to match typical host user
RUN useradd -m -u 1000 -s /bin/bash lifted
```

If your host UID is not 1000:

```bash
id -u
# If different, modify .devcontainer/Dockerfile
```

## Volumes

| Mount | Purpose |
| --- | --- |
| `..:/workspaces/myproject:cached` | Project root (`:cached` optimizes I/O on macOS/Windows) |
| `~/.claude:/home/lifted/.claude` | Claude Code auth + history persistence |
| `~/.container-bashrc:/home/lifted/.bashrc` | Shell history |

`node_modules` is **not** mounted -- runs `npm install` in container after
creation to avoid platform-specific binary conflicts.

## Workflows

### Starting services

After entering the container via `./bin/dev` (in two separate tmux panes /
terminal windows):

#### Manual (recommended for development)

```bash
# Pane 1: Frontend
cd frontend && npm run dev

# Pane 2: Worker
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Full control, separate logs, easy to restart individual services.

#### Compose (prod parity)

```bash
docker compose up
```

### Database

```bash
psql postgresql://recyclable:recyclable_dev@app-db:5432/recyclable
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

### Tests

```bash
cd backend && pytest
cd frontend && npm test
```

## Rebuilding

Rebuild when you change:

- `.devcontainer/Dockerfile`
- `.devcontainer/devcontainer.json`
- System dependencies (apt packages)

Don't rebuild for:

- App code (hot reload).
- Python/npm dep changes (reinstall in container).

```bash
./bin/dev --rebuild
# or directly:
docker compose \
  -f docker-compose.yaml \
  -f .devcontainer/docker-compose.yml \
  up -d --build devcontainer
```

## Customization

```dockerfile
# .devcontainer/Dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    your-package-here \
    && rm -rf /var/lib/apt/lists/*
```

## Troubleshooting

### Container won't start

```bash
docker ps
docker compose ps
docker compose logs devcontainer
```

### Dependencies not installing

```bash
cd backend && pip3 install --user -r requirements.txt
cd frontend && npm install
```

### Database connection refused

```bash
docker compose up app-db
docker network ls
```

### File permission issues

```bash
id -u  # Check your UID -- should be 1000
```

## Security

### Non-root user

Always develop as `lifted` user (UID 1000), never root.

### Exposed ports (development only)

- 3000 (frontend)
- 8000 (backend)
- 5432 (database)

### Secrets

Never commit `.env` files, database passwords, or API keys. `.env` is
gitignored; template lives in `.env.example`.
