"""SQL implementation of the AnswerAuditRecordRepo port.

Verdict mapping (per private/specs/contracts/answer.md):
  Accepted (empty conditions)     -> 'yes'
  Accepted (non-empty conditions) -> 'conditional'
  Refused                         -> 'no'
  NotCovered | Conflicted         -> 'unknown'

Phase 5: both the evaluated and no_evaluation save paths are
implemented. outcome_kind reflects the actual domain outcome;
conditions JSONB round-trips Accepted.conditions.

reportAny / reportExplicitAny are disabled for this file: the JSONB
citations and validator_findings columns are runtime `Any` at the
ORM boundary.
"""

# pyright: reportAny=false, reportExplicitAny=false

import datetime as dt
import logging
import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import NoEvaluationReason
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    NotCovered,
    Refused,
)
from src.infra.db.models.answer_audit_record import AnswerAuditRecordORM
from src.infra.db.repos._exceptions import translate_repo_exceptions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verdict mapping
# ---------------------------------------------------------------------------


def _verdict_to_wire(record: AnswerAuditRecord) -> str:
    """Map domain ItemVerdict to the ORM wire string."""
    v = record.verdict
    if isinstance(v, Accepted):
        return "conditional" if v.conditions else "yes"
    if isinstance(v, Refused):
        return "no"
    # NotCovered | Conflicted
    return "unknown"


def _wire_to_verdict(
    verdict_str: str,
    conditions_json: list[Any] | None = None,
) -> Accepted | Refused | NotCovered | Conflicted:
    """Map ORM wire string back to a domain ItemVerdict variant.

    Phase 5: conditions_json is read from the JSONB conditions column
    so that 'conditional' rows round-trip faithfully.
    """
    if verdict_str == "yes":
        return Accepted()
    if verdict_str == "conditional":
        conds = tuple(str(c) for c in (conditions_json or []))
        return Accepted(conditions=conds)
    if verdict_str == "no":
        return Refused()
    return NotCovered()


# ---------------------------------------------------------------------------
# NoEvaluation reason mapping
# ---------------------------------------------------------------------------


def _reason_to_orm(reason: NoEvaluationReason) -> str:
    """Map domain NoEvaluationReason to the ORM enum string."""
    return reason.value  # StrEnum values match the ORM enum literals


def _orm_to_reason(reason_str: str) -> NoEvaluationReason:
    """Map ORM enum string back to domain NoEvaluationReason."""
    return NoEvaluationReason(reason_str)


# ---------------------------------------------------------------------------
# SqlAnswerAuditRecordRepo
# ---------------------------------------------------------------------------


class SqlAnswerAuditRecordRepo:
    """Persistence-oriented repo for AnswerAuditRecord aggregate."""

    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Port surface
    # ------------------------------------------------------------------

    def next_identity(self) -> AnswerAuditRecordId:
        """Mint a fresh AnswerAuditRecordId (application-generated UUID)."""
        return AnswerAuditRecordId(uuid.uuid4())

    def save(self, record: AnswerAuditRecord) -> None:
        """Persist a new AnswerAuditRecord row.

        This is an append-only operation; no UPDATE path exists.
        Exception translation: IntegrityError -> DuplicateAggregateError,
        OperationalError -> RepositoryConcurrencyError.
        """
        logger.debug(
            "save AnswerAuditRecord id=%s verdict=%s",
            record.id,
            record.verdict,
        )
        # outcome_kind/no_evaluation_reason come from the aggregate's
        # no_evaluation_reason field (set by the application service on
        # NoEvaluation paths; None for evaluated outcomes).
        no_eval_reason: str | None = None
        outcome_kind: str = "evaluated"

        if record.no_evaluation_reason is not None:
            outcome_kind = "no_evaluation"
            no_eval_reason = _reason_to_orm(record.no_evaluation_reason)

        citations_json = [
            {
                "title": c.title,
                "url": c.url,
                "quote": c.quote,
            }
            for c in record.citations
        ]
        validator_findings_json: dict[str, object] = {
            "retrieved_source_urls": sorted(record.retrieved_source_urls),
        }

        # Persist Accepted.conditions so round-trips are faithful.
        conditions_json: list[str] | None = None
        if isinstance(record.verdict, Accepted) and record.verdict.conditions:
            conditions_json = list(record.verdict.conditions)

        orm_row = AnswerAuditRecordORM(
            id=record.id.value,
            query_text=record.query_text,
            query_location_input=record.query_location_input,
            jurisdiction_id=record.jurisdiction_id.value,
            verdict=_verdict_to_wire(record),
            outcome_kind=outcome_kind,
            no_evaluation_reason=no_eval_reason,
            conditions=conditions_json,  # type: ignore[arg-type]
            recommended_action=record.recommended_action,
            citations=citations_json,  # type: ignore[arg-type]
            validator_findings=validator_findings_json,  # type: ignore[arg-type]
            prompt_version=record.prompt_version,
            model_id=record.model_id,
            latency_ms=record.latency_ms,
            created_at=record.created_at,
        )
        with translate_repo_exceptions("AnswerAuditRecord", str(record.id)):
            self._session.add(orm_row)
            self._session.flush()

    def find_by_id(
        self, record_id: AnswerAuditRecordId
    ) -> AnswerAuditRecord | None:
        logger.debug("find_by_id record_id=%s", record_id)
        stmt = select(AnswerAuditRecordORM).where(
            AnswerAuditRecordORM.id == record_id.value
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: AnswerAuditRecordORM) -> AnswerAuditRecord:
        raw_citations = cast(list[dict[str, Any]], row.citations or [])
        citations = tuple(
            Citation(
                title=c.get("title", ""),
                url=c.get("url", ""),
                quote=c.get("quote"),
            )
            for c in raw_citations
            if c.get("url")
        )
        findings = cast(dict[str, Any], row.validator_findings or {})
        retrieved_urls_raw: list[Any] = findings.get(
            "retrieved_source_urls", []
        )
        retrieved_source_urls = frozenset(str(u) for u in retrieved_urls_raw)

        # Read conditions JSONB column (may be None for old rows).
        raw_conditions = cast(
            list[Any] | None, getattr(row, "conditions", None)
        )

        # Reconstruct verdict from wire string + conditions.
        verdict = _wire_to_verdict(row.verdict, raw_conditions)

        # Ensure created_at is timezone-aware (Postgres returns tz-aware).
        created_at: datetime = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=dt.UTC)

        # jurisdiction_id is nullable in the ORM but always set for evaluated
        # records; default to a sentinel UUID if somehow NULL.
        jid = (
            row.jurisdiction_id
            if row.jurisdiction_id is not None
            else (uuid.UUID(int=0))
        )

        return AnswerAuditRecord(
            id=AnswerAuditRecordId(row.id),
            query_text=row.query_text,
            query_location_input=row.query_location_input,
            jurisdiction_id=JurisdictionId(jid),
            verdict=verdict,
            citations=citations,
            retrieved_source_urls=retrieved_source_urls,
            recommended_action=row.recommended_action,
            prompt_version=row.prompt_version,
            model_id=row.model_id,
            latency_ms=row.latency_ms or 0,
            created_at=created_at,
        )
