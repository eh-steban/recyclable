"""ORM model registry.

Import Base and all mapped classes here so Alembic autogenerate sees them.
"""

from src.infra.db.models.answer_audit_record import AnswerAuditRecordORM
from src.infra.db.models.base import Base
from src.infra.db.models.jurisdiction import JurisdictionORM
from src.infra.db.models.material import MaterialORM
from src.infra.db.models.material_alias import MaterialAliasORM
from src.infra.db.models.regression_case import RegressionCaseORM
from src.infra.db.models.rule import RuleORM
from src.infra.db.models.source_document import SourceDocumentORM

__all__ = [
    "Base",
    "JurisdictionORM",
    "MaterialORM",
    "MaterialAliasORM",
    "SourceDocumentORM",
    "RuleORM",
    "RegressionCaseORM",
    "AnswerAuditRecordORM",
]
