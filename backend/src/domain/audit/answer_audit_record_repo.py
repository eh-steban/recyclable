"""AnswerAuditRecordRepo port (Protocol).

The interface lives in domain/audit/ alongside the aggregate.
The implementation lives in infra/db/repos/.

Design D7: persistence-oriented style with next_identity() seam.
"""

from typing import Protocol

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)


class AnswerAuditRecordRepo(Protocol):
    """Repo port for AnswerAuditRecord aggregate.

    Persistence-oriented: callers must call save() explicitly.
    next_identity() mints a UUID before construction.
    """

    def next_identity(self) -> AnswerAuditRecordId: ...

    def save(self, record: AnswerAuditRecord) -> None: ...

    def find_by_id(
        self, record_id: AnswerAuditRecordId
    ) -> AnswerAuditRecord | None: ...
