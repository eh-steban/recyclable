# Multi-stage Dockerfile for the Python research worker.
# Single source of truth for deps: pyproject.toml + uv.lock.
#
# Stages: base (uv + python) -> dev (hot reload) | runner (Railway prod).

# ---------- base ----------
FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------- dev ----------
FROM base AS dev
ENV LOG_LEVEL=DEBUG

# Run as a non-root user whose uid matches the host developer (1000 by
# default). The source is bind-mounted, so files the container writes
# (.pytest_cache, syrupy __snapshots__) are then owned by the host user
# rather than root -- otherwise `scripts/wt remove` cannot delete the
# worktree without sudo. Override USER_UID/USER_GID at build time when the
# host uid differs.
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid "${USER_GID}" appuser \
    && useradd --create-home --uid "${USER_UID}" --gid "${USER_GID}" appuser

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra dev

# Source is bind-mounted by docker-compose; this COPY is a parity fallback.
COPY . .

# appuser must own the venv (runtime uv installs) and /app before the
# bind mount shadows it.
RUN chown -R appuser:appuser /opt/venv /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- runner (prod / Railway) ----------
FROM base AS runner

RUN useradd -m -u 1000 appuser

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY --chown=appuser:appuser . .

USER appuser

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD curl --fail http://localhost:${PORT}/health || exit 1

# Single-process start. Override with `python -m src.cli ...` for one-off jobs.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
