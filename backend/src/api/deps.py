"""FastAPI dependency providers.

Each function is a FastAPI `Depends` callable that constructs and returns
an application or domain service wired with concrete infrastructure.
Tests substitute fakes via `app.dependency_overrides`.
"""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.answer_query import AnswerQuery
from src.application.get_jurisdiction_page import GetJurisdictionPage
from src.application.get_material_page import GetMaterialPage
from src.config import settings
from src.domain.audit.answer_audit_record_repo import AnswerAuditRecordRepo
from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
from src.domain.knowledge_base.material_normalizer import (
    MaterialNormalizer,
    MaterialNormalizerService,
)
from src.domain.knowledge_base.material_repo import MaterialRepo
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source_repo import SourceRepo
from src.domain.retrieval.retrieval_service import RetrievalService
from src.infra.db.repos.answer_audit_record_repo import PgAnswerAuditRecordRepo
from src.infra.db.repos.jurisdiction_repo import PgJurisdictionRepo
from src.infra.db.repos.material_alias_search import PgMaterialAliasSearch
from src.infra.db.repos.material_repo import PgMaterialRepo
from src.infra.db.repos.rule_repo import PgRuleRepo
from src.infra.db.repos.source_document_repo import PgSourceDocumentRepo
from src.infra.db.session import get_session
from src.infra.external.anthropic_client import AnthropicClient

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session]:
    """Yield a request-scoped DB session."""
    yield from get_session()


# ---------------------------------------------------------------------------
# Infrastructure leaf providers
# ---------------------------------------------------------------------------


def get_anthropic_client() -> AnthropicClient:
    """Construct the Anthropic SDK adapter (one per request)."""
    return AnthropicClient(api_key=settings.anthropic_api_key)


def get_jurisdiction_repo(
    session: Session = Depends(get_db),
) -> JurisdictionRepo:
    return PgJurisdictionRepo(session)


def get_material_repo(
    session: Session = Depends(get_db),
) -> MaterialRepo:
    return PgMaterialRepo(session)


def get_rule_repo(
    session: Session = Depends(get_db),
) -> RuleRepo:
    return PgRuleRepo(session)


def get_source_repo(
    session: Session = Depends(get_db),
) -> SourceRepo:
    return PgSourceDocumentRepo(session)


def get_audit_repo(
    session: Session = Depends(get_db),
) -> AnswerAuditRecordRepo:
    return PgAnswerAuditRecordRepo(session)


def get_material_normalizer(
    session: Session = Depends(get_db),
    anthropic: AnthropicClient = Depends(get_anthropic_client),
    material_repo: MaterialRepo = Depends(get_material_repo),
) -> MaterialNormalizer:
    """Provide a MaterialNormalizerService for the current request."""
    return MaterialNormalizerService(
        alias_search=PgMaterialAliasSearch(session),
        llm=anthropic,
        material_lookup=material_repo,
    )


# ---------------------------------------------------------------------------
# Domain service providers
# ---------------------------------------------------------------------------


def get_retrieval_service(
    normalizer: MaterialNormalizer = Depends(get_material_normalizer),
    rule_repo: RuleRepo = Depends(get_rule_repo),
    source_repo: SourceRepo = Depends(get_source_repo),
    anthropic: AnthropicClient = Depends(get_anthropic_client),
    jurisdiction_repo: JurisdictionRepo = Depends(get_jurisdiction_repo),
) -> RetrievalService:
    return RetrievalService(
        material_normalizer=normalizer,
        rule_repo=rule_repo,
        source_repo=source_repo,
        retrieval_llm=anthropic,
        jurisdiction_repo=jurisdiction_repo,
    )


# ---------------------------------------------------------------------------
# Application service providers
# ---------------------------------------------------------------------------


def get_answer_query(
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    audit_repo: AnswerAuditRecordRepo = Depends(get_audit_repo),
    jurisdiction_repo: JurisdictionRepo = Depends(get_jurisdiction_repo),
) -> AnswerQuery:
    """Provide the AnswerQuery application service."""
    return AnswerQuery(
        retrieval_service=retrieval_service,
        audit_repo=audit_repo,
        jurisdiction_repo=jurisdiction_repo,
    )


def get_jurisdiction_page_service(
    jurisdiction_repo: JurisdictionRepo = Depends(get_jurisdiction_repo),
    material_repo: MaterialRepo = Depends(get_material_repo),
    rule_repo: RuleRepo = Depends(get_rule_repo),
    source_repo: SourceRepo = Depends(get_source_repo),
) -> GetJurisdictionPage:
    """Provide the GetJurisdictionPage application service."""
    return GetJurisdictionPage(
        jurisdiction_repo=jurisdiction_repo,
        material_repo=material_repo,
        rule_repo=rule_repo,
        source_repo=source_repo,
    )


def get_material_page_service(
    jurisdiction_repo: JurisdictionRepo = Depends(get_jurisdiction_repo),
    material_repo: MaterialRepo = Depends(get_material_repo),
    rule_repo: RuleRepo = Depends(get_rule_repo),
    source_repo: SourceRepo = Depends(get_source_repo),
) -> GetMaterialPage:
    """Provide the GetMaterialPage application service."""
    return GetMaterialPage(
        jurisdiction_repo=jurisdiction_repo,
        material_repo=material_repo,
        rule_repo=rule_repo,
        source_repo=source_repo,
    )
