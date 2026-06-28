"""AnswerAuditRecordRepo port (Protocol)."""

from typing import Protocol

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.shared.repo import Repo


class AnswerAuditRecordRepo(
    Repo[AnswerAuditRecord, AnswerAuditRecordId], Protocol
): ...
