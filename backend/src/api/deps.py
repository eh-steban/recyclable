"""FastAPI dependency providers.

Each function is a FastAPI `Depends` callable that constructs and returns
an application service or domain service instance wired with concrete
infrastructure implementations.

Routes use `Depends(get_answer_query)` etc.; tests override these
functions via `app.dependency_overrides` to inject fakes without
touching the domain or infra layers.

MaterialNormalizer DI note (Phase 6.5):
  get_material_normalizer() raises NotImplementedError intentionally.
  The real SqlMaterialNormalizer (trigram + Haiku LLM) is implemented
  in Phase 6.5. Until then, a live `uvicorn src.main:app` cannot silently
  serve wrong material answers -- any request that reaches the normalizer
  will fail fast. Route tests use app.dependency_overrides to inject a
  fake, which is correct test isolation and does NOT bypass this guard.
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
from src.domain.knowledge_base.material_normalizer import MaterialNormalizer
from src.domain.knowledge_base.material_repo import MaterialRepo
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source_repo import SourceRepo
from src.domain.retrieval.retrieval_service import RetrievalService
from src.infra.db.repos.answer_audit_record_repo import SqlAnswerAuditRecordRepo
from src.infra.db.repos.jurisdiction_repo import SqlJurisdictionRepo
from src.infra.db.repos.material_repo import SqlMaterialRepo
from src.infra.db.repos.rule_repo import SqlRuleRepo
from src.infra.db.repos.source_document_repo import SqlSourceDocumentRepo
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
    return SqlJurisdictionRepo(session)


def get_material_repo(
    session: Session = Depends(get_db),
) -> MaterialRepo:
    return SqlMaterialRepo(session)


def get_rule_repo(
    session: Session = Depends(get_db),
) -> RuleRepo:
    return SqlRuleRepo(session)


def get_source_repo(
    session: Session = Depends(get_db),
) -> SourceRepo:
    return SqlSourceDocumentRepo(session)


def get_audit_repo(
    session: Session = Depends(get_db),
) -> AnswerAuditRecordRepo:
    return SqlAnswerAuditRecordRepo(session)


def get_material_normalizer() -> MaterialNormalizer:
    """Fail-fast stub -- replaced by Phase 6.5 SqlMaterialNormalizer.

    Raises NotImplementedError so a live server cannot silently serve
    incorrect material answers before the real normalizer exists.
    Tests inject a fake via app.dependency_overrides (correct isolation).
    """
    raise NotImplementedError(
        "MaterialNormalizer is not yet implemented. "
        "Phase 6.5 will wire SqlMaterialNormalizer here. "
        "Use app.dependency_overrides[get_material_normalizer] in tests."
    )


# ---------------------------------------------------------------------------
# Domain service providers
# ---------------------------------------------------------------------------


def get_retrieval_service(
    normalizer: MaterialNormalizer = Depends(get_material_normalizer),
    rule_repo: RuleRepo = Depends(get_rule_repo),
    source_repo: SourceRepo = Depends(get_source_repo),
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
    audit_repo: AnswerAuditRecordRepo = Depends(get_audit_repo),
) -> AnswerQuery:
    """Provide the AnswerQuery application service."""
    return AnswerQuery(
        retrieval_service=retrieval_service,
        audit_repo=audit_repo,
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
