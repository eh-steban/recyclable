"""FastAPI dependency providers.

Each function is a FastAPI `Depends` callable that constructs and returns
an application service or domain service instance wired with concrete
infrastructure implementations.

Routes use `Depends(get_answer_query)` etc.; tests override these
functions via `app.dependency_overrides` to inject fakes without
touching the domain or infra layers.
"""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from src.application.answer_query import AnswerQuery
from src.application.get_jurisdiction_page import GetJurisdictionPage
from src.application.get_material_page import GetMaterialPage
from src.config import settings
from src.domain.retrieval.retrieval_service import RetrievalService
from src.infra.db.repos.answer_audit_record_repo import SqlAnswerAuditRecordRepo
from src.infra.db.repos.jurisdiction_repo import SqlJurisdictionRepo
from src.infra.db.repos.material_repo import SqlMaterialRepo
from src.infra.db.repos.rule_repo import SqlRuleRepo
from src.infra.db.repos.source_document_repo import SqlSourceDocumentRepo
from src.infra.db.session import get_session
from src.infra.external.anthropic_client import AnthropicClient
from src.infra.external.material_normalizer import SqlMaterialNormalizer

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
) -> SqlJurisdictionRepo:
    return SqlJurisdictionRepo(session)


def get_material_repo(
    session: Session = Depends(get_db),
) -> SqlMaterialRepo:
    return SqlMaterialRepo(session)


def get_rule_repo(
    session: Session = Depends(get_db),
) -> SqlRuleRepo:
    return SqlRuleRepo(session)


def get_source_repo(
    session: Session = Depends(get_db),
) -> SqlSourceDocumentRepo:
    return SqlSourceDocumentRepo(session)


def get_audit_repo(
    session: Session = Depends(get_db),
) -> SqlAnswerAuditRecordRepo:
    return SqlAnswerAuditRecordRepo(session)


def get_material_normalizer(
    session: Session = Depends(get_db),
    anthropic: AnthropicClient = Depends(get_anthropic_client),
) -> SqlMaterialNormalizer:
    return SqlMaterialNormalizer(session=session, llm=anthropic)


# ---------------------------------------------------------------------------
# Domain service providers
# ---------------------------------------------------------------------------


def get_retrieval_service(
    normalizer: SqlMaterialNormalizer = Depends(get_material_normalizer),
    rule_repo: SqlRuleRepo = Depends(get_rule_repo),
    source_repo: SqlSourceDocumentRepo = Depends(get_source_repo),
    anthropic: AnthropicClient = Depends(get_anthropic_client),
) -> RetrievalService:
    return RetrievalService(
        material_normalizer=normalizer,
        rule_repo=rule_repo,
        source_repo=source_repo,
        retrieval_llm=anthropic,
    )


# ---------------------------------------------------------------------------
# Application service providers
# ---------------------------------------------------------------------------


def get_answer_query(
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    audit_repo: SqlAnswerAuditRecordRepo = Depends(get_audit_repo),
) -> AnswerQuery:
    """Provide the AnswerQuery application service."""
    return AnswerQuery(
        retrieval_service=retrieval_service,
        audit_repo=audit_repo,
    )


def get_jurisdiction_page_service(
    jurisdiction_repo: SqlJurisdictionRepo = Depends(get_jurisdiction_repo),
    material_repo: SqlMaterialRepo = Depends(get_material_repo),
    rule_repo: SqlRuleRepo = Depends(get_rule_repo),
    source_repo: SqlSourceDocumentRepo = Depends(get_source_repo),
) -> GetJurisdictionPage:
    """Provide the GetJurisdictionPage application service."""
    return GetJurisdictionPage(
        jurisdiction_repo=jurisdiction_repo,
        material_repo=material_repo,
        rule_repo=rule_repo,
        source_repo=source_repo,
    )


def get_material_page_service(
    jurisdiction_repo: SqlJurisdictionRepo = Depends(get_jurisdiction_repo),
    material_repo: SqlMaterialRepo = Depends(get_material_repo),
    rule_repo: SqlRuleRepo = Depends(get_rule_repo),
    source_repo: SqlSourceDocumentRepo = Depends(get_source_repo),
) -> GetMaterialPage:
    """Provide the GetMaterialPage application service."""
    return GetMaterialPage(
        jurisdiction_repo=jurisdiction_repo,
        material_repo=material_repo,
        rule_repo=rule_repo,
        source_repo=source_repo,
    )
