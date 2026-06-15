"""Builder for the AnswerAuditRecord aggregate."""

import uuid
from datetime import UTC, datetime

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import NoEvaluationReason
from src.domain.retrieval.item_verdict import Accepted, ItemVerdict
from tests.utils.builders.retrieval import make_citation


def make_answer_audit_record(
    *,
    id: AnswerAuditRecordId | None = None,
    query_text: str = "Can I recycle cardboard?",
    query_location_input: str = "Denver",
    jurisdiction_id: JurisdictionId | None = None,
    verdict: ItemVerdict | None = None,
    citations: tuple[Citation, ...] | None = None,
    retrieved_source_urls: frozenset[str] | None = None,
    recommended_action: str = "Yes, recycle it curbside.",
    prompt_version: str = "ask_compose_v1",
    model_id: str = "claude-sonnet-4-6",
    latency_ms: int = 1200,
    created_at: datetime | None = None,
    no_evaluation_reason: NoEvaluationReason | None = None,
) -> AnswerAuditRecord:
    if citations is None:
        citations = (make_citation(),)
    if retrieved_source_urls is None:
        retrieved_source_urls = frozenset(c.url for c in citations)
    return AnswerAuditRecord(
        id=id or AnswerAuditRecordId(uuid.uuid4()),
        query_text=query_text,
        query_location_input=query_location_input,
        jurisdiction_id=jurisdiction_id or JurisdictionId(uuid.uuid4()),
        verdict=verdict or Accepted(),
        citations=citations,
        retrieved_source_urls=retrieved_source_urls,
        recommended_action=recommended_action,
        prompt_version=prompt_version,
        model_id=model_id,
        latency_ms=latency_ms,
        created_at=created_at or datetime.now(tz=UTC),
        no_evaluation_reason=no_evaluation_reason,
    )
