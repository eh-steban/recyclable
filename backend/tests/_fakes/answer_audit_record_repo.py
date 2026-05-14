"""In-memory implementation of AnswerAuditRecordRepo for tests."""

import uuid

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)


class InMemoryAnswerAuditRecordRepo:
    """Dict-backed AnswerAuditRecordRepo satisfying the domain Protocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, AnswerAuditRecord] = {}

    def next_identity(self) -> AnswerAuditRecordId:
        return AnswerAuditRecordId(uuid.uuid4())

    def save(self, record: AnswerAuditRecord) -> None:
        self._store[record.id.value] = record

    def find_by_id(
        self, record_id: AnswerAuditRecordId
    ) -> AnswerAuditRecord | None:
        return self._store.get(record_id.value)
