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
from src.domain.knowledge_base.material_normalizer import (
    MaterialNormalizer,
    NormalizationResult,
)
from src.domain.knowledge_base.rule_repo import RuleRepo
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
    RuleRepo, RetrievalLLM) so that the Application Service can
    inject concrete implementations via FastAPI Depends without the
    domain importing infrastructure.
    """

    def __init__(
        self,
        material_normalizer: MaterialNormalizer,
        rule_repository: RuleRepo,
        retrieval_llm: RetrievalLLM,
    ) -> None:
        self._material_normalizer = material_normalizer
        self._rule_repository = rule_repository
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
        normalization: NormalizationResult | None = (
            self._material_normalizer.normalize(query.text)
        )
        if normalization is None:
            logger.info("material normalization miss: query=%r", query.text)
            return NoEvaluation(
                reason=NoEvaluationReason.NO_EVIDENCE,
                recommended_action=(
                    "Could not identify the material from your query. "
                    "Please try rephrasing."
                ),
            )

        if normalization.ambiguous:
            # Return ambiguous Refused -- prompt the user to clarify
            from src.domain.retrieval.item_verdict import Refused

            return EvaluatedAnswer(
                verdict=Refused(),
                citations=(),
                recommended_action="Please clarify which material you mean.",
                confidence="low",
                clarifying_question=(
                    "Which material are you asking about? "
                    "Please be more specific."
                ),
            )

        material_id = normalization.material.id

        # Step 3: retrieve rules
        rules = self._rule_repository.find_for(jurisdiction_id, material_id)
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

        retrieved_source_urls: frozenset[str] = frozenset(
            # Note: RetrievalService has no SourceRepo -- source URLs
            # are carried on the Rule's source_document_id. Phase 4 infra
            # will load SourceDocuments and extract URLs. For now, this is
            # a stub that Phase 4 will replace with repo calls.
            # The GroundingValidator still validates against whatever set
            # is passed in -- this ensures the seam is in place.
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
