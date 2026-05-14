"""Repo for rules."""

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.knowledge_base.rule import Rule
from src.infra.db.models.rule import RuleORM

logger = logging.getLogger(__name__)


class SqlRuleRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

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
        _ = self._session.execute(stmt)
