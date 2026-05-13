"""Repo for regression cases."""

import logging
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.cli.seed_schemas.regression_case import RegressionCase
from src.infra.db.models.regression_case import RegressionCaseORM

logger = logging.getLogger(__name__)


class RegressionCaseRepo(Protocol):
    def upsert(self, case: RegressionCase) -> None: ...


class SqlRegressionCaseRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, case: RegressionCase) -> None:
        logger.debug(
            "upserting regression_case id=%s query=%.40s", case.id, case.query
        )
        stmt = (
            insert(RegressionCaseORM)
            .values(
                id=case.id,
                query=case.query,
                jurisdiction_id=case.jurisdiction_id,
                expected_material_id=case.expected_material_id,
                expected_status=case.expected_status.value,
                expected_disposition=case.expected_disposition.value,
                must_cite_source=case.must_cite_source,
                refusal_required=case.refusal_required,
                notes=case.notes,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "query": case.query,
                    "jurisdiction_id": case.jurisdiction_id,
                    "expected_material_id": case.expected_material_id,
                    "expected_status": case.expected_status.value,
                    "expected_disposition": case.expected_disposition.value,
                    "must_cite_source": case.must_cite_source,
                    "refusal_required": case.refusal_required,
                    "notes": case.notes,
                },
                # Only update when content actually changed.
                where=(
                    (RegressionCaseORM.query != case.query)
                    | (
                        RegressionCaseORM.expected_status
                        != case.expected_status.value
                    )
                    | (
                        RegressionCaseORM.expected_disposition
                        != case.expected_disposition.value
                    )
                    | (
                        RegressionCaseORM.refusal_required
                        != case.refusal_required
                    )
                    | (
                        RegressionCaseORM.must_cite_source
                        != case.must_cite_source
                    )
                ),
            )
        )
        _ = self._session.execute(stmt)
