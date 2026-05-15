"""RetrievalService Domain Service.

Composes the Sonnet user-path choreography:
  1. Resolve location (LocationResolver)
  2. Normalize material (MaterialNormalizer)
  3. Retrieve rules (RuleRepo port)
  4. Compose prompt (ask_compose_v1 PromptComposer)
  5. Call LLM (RetrievalLLM port)
  6. Validate grounding (GroundingValidator Specification)
  7. Return EvaluatedAnswer | NoEvaluation

Multi-step choreography that would mean the same thing in any client
(HTTP, CLI, test) belongs here in the Domain Service, not in the
Application Service (services.md Principle 4, architecture.md §
Application services are thin task coordinators).
"""

import logging
from typing import final

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material_normalizer import MaterialNormalizer
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    Uncertain,
)
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source_repo import SourceRepo
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.grounding_validator import GroundingValidator
from src.domain.retrieval.location_resolver import resolve_location
from src.domain.retrieval.prompt_composer import ask_compose_v1
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import RetrievalLLM

logger = logging.getLogger(__name__)


@final
class RetrievalService:
    """Domain Service: composes the Sonnet user-path choreography.

    Takes ports as constructor parameters (MaterialNormalizer,
    RuleRepo, SourceRepo, RetrievalLLM) so that the Application
    Service can inject concrete implementations via FastAPI Depends
    without the domain importing infrastructure.
    """

    def __init__(
        self,
        material_normalizer: MaterialNormalizer,
        rule_repo: RuleRepo,
        source_repo: SourceRepo,
        retrieval_llm: RetrievalLLM,
    ) -> None:
        self._material_normalizer = material_normalizer
        self._rule_repo = rule_repo
        self._source_repo = source_repo
        self._retrieval_llm = retrieval_llm
        self._grounding_validator = GroundingValidator()

    def answer(self, query: Query) -> EvaluatedAnswer | NoEvaluation:
        """Resolve, retrieve, compose, call, validate, and return.

        Returns EvaluatedAnswer on a successful grounded response.
        Returns NoEvaluation with an appropriate reason on any refusal.
        """
        # Step 1: resolve location
        jurisdiction_id: JurisdictionId | None = resolve_location(
            query.location_input
        )
        if jurisdiction_id is None:
            logger.info(
                "location resolution miss: location=%r", query.location_input
            )
            return NoEvaluation(
                reason=NoEvaluationReason.OUT_OF_JURISDICTION,
                recommended_action=(
                    f"{query.location_input!r} is not yet supported. "
                    "Recyclable currently covers Denver only."
                ),
            )

        # Step 2: normalize material
        normalization = self._material_normalizer.normalize(query.text)

        if isinstance(normalization, Uncertain):
            logger.info(
                "material normalization uncertain: query=%r", query.text
            )
            return NoEvaluation(
                reason=NoEvaluationReason.UNCERTAIN_MATERIAL,
                recommended_action=(
                    "We couldn't identify a material in your query. "
                    "Try rephrasing with the item's name."
                ),
                clarifying_question=(
                    "Which material are you asking about? "
                    "Please be more specific."
                ),
            )

        if isinstance(normalization, Ambiguous):
            logger.info(
                "material normalization ambiguous: query=%r, candidates=%d",
                query.text,
                len(normalization.candidates),
            )
            candidate_names = ", ".join(
                c.canonical_name for c in normalization.candidates
            )
            return NoEvaluation(
                reason=NoEvaluationReason.CONFLICTED,
                recommended_action=(
                    f"Several materials match your query: {candidate_names}."
                ),
                clarifying_question=f"Did you mean one of: {candidate_names}?",
            )

        material_id = normalization.material.id

        # Step 3: retrieve rules
        rules = self._rule_repo.find_for(jurisdiction_id, material_id)
        if not rules:
            logger.info(
                "no rules for jurisdiction=%s material=%s",
                jurisdiction_id,
                material_id,
            )
            return NoEvaluation(
                reason=NoEvaluationReason.NO_EVIDENCE,
                recommended_action=(
                    "No recycling rule found for this material in "
                    "the queried jurisdiction."
                ),
            )

        # Collect retrieved source URLs for grounding validation
        # (INV-LLM-002). Sources are deduplicated by id; misses (a Rule
        # whose source_document_id has no matching SourceDocument)
        # contribute no URL to the set.
        source_ids = {rule.source_document_id for rule in rules}
        source_docs = [self._source_repo.find_by_id(sid) for sid in source_ids]
        retrieved_source_urls: frozenset[str] = frozenset(
            doc.url for doc in source_docs if doc is not None
        )

        # Step 4 + 5: compose prompt and call LLM
        messages = ask_compose_v1(query, rule_context="")
        llm_result = self._retrieval_llm.ask(messages, system_prompt="")

        if isinstance(llm_result, NoEvaluation):
            logger.warning(
                "LLM returned NoEvaluation: reason=%s", llm_result.reason
            )
            return llm_result

        # Step 6: validate grounding
        violations = self._grounding_validator.validate(
            llm_result.verdict,
            list(llm_result.citations),
            retrieved_source_urls,
        )
        if violations:
            logger.warning(
                "grounding violations: %s",
                [v.code for v in violations],
            )
            return NoEvaluation(
                reason=NoEvaluationReason.VALIDATOR_REJECTED,
                recommended_action=(
                    "The answer could not be grounded in the retrieved sources."
                ),
            )

        return llm_result

    def fallback_for_validator_rejection(self, query: Query) -> NoEvaluation:
        """Return a NoEvaluation(VALIDATOR_REJECTED) for construction-time
        grounding failures.

        """
        logger.info("fallback_for_validator_rejection: query=%r", query.text)
        return NoEvaluation(
            reason=NoEvaluationReason.VALIDATOR_REJECTED,
            recommended_action=(
                "The answer could not be grounded in the retrieved sources."
            ),
        )
