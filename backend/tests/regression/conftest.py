"""Regression-suite fixtures: seeded test DB + in-process FastAPI app.

These fixtures seed denver-easy and expose an ASGI client over the app.
They make no LLM call themselves: the offline pipeline tests
(test_ask_offline.py) inject a fake LLM and run by default, while the live
Sonnet smoke eval (test_smoke_eval.py) is opt-in behind RUN_LIVE_EVALS. DB
connectivity skips are handled by provision_test_db (root conftest).
"""

from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.cli.seed import run_seed
from src.main import app


@pytest.fixture(scope="session")
def regression_db_session(db_engine: Engine) -> Generator[Session]:
    """Seed denver-easy, install DB override, yield session, roll back.

    Rows are never committed; the outer transaction is rolled back on
    teardown, leaving recyclable_test clean.  The ``get_db`` override
    is set here so it lives for the full session rather than being
    installed and popped for every function-scoped ``asgi_client``.
    """
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)

    def _get_test_db() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_db] = _get_test_db
    try:
        run_seed("denver-easy", session)
        session.flush()
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture(scope="session")
def latency_ms_values() -> list[int]:
    """Return the shared latency accumulator for this test session."""
    return []


@pytest.fixture()
async def asgi_client(
    regression_db_session: Session,
) -> AsyncGenerator[httpx.AsyncClient]:
    """Yield an httpx.AsyncClient pointing at the in-process FastAPI app."""
    # The lifespan is NOT started: httpx.ASGITransport does not trigger the
    # FastAPI lifespan by default, bypassing the boot check.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client
