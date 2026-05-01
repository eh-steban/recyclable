"""Shared test fixtures.

Integration tests that need a real Postgres connection consume the `db_url`
fixture, which probes connectivity and skips the test (rather than failing)
when the database is unreachable.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable",
)


@pytest.fixture(scope="session")
def db_url() -> str:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect():
            pass
        engine.dispose()
    except OperationalError as exc:
        pytest.skip(f"Postgres unreachable at {DATABASE_URL}: {exc}", allow_module_level=True)
    return DATABASE_URL
