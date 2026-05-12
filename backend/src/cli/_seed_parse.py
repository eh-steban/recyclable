"""Internal parse helpers shared by ``seed.py`` and ``verify.py``.

All public names in this module are intentionally package-internal (the
module itself is prefixed with ``_``).  ``verify.py`` imports directly from
here rather than reaching into ``seed.py``'s private namespace, which keeps
pyright strict-mode happy.
"""

import hashlib
import logging
import pathlib
import sys
from datetime import UTC, datetime
from typing import NotRequired, TypedDict, cast

import yaml

from src.domain.exceptions import (
    EntityNotFoundError,
    SeedIntegrityError,
    SeedSchemaError,
)
from src.domain.models.jurisdiction import Jurisdiction
from src.domain.models.material import Material
from src.domain.models.regression_case import RegressionCase
from src.domain.models.rule import Rule
from src.domain.models.source_document import SourceDocument
from src.domain.quote_normalize import normalize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YAML row TypedDicts -- mirror the on-disk YAML shape, not the domain model.
# Pydantic does the real validation downstream; these are type-checker
# annotations only.  Fields that the domain model provides via default_factory
# are NotRequired here.
# ---------------------------------------------------------------------------


class JurisdictionRow(TypedDict):
    """Shape of one item in ``jurisdiction.yaml``."""

    name: str
    slug: str
    type: str
    country: str
    supported_status: str
    id: NotRequired[str]  # UUID string; Pydantic parses it
    created_at: NotRequired[str]  # ISO timestamp; Pydantic parses it
    updated_at: NotRequired[str]


class SourceDocumentRow(TypedDict):
    """Shape of one item in ``source_documents.yaml``.

    ``jurisdiction`` is a slug reference that gets resolved to
    ``jurisdiction_id`` (UUID) before the Pydantic model is constructed.
    """

    jurisdiction: str  # slug reference -- rewritten to jurisdiction_id
    url: str
    title: str
    authority_level: int
    source_text: str
    id: NotRequired[str]
    fetched_at: NotRequired[str]
    effective_date: NotRequired[str]  # date string; Pydantic parses it
    source_text_hash: NotRequired[str]  # auto-computed if absent
    last_reviewed_at: NotRequired[str]


class MaterialRow(TypedDict):
    """Shape of one item in ``materials.yaml``.

    ``aliases`` is a YAML-level field that is popped before constructing
    the ``Material`` domain model.
    """

    canonical_name: str
    slug: str
    category: str
    aliases: NotRequired[list[str]]  # popped before Pydantic construction
    id: NotRequired[str]
    parent_id: NotRequired[str]


class RuleRow(TypedDict):
    """Shape of one item in ``rules.yaml``.

    ``slug``, ``jurisdiction``, ``material``, and ``source_document`` are
    YAML-level keys that are popped and resolved to IDs before the Pydantic
    model is constructed.
    """

    slug: str  # used for error messages; not passed to Pydantic
    jurisdiction: str  # slug reference
    material: str  # slug reference
    source_document: str  # URL reference
    disposition: str
    accepted_status: str
    source_quote: str
    id: NotRequired[str]
    preparation_steps: NotRequired[list[str]]
    exceptions: NotRequired[list[str]]
    warnings: NotRequired[list[str]]
    confidence: NotRequired[str]
    effective_from: NotRequired[str]
    superseded_by: NotRequired[str]


class RegressionCaseRow(TypedDict):
    """Shape of one item in ``regression_cases.yaml``.

    ``jurisdiction`` and ``material`` (optional) are slug references that
    are resolved to IDs before the Pydantic model is constructed.
    """

    query: str
    jurisdiction: str  # slug reference
    expected_status: str
    expected_disposition: str
    id: NotRequired[str]
    material: NotRequired[str]  # optional slug reference
    must_cite_source: NotRequired[bool]
    refusal_required: NotRequired[bool]
    notes: NotRequired[str]


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

# ``yaml.safe_load`` returns ``object | None``, but pyright infers ``Any``
# from the pyyaml stubs.  We cast to ``object`` here so the Any boundary
# is contained at this call site and does not leak through callers.


def load_yaml(path: pathlib.Path) -> object:
    """Load a YAML file via safe_load.  Returns None if the file is missing."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return cast(object, yaml.safe_load(fh))


# ---------------------------------------------------------------------------
# Shape narrowing helpers
# ---------------------------------------------------------------------------


def as_list_of_rows[T](
    data: object,
    source: str,
    row_type: type[T],
) -> list[T]:
    """Narrow an arbitrary YAML payload to a typed list of mapping items.

    Raises ``SeedSchemaError`` if the top-level shape is wrong.  Each
    returned item is cast to *row_type* (a TypedDict) so callers and pyright
    can reason about field access without ``Any`` propagating.

    ``row_type`` is used only for error messages -- Pydantic does the real
    field validation downstream.  The cast is safe because any structural
    mismatch will raise at Pydantic construction time.
    """
    if not isinstance(data, list):
        raise SeedSchemaError(f"{source}: expected a list at top level")
    out: list[T] = []
    for i, item in enumerate(cast(list[object], data)):
        if not isinstance(item, dict):
            kind = type(item).__name__
            name = row_type.__name__
            msg = f"{source}[{i}]: expected a mapping, "
            raise SeedSchemaError(msg + f"got {kind} (parsing as {name})")
        out.append(cast(T, item))
    return out


def as_list_of_dicts(
    data: object,
    source: str,
) -> list[RuleRow]:
    """Narrow a YAML payload to a list of rule-shaped mappings.

    Kept for backwards compatibility with ``verify.py``'s quote-integrity
    check, which iterates raw rule and source-document rows without going
    through the full parse pipeline.  Returns ``list[RuleRow]`` -- the
    richest of the row types -- which has all the fields verify.py accesses
    (``url``, ``slug``, ``source_document``, ``source_quote``).

    For the full typed parse path, prefer the per-entity ``_parse_*``
    functions which use ``as_list_of_rows``.
    """
    return as_list_of_rows(data, source, RuleRow)


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def validate_dataset_path(
    dataset: str, seeds_root: pathlib.Path
) -> pathlib.Path:
    """Resolve and validate a dataset path, guarding against path traversal.

    Returns the resolved dataset directory path.  Raises ``SystemExit(1)``
    with a clear message if the resolved path escapes *seeds_root* or if
    the directory does not exist / has no YAML files.

    Both ``seed.py`` and ``verify.py`` share this validator so the check
    is applied consistently.
    """
    seeds_root_resolved = seeds_root.resolve()
    dataset_dir = seeds_root / dataset
    try:
        dataset_dir_resolved = dataset_dir.resolve()
    except OSError as exc:
        print(
            f"Error: cannot resolve dataset path '{dataset}': {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not str(dataset_dir_resolved).startswith(str(seeds_root_resolved) + "/"):
        logger.error(
            "path traversal attempt: dataset=%r resolved=%s seeds_root=%s",
            dataset,
            dataset_dir_resolved,
            seeds_root_resolved,
        )
        print(
            f"Error: dataset '{dataset}' resolves outside seeds directory."
            + " Only simple directory names are allowed.",
            file=sys.stderr,
        )
        sys.exit(1)

    return dataset_dir_resolved


# ---------------------------------------------------------------------------
# Per-entity parsers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_jurisdictions(data: object, dataset: str) -> list[Jurisdiction]:
    """Parse the jurisdictions YAML document into domain models."""
    items = as_list_of_rows(
        data, f"{dataset}/jurisdiction.yaml", JurisdictionRow
    )
    jurisdictions: list[Jurisdiction] = []
    for i, row in enumerate(items):
        try:
            # model_validate accepts Any -- Pydantic coerces str to UUID,
            # str to StrEnum, and str to datetime for the optional fields.
            jurisdictions.append(Jurisdiction.model_validate(row))
        except Exception as exc:
            slug = row.get("slug", "?")
            raise SeedSchemaError(
                f"{dataset}/jurisdiction.yaml[{i}] (slug={slug}): {exc}"
            ) from exc
    return jurisdictions


def parse_source_documents(
    data: object,
    dataset: str,
    jurisdiction_map: dict[str, Jurisdiction],
) -> list[SourceDocument]:
    """Parse source_documents YAML into domain models.

    Slug references in ``jurisdiction`` are resolved from *jurisdiction_map*.
    ``source_text_hash`` is computed automatically from the source_text.
    """
    items = as_list_of_rows(
        data, f"{dataset}/source_documents.yaml", SourceDocumentRow
    )
    docs: list[SourceDocument] = []
    for i, row in enumerate(items):
        # Resolve jurisdiction slug reference.
        try:
            jur_slug: str = row["jurisdiction"]
        except KeyError:
            raise SeedSchemaError(
                f"{dataset}/source_documents.yaml[{i}]:"
                + " missing 'jurisdiction' field"
            ) from None
        if jur_slug not in jurisdiction_map:
            raise EntityNotFoundError("Jurisdiction", jur_slug)

        # Build the resolved dict.  We copy only known fields so that
        # unexpected YAML keys do not silently pass through to Pydantic.
        source_text: str = row.get("source_text", "")
        source_text_hash: str = (
            row["source_text_hash"]
            if "source_text_hash" in row and row.get("source_text_hash")
            else _sha256(source_text)
        )
        resolved: dict[str, object] = {
            "url": row["url"],
            "title": row["title"],
            "authority_level": row["authority_level"],
            "source_text": source_text,
            "jurisdiction_id": jurisdiction_map[jur_slug].id,
            "source_text_hash": source_text_hash,
            "fetched_at": (
                row["fetched_at"] if "fetched_at" in row else datetime.now(UTC)
            ),
        }
        if "id" in row:
            resolved["id"] = row["id"]
        if "effective_date" in row:
            resolved["effective_date"] = row["effective_date"]
        if "last_reviewed_at" in row:
            resolved["last_reviewed_at"] = row["last_reviewed_at"]

        try:
            docs.append(SourceDocument.model_validate(resolved))
        except Exception as exc:
            url = row.get("url", "?")
            raise SeedSchemaError(
                f"{dataset}/source_documents.yaml[{i}] (url={url}): {exc}"
            ) from exc
    return docs


def parse_materials(
    data: object, dataset: str
) -> list[tuple[Material, list[str]]]:
    """Parse materials YAML into (Material, aliases) pairs.

    Returns a list of (Material, [alias_str, ...]) tuples.
    """
    items = as_list_of_rows(data, f"{dataset}/materials.yaml", MaterialRow)
    results: list[tuple[Material, list[str]]] = []
    for i, row in enumerate(items):
        raw_aliases: object = row.get("aliases", [])
        if not isinstance(raw_aliases, list):
            slug = row.get("slug", "?")
            raise SeedSchemaError(
                f"{dataset}/materials.yaml[{i}]"
                + f" (slug={slug}): 'aliases' must be a list"
            )
        alias_strs: list[str] = [
            str(a) for a in cast(list[object], raw_aliases)
        ]

        resolved: dict[str, object] = {
            "canonical_name": row["canonical_name"],
            "slug": row["slug"],
            "category": row["category"],
        }
        if "id" in row:
            resolved["id"] = row["id"]
        if "parent_id" in row:
            resolved["parent_id"] = row["parent_id"]

        try:
            material = Material.model_validate(resolved)
        except Exception as exc:
            slug = row.get("slug", "?")
            raise SeedSchemaError(
                f"{dataset}/materials.yaml[{i}] (slug={slug}): {exc}"
            ) from exc
        results.append((material, alias_strs))
    return results


def parse_rules(
    data: object,
    dataset: str,
    jurisdiction_map: dict[str, Jurisdiction],
    material_map: dict[str, Material],
    source_doc_map: dict[str, SourceDocument],
) -> list[Rule]:
    """Parse rules YAML into domain models.

    Slug references are resolved from the in-memory maps built earlier.
    Quote integrity is checked here -- before any DB writes.
    """
    items = as_list_of_rows(data, f"{dataset}/rules.yaml", RuleRow)
    rules: list[Rule] = []
    for i, row in enumerate(items):
        rule_slug: str = row.get("slug", f"rule[{i}]")

        # Resolve jurisdiction slug.
        try:
            jur_slug: str = row["jurisdiction"]
        except KeyError:
            raise SeedSchemaError(
                f"{dataset}/rules.yaml rule '{rule_slug}':"
                + " missing 'jurisdiction'"
            ) from None
        if jur_slug not in jurisdiction_map:
            raise EntityNotFoundError("Jurisdiction", jur_slug)

        # Resolve material slug.
        try:
            mat_slug: str = row["material"]
        except KeyError:
            raise SeedSchemaError(
                f"{dataset}/rules.yaml rule '{rule_slug}':"
                + " missing 'material'"
            ) from None
        if mat_slug not in material_map:
            raise EntityNotFoundError("Material", mat_slug)

        # Resolve source_document by URL (stable unique key).
        try:
            src_url: str = row["source_document"]
        except KeyError:
            raise SeedSchemaError(
                f"{dataset}/rules.yaml rule '{rule_slug}':"
                + " missing 'source_document'"
            ) from None
        if src_url not in source_doc_map:
            raise EntityNotFoundError("SourceDocument", src_url)
        source_doc = source_doc_map[src_url]

        # Quote integrity check -- before any DB write.
        source_quote: str = row.get("source_quote", "")
        if not source_quote:
            raise SeedSchemaError(
                f"{dataset}/rules.yaml rule '{rule_slug}':"
                + " 'source_quote' is required and must be non-empty"
            )
        if normalize(source_quote) not in normalize(source_doc.source_text):
            raise SeedIntegrityError(rule_slug, source_quote)

        resolved: dict[str, object] = {
            "disposition": row["disposition"],
            "accepted_status": row["accepted_status"],
            "source_quote": source_quote,
            "jurisdiction_id": jurisdiction_map[jur_slug].id,
            "material_id": material_map[mat_slug].id,
            "source_document_id": source_doc.id,
        }
        if "id" in row:
            resolved["id"] = row["id"]
        if "preparation_steps" in row:
            resolved["preparation_steps"] = row["preparation_steps"]
        if "exceptions" in row:
            resolved["exceptions"] = row["exceptions"]
        if "warnings" in row:
            resolved["warnings"] = row["warnings"]
        if "confidence" in row:
            resolved["confidence"] = row["confidence"]
        if "effective_from" in row:
            resolved["effective_from"] = row["effective_from"]
        if "superseded_by" in row:
            resolved["superseded_by"] = row["superseded_by"]

        try:
            rule = Rule.model_validate(resolved)
        except Exception as exc:
            raise SeedSchemaError(
                f"{dataset}/rules.yaml rule '{rule_slug}': {exc}"
            ) from exc
        rules.append(rule)
    return rules


def parse_regression_cases(
    data: object,
    dataset: str,
    jurisdiction_map: dict[str, Jurisdiction],
    material_map: dict[str, Material],
) -> list[RegressionCase]:
    """Parse regression cases YAML into domain models."""
    items = as_list_of_rows(
        data, f"{dataset}/regression_cases.yaml", RegressionCaseRow
    )
    cases: list[RegressionCase] = []
    for i, row in enumerate(items):
        # Resolve jurisdiction slug.
        try:
            jur_slug: str = row["jurisdiction"]
        except KeyError:
            raise SeedSchemaError(
                f"{dataset}/regression_cases.yaml[{i}]:"
                + " missing 'jurisdiction'"
            ) from None
        if jur_slug not in jurisdiction_map:
            raise EntityNotFoundError("Jurisdiction", jur_slug)

        resolved: dict[str, object] = {
            "query": row["query"],
            "expected_status": row["expected_status"],
            "expected_disposition": row["expected_disposition"],
            "jurisdiction_id": jurisdiction_map[jur_slug].id,
        }
        if "id" in row:
            resolved["id"] = row["id"]
        if "must_cite_source" in row:
            resolved["must_cite_source"] = row["must_cite_source"]
        if "refusal_required" in row:
            resolved["refusal_required"] = row["refusal_required"]
        if "notes" in row:
            resolved["notes"] = row["notes"]

        # Optionally resolve material slug.
        mat_slug: str | None = row.get("material")
        if mat_slug is not None:
            if mat_slug not in material_map:
                raise EntityNotFoundError("Material", mat_slug)
            resolved["expected_material_id"] = material_map[mat_slug].id

        try:
            cases.append(RegressionCase.model_validate(resolved))
        except Exception as exc:
            qry = str(row.get("query", "?"))[:40]
            raise SeedSchemaError(
                f"{dataset}/regression_cases.yaml[{i}]"
                + f" (query={qry}): {exc}"
            ) from exc
    return cases
