"""AnswerQuery application service -- user-path thin task coordinator.

The LLM call is outside the transaction boundary per
repositories.md Principle 9.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import final

from src.api.schemas.answer import Answer
from src.application.answer_query_command import AnswerQueryCommand
from src.application.mappers.domain_to_wire import (
    evaluated_answer_to_wire,
    no_evaluation_to_wire,
)
from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.audit.answer_audit_record_repo import AnswerAuditRecordRepo
from src.domain.exceptions import AnswerAuditRecordValidationError
from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
)
from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
)
from src.domain.retrieval.item_verdict import NotCovered
from src.domain.retrieval.location_resolver import resolve_location
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import SONNET_MODEL_ID
from src.domain.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

#: Sentinel values used when no LLM call was made (no_evaluation paths).
_NO_EVAL_PROMPT_VERSION = "no_evaluation"
_NO_EVAL_MODEL_ID = "none"

#: Sentinel JurisdictionId for OOJ records (no real jurisdiction resolved).
_OOJ_JURISDICTION_ID = JurisdictionId(uuid.UUID(int=0))


# ---------------------------------------------------------------------------
# Record factory (module-level for testability)
# ---------------------------------------------------------------------------


def _make_record(
    record_id: AnswerAuditRecordId,
    command: AnswerQueryCommand,
    outcome: EvaluatedAnswer | NoEvaluation,
    latency_ms: int,
    created_at: datetime,
    jurisdiction: Jurisdiction | None,
) -> AnswerAuditRecord:
    """Translate EvaluatedAnswer | NoEvaluation into an AnswerAuditRecord.

    EvaluatedAnswer -> outcome_kind='evaluated', no_evaluation_reason=None.
    NoEvaluation   -> verdict=NotCovered(), citations=(),
                      no_evaluation_reason=outcome.reason.

    The NotCovered sentinel makes the construction-time validator pass
    (NotCovered is not definitive; no citations are required).

    jurisdiction is the resolved Jurisdiction entity (or None for OOJ).
    The OOJ sentinel _OOJ_JURISDICTION_ID is used when jurisdiction is None;
    the repo save path maps that sentinel to NULL (existing behaviour).
    """
    jurisdiction_id = (
        jurisdiction.id if jurisdiction is not None else _OOJ_JURISDICTION_ID
    )

    if isinstance(outcome, EvaluatedAnswer):
        # Use citation URLs as retrieved_source_urls for the audit record.
        # GroundingValidator already verified every citation URL is in the
        # original retrieved set; this mirrors the same contract
        # (INV-LLM-002) without threading a separate url set through the
        # application layer.
        retrieved_urls = frozenset(c.url for c in outcome.citations)
        return AnswerAuditRecord(
            id=record_id,
            query_text=command.query_text,
            query_location_input=command.location_input,
            jurisdiction_id=jurisdiction_id,
            verdict=outcome.verdict,
            citations=outcome.citations,
            retrieved_source_urls=retrieved_urls,
            recommended_action=outcome.recommended_action,
            prompt_version="ask_compose_v1",
            model_id=SONNET_MODEL_ID,
            latency_ms=latency_ms,
            created_at=created_at,
            no_evaluation_reason=None,
        )
    else:
        return AnswerAuditRecord(
            id=record_id,
            query_text=command.query_text,
            query_location_input=command.location_input,
            jurisdiction_id=jurisdiction_id,
            verdict=NotCovered(),
            citations=(),
            retrieved_source_urls=frozenset(),
            recommended_action=outcome.recommended_action,
            prompt_version=_NO_EVAL_PROMPT_VERSION,
            model_id=_NO_EVAL_MODEL_ID,
            latency_ms=latency_ms,
            created_at=created_at,
            no_evaluation_reason=outcome.reason,
        )


# ---------------------------------------------------------------------------
# Application service
# ---------------------------------------------------------------------------


@final
class AnswerQuery:
    """Application service for the user-path ask flow.

    Constructor parameters are domain ports; FastAPI Depends injects
    concrete implementations at request time.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        audit_repo: AnswerAuditRecordRepo,
        jurisdiction_repo: JurisdictionRepo,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._audit_repo = audit_repo
        self._jurisdiction_repo = jurisdiction_repo

    def execute(self, command: AnswerQueryCommand) -> Answer:
        """Run the ask flow and return a wire Answer."""
        query = Query(
            text=command.query_text,
            location_input=command.location_input,
        )

        # Mint identity before any I/O (available on all paths).
        record_id = self._audit_repo.next_identity()

        slug = resolve_location(command.location_input)
        jurisdiction: Jurisdiction | None = (
            self._jurisdiction_repo.find_by_slug(slug) if slug else None
        )
        if slug is not None and jurisdiction is None:
            # A configured slug with no knowledge-base row is a misconfig:
            # the location resolved but the jurisdiction was never seeded.
            # The user path still refuses (out-of-jurisdiction downstream).
            logger.warning(
                "slug resolved but no jurisdiction row: slug=%r location=%r",
                slug,
                command.location_input,
            )

        # LLM call outside transaction boundary (repositories.md Principle 9).
        start = datetime.now(tz=UTC)
        outcome: EvaluatedAnswer | NoEvaluation = (
            self._retrieval_service.answer(query, jurisdiction)
        )
        end = datetime.now(tz=UTC)
        latency_ms = int((end - start).total_seconds() * 1000)

        logger.info(
            "retrieval complete: query=%r location=%r latency_ms=%d",
            command.query_text,
            command.location_input,
            latency_ms,
        )

        # Last-line defense after GroundingValidator.
        try:
            record = _make_record(
                record_id, command, outcome, latency_ms, end, jurisdiction
            )
        except AnswerAuditRecordValidationError as exc:
            _msg = (
                "construction-time validator rejected"
                " record id=%s: %s;"
                " falling back to VALIDATOR_REJECTED"
            )
            logger.warning(_msg, record_id, exc)
            outcome = self._retrieval_service.fallback_for_validator_rejection(
                query
            )
            record = _make_record(
                record_id, command, outcome, latency_ms, end, jurisdiction
            )

        self._audit_repo.save(record)

        return self._to_wire(record_id.value, command, outcome, jurisdiction)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_wire(
        self,
        record_id_value: uuid.UUID,
        command: AnswerQueryCommand,
        outcome: EvaluatedAnswer | NoEvaluation,
        jurisdiction: Jurisdiction | None,
    ) -> Answer:
        """Map domain outcome to wire Answer."""
        if isinstance(outcome, EvaluatedAnswer):
            jid = (
                jurisdiction.id
                if jurisdiction is not None
                else _OOJ_JURISDICTION_ID
            )
            jurisdiction_name = (
                jurisdiction.name if jurisdiction is not None else ""
            )
            return evaluated_answer_to_wire(
                outcome,
                record_id_value,
                jid,
                jurisdiction_name,
            )
        else:
            return no_evaluation_to_wire(
                outcome,
                record_id_value,
                command.location_input,
                jurisdiction_id=(
                    jurisdiction.id if jurisdiction is not None else None
                ),
                jurisdiction_name=(
                    jurisdiction.name if jurisdiction is not None else None
                ),
            )
