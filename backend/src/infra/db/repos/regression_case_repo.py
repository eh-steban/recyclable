"""Repo for regression cases."""

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.audit.regression_case import RegressionCase
from src.infra.db.models.regression_case import RegressionCaseORM

logger = logging.getLogger(__name__)


class PgRegressionCaseRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, case: RegressionCase) -> None:
        logger.debug(
            "saving regression_case id=%s query=%.40s", case.id, case.query
        )
        expected_material_uuid = (
            case.expected_material_id.value
            if case.expected_material_id is not None
            else None
        )
        stmt = (
            insert(RegressionCaseORM)
            .values(
                id=case.id.value,
                query=case.query,
                jurisdiction_id=case.jurisdiction_id.value,
                expected_material_id=expected_material_uuid,
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
                    "jurisdiction_id": case.jurisdiction_id.value,
                    "expected_material_id": expected_material_uuid,
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
