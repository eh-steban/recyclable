"""Shared domain builders for backend tests.

Valid-by-default constructors for the aggregates and Values that tests
assemble repeatedly.
"""

from tests.utils.builders.audit import make_answer_audit_record
from tests.utils.builders.knowledge_base import (
    make_jurisdiction,
    make_material,
    make_rule,
    make_source_document,
)
from tests.utils.builders.retrieval import make_citation, make_evaluated_answer

__all__ = [
    "make_answer_audit_record",
    "make_citation",
    "make_evaluated_answer",
    "make_jurisdiction",
    "make_material",
    "make_rule",
    "make_source_document",
]
