"""In-memory implementation of MaterialAliasSearch for tests."""

from src.domain.knowledge_base.material import MaterialId


class MemMaterialAliasSearch:
    """Preset-list-backed MaterialAliasSearch satisfying the domain Protocol.

    Constructed with a preset list of (MaterialId, float) pairs representing
    per-material max trigram similarity scores, already ordered descending
    and filtered to similarity > 0.

    Honors the MaterialAliasSearch contract:
    - Results are ordered by max_sim descending.
    - Only materials with similarity > 0 are included.
    - Multiple aliases for the same material are pre-collapsed to their
      max similarity (the caller constructs the list that way).

    The constructor asserts there are no duplicate MaterialId values in
    the preset rows. The port contract is per-material-collapsed; a
    mis-built test that passes duplicate rows would silently violate it.
    """

    _rows: list[tuple[MaterialId, float]]

    def __init__(
        self,
        rows: list[tuple[MaterialId, float]],
    ) -> None:
        seen: set[MaterialId] = set()
        for mat_id, _ in rows:
            assert mat_id not in seen, (
                f"MemMaterialAliasSearch: duplicate MaterialId {mat_id!r} in "
                "preset rows -- the port contract requires one row per "
                "material (pre-collapsed to max similarity)."
            )
            seen.add(mat_id)
        self._rows = rows

    def search(
        self,
        query_text: str,  # noqa: ARG002
    ) -> list[tuple[MaterialId, float]]:
        """Return the preset rows regardless of query_text."""
        return list(self._rows)
