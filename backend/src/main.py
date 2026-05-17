"""FastAPI application entry point.

Startup checks (run when the ASGI lifespan starts):
  - ANTHROPIC_API_KEY must be non-empty in the environment.
  - DATABASE_URL must be non-empty in the environment.

Both are read from os.environ directly so that an unset var is caught
even if config.py provides a default (D6: boot check must not be made
inert by a settings-object fallback). Per spec § Boot-check specification.

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
import os
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
    """Raise RuntimeError with a descriptive message on missing env vars.

    Reads DATABASE_URL and ANTHROPIC_API_KEY from os.environ directly so
    that the check cannot be bypassed by a settings-object default value.
    Inspects both vars before raising so a single error enumerates every
    absent variable (per spec § Boot-check specification D6).
    """
    errors: list[str] = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append(
            "ANTHROPIC_API_KEY is not set or is empty. "
            "Export the key before starting the server."
        )
    if not os.environ.get("DATABASE_URL"):
        errors.append(
            "DATABASE_URL is not set or is empty. "
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
