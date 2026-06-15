"""In-memory implementation of AnswerAuditRecordRepo for tests."""

import uuid
from typing import override

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from tests.utils.fakes._base import InMemoryRepo


class MemAnswerAuditRecordRepo(
    InMemoryRepo[AnswerAuditRecord, AnswerAuditRecordId]
):
    @override
    def next_identity(self) -> AnswerAuditRecordId:
        return AnswerAuditRecordId(uuid.uuid4())
