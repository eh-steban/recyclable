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
import uuid
from datetime import UTC, date, datetime
from typing import NotRequired, TypedDict, cast

import yaml

from src.domain.audit.regression_case import (
    RegressionCase,
    RegressionCaseId,
)
from src.domain.exceptions import (
    EntityNotFoundError,
    SeedIntegrityError,
    SeedSchemaError,
)
from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
    JurisdictionType,
    SupportedStatus,
)
from src.domain.knowledge_base.material import (
    Material,
    MaterialCategory,
    MaterialId,
)
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Confidence,
    Disposition,
    Rule,
    RuleId,
)
from src.domain.knowledge_base.source import (
    SourceDocument,
    SourceId,
)
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


def _coerce_uuid(value: object) -> uuid.UUID:
    """Coerce a YAML scalar to uuid.UUID. Raises ValueError on failure."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        return uuid.UUID(value)
    raise ValueError(f"expected UUID or str, got {type(value).__name__}")


def _coerce_datetime(value: object) -> datetime:
    """Coerce a YAML scalar to datetime. Raises ValueError on failure."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError(f"expected datetime or str, got {type(value).__name__}")


def _coerce_date(value: object) -> date:
    """Coerce a YAML scalar to date. Raises ValueError on failure."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"expected date or str, got {type(value).__name__}")


def parse_jurisdictions(data: object, dataset: str) -> list[Jurisdiction]:
    """Parse the jurisdictions YAML document into domain entities.

    Any coercion or invariant-check failure surfaces as SeedSchemaError
    so callers can keep their single-exception catch shape.
    """
    items = as_list_of_rows(
        data, f"{dataset}/jurisdiction.yaml", JurisdictionRow
    )
    jurisdictions: list[Jurisdiction] = []
    for i, row in enumerate(items):
        try:
            raw_id: object = row.get("id")
            jid = (
                JurisdictionId(_coerce_uuid(raw_id))
                if raw_id is not None
                else JurisdictionId(uuid.uuid4())
            )
            raw_created: object = row.get("created_at")
            created_at = (
                _coerce_datetime(raw_created)
                if raw_created is not None
                else datetime.now(UTC)
            )
            raw_updated: object = row.get("updated_at")
            updated_at = (
                _coerce_datetime(raw_updated)
                if raw_updated is not None
                else datetime.now(UTC)
            )
            jurisdictions.append(
                Jurisdiction(
                    id=jid,
                    name=row["name"],
                    slug=row["slug"],
                    type=JurisdictionType(row["type"]),
                    country=row["country"],
                    supported_status=SupportedStatus(row["supported_status"]),
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        except (KeyError, ValueError) as exc:
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
    """Parse source_documents YAML into domain entities.

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

        source_text: str = row.get("source_text", "")
        source_text_hash: str = (
            row["source_text_hash"]
            if "source_text_hash" in row and row.get("source_text_hash")
            else _sha256(source_text)
        )

        try:
            raw_id: object = row.get("id")
            sid = (
                SourceId(_coerce_uuid(raw_id))
                if raw_id is not None
                else SourceId(uuid.uuid4())
            )
            raw_fetched: object = row.get("fetched_at")
            fetched_at = (
                _coerce_datetime(raw_fetched)
                if raw_fetched is not None
                else datetime.now(UTC)
            )
            raw_effective: object = row.get("effective_date")
            effective_date = (
                _coerce_date(raw_effective)
                if raw_effective is not None
                else None
            )
            raw_reviewed: object = row.get("last_reviewed_at")
            last_reviewed_at = (
                _coerce_datetime(raw_reviewed)
                if raw_reviewed is not None
                else None
            )
            docs.append(
                SourceDocument(
                    id=sid,
                    jurisdiction_id=jurisdiction_map[jur_slug].id,
                    url=row["url"],
                    title=row["title"],
                    authority_level=row["authority_level"],
                    fetched_at=fetched_at,
                    source_text=source_text,
                    source_text_hash=source_text_hash,
                    effective_date=effective_date,
                    last_reviewed_at=last_reviewed_at,
                )
            )
        except (KeyError, ValueError) as exc:
            url = row.get("url", "?")
            raise SeedSchemaError(
                f"{dataset}/source_documents.yaml[{i}] (url={url}): {exc}"
            ) from exc
    return docs


def parse_materials(
    data: object, dataset: str
) -> list[tuple[Material, list[str]]]:
    """Parse materials YAML into (Material, aliases) pairs.

    Returns a list of (domain.Material, [alias_str, ...]) tuples.
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

        try:
            raw_id: object = row.get("id")
            mid = (
                MaterialId(_coerce_uuid(raw_id))
                if raw_id is not None
                else MaterialId(uuid.uuid4())
            )
            raw_parent: object = row.get("parent_id")
            parent_id = (
                MaterialId(_coerce_uuid(raw_parent))
                if raw_parent is not None
                else None
            )
            material = Material(
                id=mid,
                canonical_name=row["canonical_name"],
                slug=row["slug"],
                category=MaterialCategory(row["category"]),
                parent_id=parent_id,
            )
        except (KeyError, ValueError) as exc:
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

        try:
            raw_id: object = row.get("id")
            rid = (
                RuleId(_coerce_uuid(raw_id))
                if raw_id is not None
                else RuleId(uuid.uuid4())
            )
            prep = tuple(row.get("preparation_steps") or ())
            exc_list = tuple(row.get("exceptions") or ())
            warn_list = tuple(row.get("warnings") or ())
            raw_conf: object = row.get("confidence")
            confidence = (
                Confidence(raw_conf)
                if raw_conf is not None
                else Confidence.HIGH
            )
            raw_effective_from: object = row.get("effective_from")
            effective_from = (
                _coerce_date(raw_effective_from)
                if raw_effective_from is not None
                else None
            )
            raw_superseded: object = row.get("superseded_by")
            superseded_by = (
                RuleId(_coerce_uuid(raw_superseded))
                if raw_superseded is not None
                else None
            )
            rule = Rule(
                id=rid,
                jurisdiction_id=jurisdiction_map[jur_slug].id,
                material_id=material_map[mat_slug].id,
                source_document_id=source_doc.id,
                disposition=Disposition(row["disposition"]),
                accepted_status=AcceptedStatus(row["accepted_status"]),
                source_quote=source_quote,
                preparation_steps=prep,
                exceptions=exc_list,
                warnings=warn_list,
                confidence=confidence,
                effective_from=effective_from,
                superseded_by=superseded_by,
            )
        except (KeyError, ValueError) as exc:
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

        # Optionally resolve material slug.
        mat_slug: str | None = row.get("material")
        expected_material_id: MaterialId | None = None
        if mat_slug is not None:
            if mat_slug not in material_map:
                raise EntityNotFoundError("Material", mat_slug)
            expected_material_id = material_map[mat_slug].id

        try:
            raw_id: object = row.get("id")
            rcid = (
                RegressionCaseId(_coerce_uuid(raw_id))
                if raw_id is not None
                else RegressionCaseId(uuid.uuid4())
            )
            cases.append(
                RegressionCase(
                    id=rcid,
                    query=row["query"],
                    jurisdiction_id=jurisdiction_map[jur_slug].id,
                    expected_status=AcceptedStatus(row["expected_status"]),
                    expected_disposition=Disposition(
                        row["expected_disposition"]
                    ),
                    expected_material_id=expected_material_id,
                    must_cite_source=row.get("must_cite_source", True),
                    refusal_required=row.get("refusal_required", False),
                    notes=row.get("notes"),
                )
            )
        except (KeyError, ValueError) as exc:
            qry = str(row.get("query", "?"))[:40]
            raise SeedSchemaError(
                f"{dataset}/regression_cases.yaml[{i}]"
                + f" (query={qry}): {exc}"
            ) from exc
    return cases
