"""Material entity and its typed identity Value."""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import override

# ---------------------------------------------------------------------------
# Typed identity Value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaterialId:
    """Typed identity Value for Material."""

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Standard Types
# ---------------------------------------------------------------------------


class MaterialCategory(StrEnum):
    GLASS = "glass"
    PLASTIC = "plastic"
    METAL = "metal"
    PAPER = "paper"
    ORGANIC = "organic"
    HAZARDOUS = "hazardous"
    ELECTRONIC = "electronic"
    TEXTILE = "textile"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Material entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Material:
    """Material aggregate root (single-entity aggregate at MVP)."""

    id: MaterialId
    canonical_name: str
    slug: str
    category: MaterialCategory
    parent_id: MaterialId | None = None

    def __post_init__(self) -> None:
        if not self.slug:
            raise ValueError("slug must be non-empty")
        if not self.canonical_name:
            raise ValueError("canonical_name must be non-empty")


# ---------------------------------------------------------------------------
# MaterialAlias Value (describes a Material, no identity of its own)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaterialAlias:
    """Alias entry for a Material.

    A Value that describes how a user might refer to a Material.
    Identity belongs to the parent Material.
    """

    material_id: MaterialId
    alias: str
    weight: int = field(default=1)

    def __post_init__(self) -> None:
        if not self.alias:
            raise ValueError("alias must be non-empty")
        if self.weight < 1:
            raise ValueError("weight must be >= 1")
