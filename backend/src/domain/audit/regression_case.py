"""RegressionCase entity and its typed identity Value.

A persisted eval-replay test artifact. Each case names a query against
a jurisdiction (optionally a material) plus the expected verdict shape,
and is replayed offline against the user path to detect regressions.

Lives in the audit Module per architecture.md: the audit Module's
charter covers "eval replay" alongside the user-path AnswerAuditRecord.
"""

import uuid
from dataclasses import dataclass

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import AcceptedStatus, Disposition

# ---------------------------------------------------------------------------
# Typed identity Value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegressionCaseId:
    """Typed identity Value for RegressionCase."""

    value: uuid.UUID

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegressionCase:
    """Eval-replay test case.

    Names a (query, jurisdiction, optional material) tuple plus the
    expected verdict shape. Replayed offline to detect regressions in
    the user path.
    """

    id: RegressionCaseId
    query: str
    jurisdiction_id: JurisdictionId
    expected_status: AcceptedStatus
    expected_disposition: Disposition
    expected_material_id: MaterialId | None = None
    must_cite_source: bool = True
    refusal_required: bool = False
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.query:
            raise ValueError("query must be non-empty")
