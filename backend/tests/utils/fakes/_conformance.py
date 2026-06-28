"""Static conformance probes: each fake satisfies its domain port.

basedpyright checks these assignments; nothing runs (the `TYPE_CHECKING`
guard is false at runtime). If a fake drifts from its port -- a finder
signature, a return type, a missing method -- the mismatch surfaces here
as a type error instead of passing silently.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.audit.answer_audit_record_repo import AnswerAuditRecordRepo
    from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
    from src.domain.knowledge_base.material_normalizer import (
        MaterialAliasSearch,
    )
    from src.domain.knowledge_base.material_repo import MaterialRepo
    from src.domain.knowledge_base.rule_repo import RuleRepo
    from src.domain.knowledge_base.source_repo import SourceRepo
    from tests.utils.fakes.answer_audit_record_repo import (
        MemAnswerAuditRecordRepo,
    )
    from tests.utils.fakes.jurisdiction_repo import MemJurisdictionRepo
    from tests.utils.fakes.material_alias_search import MemMaterialAliasSearch
    from tests.utils.fakes.material_repo import MemMaterialRepo
    from tests.utils.fakes.rule_repo import MemRuleRepo
    from tests.utils.fakes.source_repo import MemSourceRepo

    _rule: RuleRepo = MemRuleRepo()
    _material: MaterialRepo = MemMaterialRepo()
    _jurisdiction: JurisdictionRepo = MemJurisdictionRepo()
    _source: SourceRepo = MemSourceRepo()
    _audit: AnswerAuditRecordRepo = MemAnswerAuditRecordRepo()
    _alias_search: MaterialAliasSearch = MemMaterialAliasSearch([])
