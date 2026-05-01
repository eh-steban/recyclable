"""Shared test fixtures.

Migration tests and integration tests that need a real Postgres connection
use the DATABASE_URL environment variable (pointing at the compose app-db).

If DATABASE_URL is not set, those tests are skipped.
"""
from __future__ import annotations

import os

import pytest

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable",
)


@pytest.fixture(scope="session")
def db_url() -> str:
    return DATABASE_URL
