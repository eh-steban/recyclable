"""Generic repository port for the shared kernel.

Positional-only markers on `save` and `find_by_id` allow concrete repos
to use their own parameter names without suppression.
"""

from typing import Protocol


class Repo[T, ID](Protocol):
    def next_identity(self) -> ID: ...

    def save(self, entity: T, /) -> None: ...

    def find_by_id(self, entity_id: ID, /) -> T | None: ...
