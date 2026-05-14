"""Exception-translation helpers for SQL repo implementations.

Each repo's write path catches SQLAlchemy framework exceptions and
re-raises as domain exceptions so the application layer never imports
sqlalchemy.exc (per the DDD layering rules).
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError, OperationalError

from src.domain.exceptions import (
    DuplicateAggregateError,
    RepositoryConcurrencyError,
)


@contextmanager
def translate_repo_exceptions(
    aggregate_name: str, aggregate_id: str
) -> Generator[None]:
    """Translate SQLAlchemy write exceptions to domain exceptions.

    IntegrityError  -> DuplicateAggregateError(aggregate_name, aggregate_id)
    OperationalError -> RepositoryConcurrencyError(str(exc))
    """
    try:
        yield
    except IntegrityError as exc:
        raise DuplicateAggregateError(aggregate_name, aggregate_id) from exc
    except OperationalError as exc:
        raise RepositoryConcurrencyError(str(exc)) from exc
