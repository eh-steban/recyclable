"""FastAPI application entry point.

Startup checks (run when the ASGI lifespan starts):
  - ANTHROPIC_API_KEY must be non-empty.
  - DATABASE_URL must be non-empty.

On failure the lifespan raises RuntimeError with a descriptive message.
uvicorn surfaces the traceback and exits non-zero; TestClient surfaces
it as an exception when raise_server_exceptions=True.

Reconciliation note (Phase 6): the plan text named src/api/main.py as
the file to receive routers and boot checks. The existing entry point
is src/main.py (per .claude/CLAUDE.md quick reference:
`uvicorn src.main:app` and per docker-compose). To avoid breaking the
uvicorn invocation, routers and boot checks live here instead.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes.ask import router as ask_router
from src.api.routes.pages import router as pages_router
from src.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO)
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan -- boot checks run before the server accepts requests.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    _check_boot_config()
    logger.info("startup checks passed")
    yield
    logger.info("shutdown")


def _check_boot_config() -> None:
    """Raise RuntimeError with a descriptive message on missing config."""
    errors: list[str] = []
    if not settings.anthropic_api_key:
        errors.append(
            "ANTHROPIC_API_KEY is not set (empty string). "
            "Export the key before starting the server."
        )
    if not settings.database_url:
        errors.append(
            "DATABASE_URL is not set (empty string). "
            "Export a valid Postgres URL before starting the server."
        )
    if errors:
        for msg in errors:
            logger.critical("boot check failed: %s", msg)
        raise RuntimeError(
            "Missing required configuration:\n" + "\n".join(errors)
        )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Recyclable Backend",
    version="0.1.0",
    lifespan=_lifespan,
)

app.include_router(ask_router)
app.include_router(pages_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
