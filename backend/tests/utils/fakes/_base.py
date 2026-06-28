"""Generic in-memory repository base for the aggregate-repo fakes.

A subclass binds `T`/`ID` to a concrete aggregate and its typed id and adds
only the domain-specific finders; `save` / `find_by_id` are inherited.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Protocol, override

from src.domain.shared.repo import Repo


class _HasUuidValue(Protocol):
    @property
    def value(self) -> uuid.UUID: ...


class _HasTypedId(Protocol):
    @property
    def id(self) -> _HasUuidValue: ...


class InMemoryRepo[T: _HasTypedId, ID: _HasUuidValue](Repo[T, ID], ABC):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, T] = {}

    @override
    @abstractmethod
    def next_identity(self) -> ID: ...

    @override
    def save(self, entity: T, /) -> None:
        self._store[entity.id.value] = entity

    @override
    def find_by_id(self, entity_id: ID, /) -> T | None:
        return self._store.get(entity_id.value)
