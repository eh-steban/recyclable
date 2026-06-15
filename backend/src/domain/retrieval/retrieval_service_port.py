"""RetrievalServicePort -- the user-path retrieval seam for AnswerQuery."""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import Jurisdiction
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
)
from src.domain.retrieval.query import Query


class RetrievalServicePort(Protocol):
    """Port for the Sonnet user-path retrieval choreography.

    AnswerQuery depends on this Protocol, not the concrete ``@final``
    RetrievalService, so test doubles substitute without subclassing.
    """

    def answer(
        self, query: Query, jurisdiction: Jurisdiction | None
    ) -> EvaluatedAnswer | NoEvaluation: ...

    def fallback_for_validator_rejection(
        self, query: Query
    ) -> NoEvaluation: ...
