"""Repository for rules."""
from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.models.rule import Rule
from app.infra.db.models.rule import RuleORM

logger = logging.getLogger(__name__)


class RuleRepository(Protocol):
    def upsert(self, rule: Rule) -> None: ...


class SqlRuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, rule: Rule) -> None:
        logger.debug(
            "upserting rule jurisdiction_id=%s material_id=%s",
            rule.jurisdiction_id,
            rule.material_id,
        )
        stmt = (
            insert(RuleORM)
            .values(
                id=rule.id,
                jurisdiction_id=rule.jurisdiction_id,
                material_id=rule.material_id,
                disposition=rule.disposition.value,
                accepted_status=rule.accepted_status.value,
                preparation_steps=rule.preparation_steps,
                exceptions=rule.exceptions,
                warnings=rule.warnings,
                source_document_id=rule.source_document_id,
                source_quote=rule.source_quote,
                confidence=rule.confidence.value,
                effective_from=rule.effective_from,
                superseded_by=rule.superseded_by,
            )
            .on_conflict_do_update(
                # Conflict on the partial unique index for active rules.
                # SQLAlchemy uses index_where for partial index conflict targets.
                index_elements=["jurisdiction_id", "material_id"],
                index_where=(RuleORM.superseded_by.is_(None)),
                set_={
                    "disposition": rule.disposition.value,
                    "accepted_status": rule.accepted_status.value,
                    "preparation_steps": rule.preparation_steps,
                    "exceptions": rule.exceptions,
                    "warnings": rule.warnings,
                    "source_document_id": rule.source_document_id,
                    "source_quote": rule.source_quote,
                    "confidence": rule.confidence.value,
                    "effective_from": rule.effective_from,
                },
            )
        )
        self._session.execute(stmt)
