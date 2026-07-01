"""IngestionReportRepo port.

Interface in domain/, implementation in infra/db/repos/.
"""

from typing import Protocol

from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
)
from src.domain.shared.repo import Repo


class IngestionReportRepo(Repo[IngestionReport, IngestionReportId], Protocol):
    """Repository port for the IngestionReport aggregate."""

    def find_pending(self) -> list[IngestionReport]:
        """Return all reports with status pending_review.

        Used by Part B's apply path to enumerate reports awaiting review.
        """
        ...
