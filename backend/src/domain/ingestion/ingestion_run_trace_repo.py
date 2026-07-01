"""IngestionRunTraceRepo port.

Interface in domain/, implementation in infra/db/repos/.
"""

from typing import Protocol

from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.domain.shared.repo import Repo


class IngestionRunTraceRepo(
    Repo[IngestionRunTrace, IngestionRunTraceId], Protocol
):
    """Repository port for the IngestionRunTrace entity."""
