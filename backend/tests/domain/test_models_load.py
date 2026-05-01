"""Domain model import and ORM<->Pydantic round-trip tests.

These tests are pure (no DB) -- they verify that:
1. All imports resolve.
2. Each domain model can be instantiated with valid data.
3. ORM model can be reflected back to a domain model (round-trip via dict).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.models import (
    AcceptedStatus,
    AnswerTrace,
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
from app.infra.db.models import (
    AnswerTraceORM,
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
ANSWER_TRACE_ID = uuid.uuid4()
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


def test_source_document_authority_level_bounds():
    with pytest.raises(ValidationError):
        SourceDocument(
            id=SOURCE_DOC_ID,
            jurisdiction_id=JURISDICTION_ID,
            url="https://example.com",
            title="Test",
            authority_level=0,  # out of range
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


def test_answer_trace_model():
    at = AnswerTrace(
        id=ANSWER_TRACE_ID,
        user_query="Can I recycle aluminum cans?",
        prompt_name="ask_compose",
        prompt_version=1,
        model_id="claude-sonnet-4-6",
        created_at=NOW,
    )
    assert at.cache_hit is False


# ---- Enum validation ----

def test_jurisdiction_type_rejects_invalid():
    with pytest.raises(ValidationError):
        Jurisdiction(
            name="Test",
            slug="test",
            type="village",  # not in enum
            country="US",
            supported_status=SupportedStatus.SUPPORTED,
        )


def test_material_category_rejects_invalid():
    with pytest.raises(ValidationError):
        Material(
            canonical_name="Mystery material",
            slug="mystery",
            category="unknown_category",  # not in enum
        )


def test_rule_disposition_rejects_invalid():
    with pytest.raises(ValidationError):
        Rule(
            jurisdiction_id=JURISDICTION_ID,
            material_id=MATERIAL_ID,
            disposition="magic",  # not in enum
            accepted_status=AcceptedStatus.ACCEPTED,
            source_document_id=SOURCE_DOC_ID,
            source_quote="quote",
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
    assert AnswerTraceORM.__tablename__ == "answer_traces"


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
    assert domain.slug == "denver"
    assert domain.type == JurisdictionType.CITY


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
    assert domain.slug == "aluminum-cans"


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
    assert domain.accepted_status == AcceptedStatus.ACCEPTED


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
    assert domain.expected_status == AcceptedStatus.ACCEPTED


def test_answer_trace_orm_to_domain_roundtrip():
    orm = AnswerTraceORM(
        id=ANSWER_TRACE_ID,
        user_query="Can I recycle aluminum cans?",
        jurisdiction_id=None,
        normalized_materials=[],
        retrieved_rule_ids=[],
        retrieved_source_ids=[],
        prompt_name="ask_compose",
        prompt_version=1,
        model_id="claude-sonnet-4-6",
        raw_model_output={},
        final_answer={},
        validator_result={},
        confidence=None,
        latency_ms=None,
        cache_hit=False,
        created_at=NOW,
    )
    domain = AnswerTrace(
        id=orm.id,
        user_query=orm.user_query,
        jurisdiction_id=orm.jurisdiction_id,
        normalized_materials=list(orm.normalized_materials or []),
        retrieved_rule_ids=list(orm.retrieved_rule_ids or []),
        retrieved_source_ids=list(orm.retrieved_source_ids or []),
        prompt_name=orm.prompt_name,
        prompt_version=orm.prompt_version,
        model_id=orm.model_id,
        raw_model_output=dict(orm.raw_model_output or {}),
        final_answer=dict(orm.final_answer or {}),
        validator_result=dict(orm.validator_result or {}),
        confidence=orm.confidence,
        latency_ms=orm.latency_ms,
        cache_hit=orm.cache_hit,
        created_at=orm.created_at,
    )
    assert domain.prompt_name == "ask_compose"
