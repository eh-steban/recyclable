"""Postgres implementation of the IngestionReportRepo port.

JSONB round-trip for proposed_rule_changes and conflicts:
  proposed_rule_changes -> list of {op, rule, confidence,
                           source_document_id, source_quote}
  conflicts -> list of {existing_rule_id, proposed, source_document_id,
               source_quote, reason}

reportAny / reportExplicitAny are disabled: JSONB columns are untyped
at the ORM boundary.
"""

# pyright: reportAny=false, reportExplicitAny=false

import logging
import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
    IngestionReportStatus,
    ProposedRuleChange,
    RuleOp,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.infra.db.models.ingestion_report import IngestionReportORM
from src.infra.db.repos._exceptions import translate_repo_exceptions

logger = logging.getLogger(__name__)


class PgIngestionReportRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def next_identity(self) -> IngestionReportId:
        return IngestionReportId(uuid.uuid4())

    def save(self, report: IngestionReport) -> None:
        logger.debug(
            "saving ingestion_report id=%s status=%s",
            report.id,
            report.status,
        )
        jur_uuid = (
            report.jurisdiction_id.value
            if report.jurisdiction_id is not None
            else None
        )
        stmt = (
            insert(IngestionReportORM)
            .values(
                id=report.id.value,
                jurisdiction_id=jur_uuid,
                seed_url=report.seed_url,
                proposed_rule_changes=_changes_to_json(
                    report.proposed_rule_changes
                ),
                conflicts=list(report.conflicts),
                missing_fields=list(report.missing_fields),
                status=str(report.status),
                reviewer_id=report.reviewer_id,
                prompt_name=report.prompt_name,
                prompt_version=report.prompt_version,
                model_id=report.model_id,
                trace_id=report.trace_id,
                created_at=report.created_at,
                decided_at=report.decided_at,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": str(report.status),
                    "proposed_rule_changes": _changes_to_json(
                        report.proposed_rule_changes
                    ),
                    "conflicts": list(report.conflicts),
                    "missing_fields": list(report.missing_fields),
                    "decided_at": report.decided_at,
                    "reviewer_id": report.reviewer_id,
                },
            )
        )
        with translate_repo_exceptions("IngestionReport", str(report.id)):
            _ = self._session.execute(stmt)

    def find_by_id(
        self, report_id: IngestionReportId
    ) -> IngestionReport | None:
        stmt = select(IngestionReportORM).where(
            IngestionReportORM.id == report_id.value
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    def find_pending(self) -> list[IngestionReport]:
        """Return all pending_review reports for Part B's apply path."""
        stmt = select(IngestionReportORM).where(
            IngestionReportORM.status == "pending_review"
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_domain(r) for r in rows]


# ---------------------------------------------------------------------------
# JSONB serialization helpers
# ---------------------------------------------------------------------------


def _changes_to_json(
    changes: tuple[ProposedRuleChange, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "op": str(c.op),
            "rule": c.rule,
            "confidence": c.confidence,
            "source_document_id": (
                str(c.source_document_id)
                if c.source_document_id is not None
                else None
            ),
            "source_quote": c.source_quote,
        }
        for c in changes
    ]


def _changes_from_json(
    raw: list[dict[str, Any]] | None,
) -> tuple[ProposedRuleChange, ...]:
    if not raw:
        return ()
    result: list[ProposedRuleChange] = []
    for item in raw:
        src_id_str: str | None = item.get("source_document_id")
        src_id = uuid.UUID(src_id_str) if src_id_str else None
        result.append(
            ProposedRuleChange(
                op=RuleOp(item["op"]),
                rule=item.get("rule", {}),
                confidence=item.get("confidence", "low"),
                source_document_id=src_id,
                source_quote=item.get("source_quote", ""),
            )
        )
    return tuple(result)


def _to_domain(row: IngestionReportORM) -> IngestionReport:
    raw_changes: list[dict[str, Any]] | None = cast(
        "list[dict[str, Any]] | None", row.proposed_rule_changes
    )
    raw_conflicts: list[dict[str, Any]] | None = cast(
        "list[dict[str, Any]] | None", row.conflicts
    )
    raw_missing: list[str] | None = cast("list[str] | None", row.missing_fields)

    return IngestionReport(
        id=IngestionReportId(row.id),
        jurisdiction_id=JurisdictionId(row.jurisdiction_id),
        trace_id=row.trace_id,
        seed_url=row.seed_url,
        proposed_rule_changes=_changes_from_json(raw_changes),
        conflicts=tuple(raw_conflicts) if raw_conflicts else (),
        missing_fields=tuple(raw_missing) if raw_missing else (),
        status=IngestionReportStatus(row.status),
        created_at=row.created_at,
        decided_at=row.decided_at,
        reviewer_id=row.reviewer_id,
        prompt_name=row.prompt_name,
        prompt_version=row.prompt_version,
        model_id=row.model_id,
    )
