"""ORM model registry.

Import Base and all mapped classes here so Alembic autogenerate sees them.
"""

from app.infra.db.models.answer_trace import AnswerTraceORM
from app.infra.db.models.base import Base
from app.infra.db.models.jurisdiction import JurisdictionORM
from app.infra.db.models.material import MaterialORM
from app.infra.db.models.material_alias import MaterialAliasORM
from app.infra.db.models.regression_case import RegressionCaseORM
from app.infra.db.models.rule import RuleORM
from app.infra.db.models.source_document import SourceDocumentORM

__all__ = [
    "Base",
    "JurisdictionORM",
    "MaterialORM",
    "MaterialAliasORM",
    "SourceDocumentORM",
    "RuleORM",
    "RegressionCaseORM",
    "AnswerTraceORM",
]
