"""Domain model import and ORM<->domain round-trip tests.

These tests are pure (no DB) -- they verify that:
1. All imports resolve.
2. Each domain entity can be instantiated with valid data.
3. ORM model can be reflected back to a domain entity (round-trip via dict).

Note: AnswerTrace/AnswerTraceORM removed in Phase 2; AnswerAuditRecordORM
column-shape tests live in tests/infra/test_answer_audit_record_orm.py.
"""

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.audit.regression_case import RegressionCase, RegressionCaseId
from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
    JurisdictionType,
    SupportedStatus,
)
from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
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
        id=JurisdictionId(JURISDICTION_ID),
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
        id=MaterialId(MATERIAL_ID),
        canonical_name="Aluminum beverage can",
        slug="aluminum-cans",
        category=MaterialCategory.METAL,
    )
    assert m.category == MaterialCategory.METAL
    assert m.parent_id is None


def test_material_alias_model():
    a = MaterialAlias(
        material_id=MaterialId(MATERIAL_ID),
        alias="soda can",
    )
    assert a.weight == 1


def test_source_document_model():
    doc = SourceDocument(
        id=SourceId(SOURCE_DOC_ID),
        jurisdiction_id=JurisdictionId(JURISDICTION_ID),
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
    with pytest.raises(ValueError):
        _ = SourceDocument(
            id=SourceId(SOURCE_DOC_ID),
            jurisdiction_id=JurisdictionId(JURISDICTION_ID),
            url="https://example.com",
            title="Test",
            authority_level=level,
            source_text="text",
            source_text_hash="hash",
            fetched_at=NOW,
        )


def test_rule_model():
    r = Rule(
        id=RuleId(RULE_ID),
        jurisdiction_id=JurisdictionId(JURISDICTION_ID),
        material_id=MaterialId(MATERIAL_ID),
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_document_id=SourceId(SOURCE_DOC_ID),
        source_quote="Aluminum cans are accepted for curbside recycling.",
        confidence=Confidence.HIGH,
    )
    assert r.disposition == Disposition.CURBSIDE_RECYCLE
    assert r.preparation_steps == ()
    assert r.exceptions == ()
    assert r.warnings == ()


def test_regression_case_model():
    rc = RegressionCase(
        id=RegressionCaseId(REGRESSION_CASE_ID),
        query="Can I recycle aluminum cans in Denver?",
        jurisdiction_id=JurisdictionId(JURISDICTION_ID),
        expected_status=AcceptedStatus.ACCEPTED,
        expected_disposition=Disposition.CURBSIDE_RECYCLE,
        must_cite_source=True,
        refusal_required=False,
    )
    assert rc.refusal_required is False


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
    """Simulate reading an ORM row and mapping to the domain entity."""
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
        id=JurisdictionId(orm.id),
        name=orm.name,
        slug=orm.slug,
        type=JurisdictionType(orm.type),
        country=orm.country,
        supported_status=SupportedStatus(orm.supported_status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )
    assert domain.id.value == orm.id
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
        id=MaterialId(orm.id),
        canonical_name=orm.canonical_name,
        slug=orm.slug,
        category=MaterialCategory(orm.category),
        parent_id=None,
    )
    assert domain.id.value == orm.id
    assert domain.canonical_name == orm.canonical_name
    assert domain.slug == orm.slug
    assert domain.category.value == orm.category
    assert domain.parent_id is None


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
        id=RuleId(orm.id),
        jurisdiction_id=JurisdictionId(orm.jurisdiction_id),
        material_id=MaterialId(orm.material_id),
        disposition=Disposition(orm.disposition),
        accepted_status=AcceptedStatus(orm.accepted_status),
        preparation_steps=tuple(orm.preparation_steps or ()),
        exceptions=tuple(orm.exceptions or ()),
        warnings=tuple(orm.warnings or ()),
        source_document_id=SourceId(orm.source_document_id),
        source_quote=orm.source_quote,
        confidence=Confidence(orm.confidence),
        effective_from=orm.effective_from,
        superseded_by=None,
    )
    assert domain.id.value == orm.id
    assert domain.jurisdiction_id.value == orm.jurisdiction_id
    assert domain.material_id.value == orm.material_id
    assert domain.disposition.value == orm.disposition
    assert domain.accepted_status.value == orm.accepted_status
    assert list(domain.preparation_steps) == list(orm.preparation_steps)
    assert list(domain.exceptions) == list(orm.exceptions)
    assert list(domain.warnings) == list(orm.warnings)
    assert domain.source_document_id.value == orm.source_document_id
    assert domain.source_quote == orm.source_quote
    assert domain.confidence.value == orm.confidence
    assert domain.effective_from == orm.effective_from
    assert domain.superseded_by is None


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
        id=SourceId(orm.id),
        jurisdiction_id=JurisdictionId(orm.jurisdiction_id),
        url=orm.url,
        title=orm.title,
        authority_level=orm.authority_level,
        fetched_at=orm.fetched_at,
        effective_date=orm.effective_date,
        source_text=orm.source_text,
        source_text_hash=orm.source_text_hash,
        last_reviewed_at=orm.last_reviewed_at,
    )
    assert domain.id.value == orm.id
    assert domain.jurisdiction_id.value == orm.jurisdiction_id
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
        material_id=MaterialId(orm.material_id),
        alias=orm.alias,
        weight=orm.weight,
    )
    assert domain.material_id.value == orm.material_id
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
        id=RegressionCaseId(orm.id),
        query=orm.query,
        jurisdiction_id=JurisdictionId(orm.jurisdiction_id),
        expected_material_id=None,
        expected_status=AcceptedStatus(orm.expected_status),
        expected_disposition=Disposition(orm.expected_disposition),
        must_cite_source=orm.must_cite_source,
        refusal_required=orm.refusal_required,
        notes=orm.notes,
    )
    assert domain.id.value == orm.id
    assert domain.query == orm.query
    assert domain.jurisdiction_id.value == orm.jurisdiction_id
    assert domain.expected_material_id is None
    assert domain.expected_status.value == orm.expected_status
    assert domain.expected_disposition.value == orm.expected_disposition
    assert domain.must_cite_source == orm.must_cite_source
    assert domain.refusal_required == orm.refusal_required
    assert domain.notes == orm.notes
