"""SQL implementation of the AnswerAuditRecordRepo port.

Verdict mapping (per private/specs/contracts/answer.md):
  Accepted (empty conditions)     -> 'yes'
  Accepted (non-empty conditions) -> 'conditional'
  Refused                         -> 'no'
  NotCovered | Conflicted         -> 'unknown'

For Phase 4, only the evaluated save path is implemented.
outcome_kind is always 'evaluated'; no_evaluation_reason is NULL.
The NoEvaluation save path is deferred to Phase 5 mappers.

reportAny / reportExplicitAny are disabled for this file: the JSONB
citations and validator_findings columns are runtime `Any` at the
ORM boundary. Phase 5 will replace the casts with a typed parser.
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
) -> Accepted | Refused | NotCovered | Conflicted:
    """Map ORM wire string back to a domain ItemVerdict variant.

    Phase 5 blocker: a row stored as 'conditional' reconstructs as
    Accepted([]), silently dropping the conditions tuple. The audit
    ORM has no column for conditions at Phase 4. Until Phase 5
    extends the schema (either a dedicated conditions JSONB column
    or persisting conditions inside validator_findings), do not
    call find_by_id() and then re-save the record -- the round-trip
    will coerce 'conditional' -> 'yes' on the next save().
    Tracked in Phase 4 Checkpoint Deferred items.
    """
    if verdict_str == "yes":
        return Accepted()
    if verdict_str == "conditional":
        return Accepted()
    if verdict_str == "no":
        return Refused()
    return NotCovered()


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
        orm_row = AnswerAuditRecordORM(
            id=record.id.value,
            query_text=record.query_text,
            query_location_input=record.query_location_input,
            jurisdiction_id=record.jurisdiction_id.value,
            verdict=_verdict_to_wire(record),
            outcome_kind="evaluated",
            no_evaluation_reason=None,
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

        # Reconstruct verdict from wire string.
        verdict = _wire_to_verdict(row.verdict)

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
