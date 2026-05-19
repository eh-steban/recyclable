"""Fixtures for migration tests.

Migration tests (up/down cycles) run DDL that cannot live inside a
rolled-back transaction, so they do not use the shared ``db_session``
rollback fixture.  They operate directly against the test database via
their own engines and alembic configs.

No shared fixtures are defined here beyond the doc comment; each
migration test module provides its own module-scoped ``alembic_cfg`` and
``engine`` fixtures that restore the database to ``head`` in teardown so
non-migration tests that follow always see a fully migrated schema.
"""
