"""Domain model import and ORM<->Pydantic round-trip tests.

These tests are pure (no DB) -- they verify that:
1. All imports resolve.
2. Each domain model can be instantiated with valid data.
3. ORM model can be reflected back to a domain model (round-trip via dict).

Note: AnswerTrace/AnswerTraceORM removed in Phase 2; AnswerAuditRecordORM
column-shape tests live in tests/infra/test_answer_audit_record_orm.py.
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.cli.seed_schemas import (
    AcceptedStatus,
    Confidence,
    Disposition,
    Jurisdiction,
    JurisdictionType,
    Material,
    MaterialAlias,
    MaterialCategory,
    RegressionCase,
    Rule,
    SourceDocument,
    SupportedStatus,
)
from src.infra.db.models import (
    AnswerAuditRecordORM,
    JurisdictionORM,
    MaterialAliasORM,
    MaterialORM,
    RegressionCaseORM,
    RuleORM,
    SourceDocumentORM,
)

# ---- Fixtures ----

JURISDICTION_ID = uuid.uuid4()
MATERIAL_ID = uuid.uuid4()
SOURCE_DOC_ID = uuid.uuid4()
RULE_ID = uuid.uuid4()
REGRESSION_CASE_ID = uuid.uuid4()
NOW = datetime.now(tz=UTC)


# ---- Domain model instantiation ----


def test_jurisdiction_model():
    j = Jurisdiction(
        id=JURISDICTION_ID,
        name="City and County of Denver",
        slug="denver",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
        created_at=NOW,
        updated_at=NOW,
    )
    assert j.slug == "denver"
    assert j.type == JurisdictionType.CITY


def test_material_model():
    m = Material(
        id=MATERIAL_ID,
        canonical_name="Aluminum beverage can",
        slug="aluminum-cans",
        category=MaterialCategory.METAL,
    )
    assert m.category == MaterialCategory.METAL
    assert m.parent_id is None


def test_material_alias_model():
    a = MaterialAlias(
        material_id=MATERIAL_ID,
        alias="soda can",
    )
    assert a.weight == 1


def test_source_document_model():
    doc = SourceDocument(
        id=SOURCE_DOC_ID,
        jurisdiction_id=JURISDICTION_ID,
        url="https://denvergov.org/recycling",
        title="Denver Recycling",
        authority_level=1,
        source_text="Aluminum cans are accepted for curbside recycling.",
        source_text_hash="abc123",
        fetched_at=NOW,
    )
    assert doc.authority_level == 1


@pytest.mark.parametrize("level", [0, 7])
def test_source_document_authority_level_bounds(level: int) -> None:
    with pytest.raises(ValidationError):
        _ = SourceDocument(
            id=SOURCE_DOC_ID,
            jurisdiction_id=JURISDICTION_ID,
            url="https://example.com",
            title="Test",
            authority_level=level,
            source_text="text",
            source_text_hash="hash",
            fetched_at=NOW,
        )


def test_rule_model():
    r = Rule(
        id=RULE_ID,
        jurisdiction_id=JURISDICTION_ID,
        material_id=MATERIAL_ID,
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_document_id=SOURCE_DOC_ID,
        source_quote="Aluminum cans are accepted for curbside recycling.",
        confidence=Confidence.HIGH,
    )
    assert r.disposition == Disposition.CURBSIDE_RECYCLE
    assert r.preparation_steps == []
    assert r.exceptions == []
    assert r.warnings == []


def test_regression_case_model():
    rc = RegressionCase(
        id=REGRESSION_CASE_ID,
        query="Can I recycle aluminum cans in Denver?",
        jurisdiction_id=JURISDICTION_ID,
        expected_status=AcceptedStatus.ACCEPTED,
        expected_disposition=Disposition.CURBSIDE_RECYCLE,
        must_cite_source=True,
        refusal_required=False,
    )
    assert rc.refusal_required is False


# ---- Enum validation ----


def test_jurisdiction_type_rejects_invalid() -> None:
    # Intentionally passing an invalid type value to test Pydantic validation.
    with pytest.raises(ValidationError):
        _ = Jurisdiction.model_validate(
            {
                "name": "Test",
                "slug": "test",
                "type": "village",  # not in enum
                "country": "US",
                "supported_status": "supported",
            }
        )


def test_material_category_rejects_invalid() -> None:
    # Intentionally passing an invalid category to test Pydantic validation.
    with pytest.raises(ValidationError):
        _ = Material.model_validate(
            {
                "canonical_name": "Mystery material",
                "slug": "mystery",
                "category": "unknown_category",  # not in enum
            }
        )


def test_rule_disposition_rejects_invalid() -> None:
    # Intentionally passing an invalid disposition to test Pydantic validation.
    with pytest.raises(ValidationError):
        _ = Rule.model_validate(
            {
                "jurisdiction_id": str(JURISDICTION_ID),
                "material_id": str(MATERIAL_ID),
                "disposition": "magic",  # not in enum
                "accepted_status": "accepted",
                "source_document_id": str(SOURCE_DOC_ID),
                "source_quote": "quote",
            }
        )


# ---- ORM model import (no DB needed) ----


def test_orm_models_importable():
    """All 7 ORM classes must be importable and have the correct tablename."""
    assert JurisdictionORM.__tablename__ == "jurisdictions"
    assert MaterialORM.__tablename__ == "materials"
    assert MaterialAliasORM.__tablename__ == "material_aliases"
    assert SourceDocumentORM.__tablename__ == "source_documents"
    assert RuleORM.__tablename__ == "rules"
    assert RegressionCaseORM.__tablename__ == "regression_cases"
    assert AnswerAuditRecordORM.__tablename__ == "answer_audit_records"


# ---- ORM -> Pydantic round-trip (no DB) ----


def test_jurisdiction_orm_to_domain_roundtrip():
    """Simulate reading an ORM row and mapping to the Pydantic domain model."""
    orm = JurisdictionORM(
        id=JURISDICTION_ID,
        name="City and County of Denver",
        slug="denver",
        type="city",
        country="US",
        supported_status="supported",
        created_at=NOW,
        updated_at=NOW,
    )
    domain = Jurisdiction(
        id=orm.id,
        name=orm.name,
        slug=orm.slug,
        type=JurisdictionType(orm.type),
        country=orm.country,
        supported_status=SupportedStatus(orm.supported_status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )
    assert domain.id == orm.id
    assert domain.name == orm.name
    assert domain.slug == orm.slug
    assert domain.type.value == orm.type
    assert domain.country == orm.country
    assert domain.supported_status.value == orm.supported_status
    assert domain.created_at == orm.created_at
    assert domain.updated_at == orm.updated_at


def test_material_orm_to_domain_roundtrip():
    orm = MaterialORM(
        id=MATERIAL_ID,
        canonical_name="Aluminum beverage can",
        slug="aluminum-cans",
        category="metal",
        parent_id=None,
    )
    domain = Material(
        id=orm.id,
        canonical_name=orm.canonical_name,
        slug=orm.slug,
        category=MaterialCategory(orm.category),
        parent_id=orm.parent_id,
    )
    assert domain.id == orm.id
    assert domain.canonical_name == orm.canonical_name
    assert domain.slug == orm.slug
    assert domain.category.value == orm.category
    assert domain.parent_id == orm.parent_id


def test_rule_orm_to_domain_roundtrip():
    orm = RuleORM(
        id=RULE_ID,
        jurisdiction_id=JURISDICTION_ID,
        material_id=MATERIAL_ID,
        disposition="curbside_recycle",
        accepted_status="accepted",
        preparation_steps=[],
        exceptions=[],
        warnings=[],
        source_document_id=SOURCE_DOC_ID,
        source_quote="Aluminum cans are accepted.",
        confidence="high",
        effective_from=None,
        superseded_by=None,
    )
    domain = Rule(
        id=orm.id,
        jurisdiction_id=orm.jurisdiction_id,
        material_id=orm.material_id,
        disposition=Disposition(orm.disposition),
        accepted_status=AcceptedStatus(orm.accepted_status),
        preparation_steps=orm.preparation_steps or [],
        exceptions=orm.exceptions or [],
        warnings=orm.warnings or [],
        source_document_id=orm.source_document_id,
        source_quote=orm.source_quote,
        confidence=Confidence(orm.confidence),
        effective_from=orm.effective_from,
        superseded_by=orm.superseded_by,
    )
    assert domain.id == orm.id
    assert domain.jurisdiction_id == orm.jurisdiction_id
    assert domain.material_id == orm.material_id
    assert domain.disposition.value == orm.disposition
    assert domain.accepted_status.value == orm.accepted_status
    assert domain.preparation_steps == orm.preparation_steps
    assert domain.exceptions == orm.exceptions
    assert domain.warnings == orm.warnings
    assert domain.source_document_id == orm.source_document_id
    assert domain.source_quote == orm.source_quote
    assert domain.confidence.value == orm.confidence
    assert domain.effective_from == orm.effective_from
    assert domain.superseded_by == orm.superseded_by


def test_source_document_orm_to_domain_roundtrip():
    orm = SourceDocumentORM(
        id=SOURCE_DOC_ID,
        jurisdiction_id=JURISDICTION_ID,
        url="https://denvergov.org/recycling",
        title="Denver Recycling",
        authority_level=1,
        fetched_at=NOW,
        effective_date=None,
        source_text="Aluminum cans are accepted for curbside recycling.",
        source_text_hash="abc123",
        last_reviewed_at=None,
    )
    domain = SourceDocument(
        id=orm.id,
        jurisdiction_id=orm.jurisdiction_id,
        url=orm.url,
        title=orm.title,
        authority_level=orm.authority_level,
        fetched_at=orm.fetched_at,
        effective_date=orm.effective_date,
        source_text=orm.source_text,
        source_text_hash=orm.source_text_hash,
        last_reviewed_at=orm.last_reviewed_at,
    )
    assert domain.id == orm.id
    assert domain.jurisdiction_id == orm.jurisdiction_id
    assert domain.url == orm.url
    assert domain.title == orm.title
    assert domain.authority_level == orm.authority_level
    assert domain.fetched_at == orm.fetched_at
    assert domain.effective_date == orm.effective_date
    assert domain.source_text == orm.source_text
    assert domain.source_text_hash == orm.source_text_hash
    assert domain.last_reviewed_at == orm.last_reviewed_at


def test_material_alias_orm_to_domain_roundtrip():
    orm = MaterialAliasORM(
        material_id=MATERIAL_ID,
        alias="soda can",
        weight=2,
    )
    domain = MaterialAlias(
        material_id=orm.material_id,
        alias=orm.alias,
        weight=orm.weight,
    )
    assert domain.material_id == orm.material_id
    assert domain.alias == orm.alias
    assert domain.weight == orm.weight


def test_regression_case_orm_to_domain_roundtrip():
    orm = RegressionCaseORM(
        id=REGRESSION_CASE_ID,
        query="Can I recycle aluminum cans in Denver?",
        jurisdiction_id=JURISDICTION_ID,
        expected_material_id=None,
        expected_status="accepted",
        expected_disposition="curbside_recycle",
        must_cite_source=True,
        refusal_required=False,
        notes=None,
    )
    domain = RegressionCase(
        id=orm.id,
        query=orm.query,
        jurisdiction_id=orm.jurisdiction_id,
        expected_material_id=orm.expected_material_id,
        expected_status=AcceptedStatus(orm.expected_status),
        expected_disposition=Disposition(orm.expected_disposition),
        must_cite_source=orm.must_cite_source,
        refusal_required=orm.refusal_required,
        notes=orm.notes,
    )
    assert domain.id == orm.id
    assert domain.query == orm.query
    assert domain.jurisdiction_id == orm.jurisdiction_id
    assert domain.expected_material_id == orm.expected_material_id
    assert domain.expected_status.value == orm.expected_status
    assert domain.expected_disposition.value == orm.expected_disposition
    assert domain.must_cite_source == orm.must_cite_source
    assert domain.refusal_required == orm.refusal_required
    assert domain.notes == orm.notes
