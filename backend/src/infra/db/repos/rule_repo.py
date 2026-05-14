"""SQL implementation of the RuleRepo port."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Confidence,
    Disposition,
    Rule,
    RuleId,
)
from src.domain.knowledge_base.source import SourceId
from src.infra.db.models.rule import RuleORM
from src.infra.db.repos._exceptions import translate_repo_exceptions

logger = logging.getLogger(__name__)


class SqlRuleRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Port surface
    # ------------------------------------------------------------------

    def next_identity(self) -> RuleId:
        """Mint a fresh RuleId (application-generated UUID)."""
        return RuleId(uuid.uuid4())

    def save(self, rule: Rule) -> None:
        logger.debug(
            "saving rule jurisdiction_id=%s material_id=%s",
            rule.jurisdiction_id,
            rule.material_id,
        )
        superseded_uuid = (
            rule.superseded_by.value if rule.superseded_by is not None else None
        )
        stmt = (
            insert(RuleORM)
            .values(
                id=rule.id.value,
                jurisdiction_id=rule.jurisdiction_id.value,
                material_id=rule.material_id.value,
                disposition=rule.disposition.value,
                accepted_status=rule.accepted_status.value,
                preparation_steps=list(rule.preparation_steps),
                exceptions=list(rule.exceptions),
                warnings=list(rule.warnings),
                source_document_id=rule.source_document_id.value,
                source_quote=rule.source_quote,
                confidence=rule.confidence.value,
                effective_from=rule.effective_from,
                superseded_by=superseded_uuid,
            )
            .on_conflict_do_update(
                # Conflict on the partial unique index for active rules.
                # index_where targets the partial index conflict.
                index_elements=["jurisdiction_id", "material_id"],
                index_where=(RuleORM.superseded_by.is_(None)),
                set_={
                    "disposition": rule.disposition.value,
                    "accepted_status": rule.accepted_status.value,
                    "preparation_steps": list(rule.preparation_steps),
                    "exceptions": list(rule.exceptions),
                    "warnings": list(rule.warnings),
                    "source_document_id": rule.source_document_id.value,
                    "source_quote": rule.source_quote,
                    "confidence": rule.confidence.value,
                    "effective_from": rule.effective_from,
                },
                # Only update when content actually changed.
                where=(
                    (RuleORM.disposition != rule.disposition.value)
                    | (RuleORM.accepted_status != rule.accepted_status.value)
                    | (RuleORM.source_quote != rule.source_quote)
                    | (RuleORM.confidence != rule.confidence.value)
                    | (
                        RuleORM.source_document_id
                        != rule.source_document_id.value
                    )
                ),
            )
        )
        with translate_repo_exceptions("Rule", str(rule.id)):
            _ = self._session.execute(stmt)

    def find_by_id(self, rule_id: RuleId) -> Rule | None:
        logger.debug("find_by_id rule_id=%s", rule_id)
        row = self._session.get(RuleORM, rule_id.value)
        if row is None:
            return None
        return self._to_domain(row)

    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]:
        """Return the active rule for an exact (jurisdiction, material) tuple.

        Filters: exact tuple match + superseded_by IS NULL (INV-AUTH-002).
        Orders by effective_from DESC NULLS LAST, LIMIT 1.
        Returns an empty list when no active rule exists.
        No cross-jurisdiction or cross-material fallback (INV-PROD-002).
        """
        logger.debug(
            "find_for jurisdiction_id=%s material_id=%s",
            jurisdiction_id,
            material_id,
        )
        stmt = (
            select(RuleORM)
            .where(
                RuleORM.jurisdiction_id == jurisdiction_id.value,
                RuleORM.material_id == material_id.value,
                RuleORM.superseded_by.is_(None),
            )
            .order_by(RuleORM.effective_from.desc().nullslast())
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return []
        return [self._to_domain(row)]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: RuleORM) -> Rule:
        return Rule(
            id=RuleId(row.id),
            jurisdiction_id=JurisdictionId(row.jurisdiction_id),
            material_id=MaterialId(row.material_id),
            disposition=Disposition(row.disposition),
            accepted_status=AcceptedStatus(row.accepted_status),
            source_document_id=SourceId(row.source_document_id),
            source_quote=row.source_quote,
            preparation_steps=tuple(row.preparation_steps),
            exceptions=tuple(row.exceptions),
            warnings=tuple(row.warnings),
            confidence=Confidence(row.confidence),
            effective_from=row.effective_from,
            superseded_by=(
                RuleId(row.superseded_by)
                if row.superseded_by is not None
                else None
            ),
        )
